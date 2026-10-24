"""Snowflake derived-feature export and explicitly requested classifier training.

No classifier is trained or promoted on application startup. User feedback labels
are subjective helpfulness reports, never objective quality or acceptance labels.
All network work runs outside the ASGI event loop. Driver errors are sanitized.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

FEATURE_KEYS = (
    "task_type",
    "missing_constraints_count",
    "candidate_count",
    "relevant_count",
    "best_retrieval_score",
    "enhancement_type",
    "model_version",
)
TASK_TYPES = {"coding", "writing", "analysis", "research", "planning", "other"}
FEATURE_COLUMNS = ",".join(key.upper() for key in FEATURE_KEYS)


class _ValidationError(ValueError):
    """Fixed-message validation failures safe to return across the boundary."""


class SnowflakeUnavailable(Exception):
    pass


class ClassifierColdStart(Exception):
    pass


@dataclass(frozen=True)
class Prediction:
    source: str
    model_version: str | None
    predicted_class: str | None
    probabilities: dict[str, float]


@dataclass(frozen=True)
class TrainingPlan:
    version: str
    # Mandatory mapping must group related revisions and knowledge-derived duplicate
    # tasks together. Request IDs alone are not a valid grouping assertion.
    task_groups: Mapping[str, str]
    label_definition: str
    minimum_per_class: int = 20
    test_fraction: float = 0.2


def _identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value):
        raise _ValidationError("Invalid Snowflake object identifier")
    return value.upper()


def _features(value: Any) -> dict[str, Any]:
    source = asdict(value) if hasattr(value, "__dataclass_fields__") else dict(value)
    # A strict whitelist prevents prompt/tag/summary payloads entering Snowflake.
    try:
        result = {key: source[key] for key in FEATURE_KEYS}
    except KeyError:
        raise _ValidationError("Missing required derived feature") from None
    if result["task_type"] not in TASK_TYPES:
        raise _ValidationError("Unknown derived task category")
    if result["enhancement_type"] not in {"autocomplete", "multiple_choice", "none"}:
        raise _ValidationError("Unknown suggestion category")
    for key in ("missing_constraints_count", "candidate_count", "relevant_count"):
        if type(result[key]) is not int or not 0 <= result[key] <= 100000:
            raise _ValidationError("Invalid derived feature count")
    score = result["best_retrieval_score"]
    if score is not None and (
        not isinstance(score, (int, float)) or not math.isfinite(score) or not -1 <= score <= 1
    ):
        raise _ValidationError("Invalid retrieval score")
    if not re.fullmatch(r"[A-Za-z0-9_.:/+-]{1,160}", result["model_version"]):
        raise _ValidationError("Invalid model version")
    return result


def _timestamp(value) -> datetime:
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else value
    except ValueError:
        raise _ValidationError("Invalid event timestamp") from None
    if not isinstance(result, datetime) or result.tzinfo is None:
        raise _ValidationError("Expected timezone-aware event timestamp")
    return result.astimezone(UTC)


class SnowflakeClassifier:
    def __init__(
        self,
        connect_kwargs: Mapping[str, Any] | None = None,
        *,
        connection_factory: Callable[..., Any] | None = None,
        table_prefix="PROMPT_ENHANCE",
        model_version: str | None = None,
    ):
        self._connect_kwargs = dict(connect_kwargs or {})
        self._factory = connection_factory
        self.prefix = _identifier(table_prefix)
        self.model_version = _identifier(model_version) if model_version else None
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self._connect_kwargs or self._factory)

    @contextmanager
    def _connection(self):
        if not self.configured:
            raise SnowflakeUnavailable("Snowflake is not configured")
        try:
            factory = self._factory
            if factory is None:
                import snowflake.connector

                factory = snowflake.connector.connect
            kwargs = {"login_timeout": 10, "network_timeout": 30, **self._connect_kwargs}
            connection = factory(**kwargs)
            try:
                yield connection
            finally:
                connection.close()
        except (_ValidationError, ClassifierColdStart):
            raise
        except Exception:  # noqa: BLE001 - sanitize all connector exceptions.
            raise SnowflakeUnavailable("Snowflake operation failed") from None

    def _setup(self, cursor):
        cursor.execute(f"""CREATE TRANSIENT TABLE IF NOT EXISTS {self.prefix}_EVENTS (
            EVENT_ID VARCHAR NOT NULL,REQUEST_ID VARCHAR NOT NULL,EVENT_TYPE VARCHAR NOT NULL,
            OBSERVED_RESULT VARCHAR,TIMESTAMP TIMESTAMP_TZ NOT NULL,EXPIRES_AT TIMESTAMP_TZ NOT NULL,
            FEATURE_SCHEMA NUMBER NOT NULL,TASK_TYPE VARCHAR,MISSING_CONSTRAINTS_COUNT NUMBER,
            CANDIDATE_COUNT NUMBER,RELEVANT_COUNT NUMBER,BEST_RETRIEVAL_SCORE FLOAT,
            ENHANCEMENT_TYPE VARCHAR,MODEL_VERSION VARCHAR) DATA_RETENTION_TIME_IN_DAYS=0""")
        cursor.execute(f"""CREATE TRANSIENT TABLE IF NOT EXISTS {self.prefix}_MODELS (
            VERSION VARCHAR NOT NULL,OBJECT_NAME VARCHAR NOT NULL,CREATED_AT TIMESTAMP_TZ NOT NULL,
            EXPIRES_AT TIMESTAMP_TZ NOT NULL,REPORT VARIANT NOT NULL) DATA_RETENTION_TIME_IN_DAYS=0""")
        cursor.execute(
            """SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA=CURRENT_SCHEMA() AND TABLE_NAME IN (%s,%s)
            AND IS_TRANSIENT<>'YES' """,
            (self.prefix + "_EVENTS", self.prefix + "_MODELS"),
        )
        if cursor.fetchone()[0]:
            raise _ValidationError("Snowflake export tables must be transient to honor retention")
        # Existing transient tables must also obey the same Time Travel policy.
        cursor.execute(f"ALTER TABLE {self.prefix}_EVENTS SET DATA_RETENTION_TIME_IN_DAYS=0")
        cursor.execute(f"ALTER TABLE {self.prefix}_MODELS SET DATA_RETENTION_TIME_IN_DAYS=0")

    async def status(self) -> str:
        if not self.configured:
            return "not_configured"
        try:
            await asyncio.to_thread(self._health)
            return "ready"
        except SnowflakeUnavailable:
            return "unavailable"

    async def active_model_version(self) -> str | None:
        """A configured name is active only while its registry entry is live."""
        if not self.configured or not self.model_version:
            return None
        try:
            return await asyncio.to_thread(self._active_model_version)
        except SnowflakeUnavailable:
            return None

    def _active_model_version(self) -> str | None:
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"""SELECT VERSION FROM {self.prefix}_MODELS
                    WHERE VERSION=%s AND EXPIRES_AT>CURRENT_TIMESTAMP() ORDER BY CREATED_AT DESC LIMIT 1""",
                    (self.model_version,),
                )
                row = cursor.fetchone()
                return row[0] if row else None
            finally:
                cursor.close()

    def _health(self):
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                cursor.close()

    async def export(self, events: Sequence[Mapping[str, Any]]) -> int:
        now = datetime.now(UTC)
        rows = []
        for event in events:
            timestamp = _timestamp(event["timestamp"])
            expiry = min(_timestamp(event["expires_at"]), timestamp + timedelta(days=30))
            if expiry <= now:
                continue
            if event["event_type"] not in {
                "displayed",
                "accepted",
                "declined",
                "stale",
                "failed",
                "observed",
            }:
                raise _ValidationError("Unknown outcome event")
            observed = event.get("observed_result")
            if observed not in {None, "helpful", "unhelpful", "unknown"} or (
                observed is not None and event["event_type"] != "observed"
            ):
                raise _ValidationError("Only independently observed events may have helpfulness labels")
            features = _features(event["features"])
            if event["feature_schema"] != 1:
                raise _ValidationError("Unsupported feature schema")
            rows.append(
                (
                    str(event["event_id"]),
                    str(event["request_id"]),
                    event["event_type"],
                    observed,
                    timestamp,
                    expiry,
                    1,
                    *(features[key] for key in FEATURE_KEYS),
                )
            )
        if not rows:
            return 0
        async with self._lock:
            return await asyncio.to_thread(self._export, rows)

    def _export(self, rows):
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                self._setup(cursor)
                columns = (
                    "EVENT_ID,REQUEST_ID,EVENT_TYPE,OBSERVED_RESULT,TIMESTAMP,EXPIRES_AT,FEATURE_SCHEMA,"
                    + FEATURE_COLUMNS
                )
                # Server-side MERGE keeps repeated export batches idempotent. The
                # single-user exporter serializes batches; deployment must run one
                # export worker (standard Snowflake tables do not enforce UNIQUE).
                selects = ",".join(f"%s AS {column}" for column in columns.split(","))
                cursor.executemany(
                    f"""MERGE INTO {self.prefix}_EVENTS t USING (SELECT {selects}) s
                    ON t.EVENT_ID=s.EVENT_ID WHEN NOT MATCHED THEN INSERT({columns})
                    VALUES({",".join("s." + column for column in columns.split(","))})""",
                    rows,
                )
                connection.commit()
                return len(rows)
            finally:
                cursor.close()

    async def cleanup(self) -> int:
        if not self.configured:
            return 0
        async with self._lock:
            return await asyncio.to_thread(self._cleanup)

    def _cleanup(self):
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                self._setup(cursor)
                cursor.execute(
                    f"SELECT OBJECT_NAME FROM {self.prefix}_MODELS WHERE EXPIRES_AT<=CURRENT_TIMESTAMP()"
                )
                for row in cursor.fetchall():
                    cursor.execute(f"DROP SNOWFLAKE.ML.CLASSIFICATION IF EXISTS {_identifier(row[0])}")
                cursor.execute(f"DELETE FROM {self.prefix}_MODELS WHERE EXPIRES_AT<=CURRENT_TIMESTAMP()")
                count = max(0, cursor.rowcount)
                cursor.execute(f"DELETE FROM {self.prefix}_EVENTS WHERE EXPIRES_AT<=CURRENT_TIMESTAMP()")
                count += max(0, cursor.rowcount)
                connection.commit()
                return count
            finally:
                cursor.close()

    async def predict(self, features) -> Prediction:
        validated = _features(features)
        if not self.configured or not self.model_version:
            return Prediction("baseline", None, None, {})
        try:
            return await asyncio.to_thread(self._predict, validated)
        except (SnowflakeUnavailable, ClassifierColdStart):
            return Prediction("baseline", None, None, {})

    def _predict(self, features):
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"""SELECT OBJECT_NAME FROM {self.prefix}_MODELS
                    WHERE VERSION=%s AND EXPIRES_AT>CURRENT_TIMESTAMP() ORDER BY CREATED_AT DESC LIMIT 1""",
                    (self.model_version,),
                )
                row = cursor.fetchone()
                if not row:
                    raise ClassifierColdStart("No valid trained classifier has been promoted")
                model = _identifier(row[0])
                cursor.execute(
                    f"SELECT {model}!PREDICT(INPUT_DATA=>PARSE_JSON(%s))",
                    (json.dumps({key.upper(): value for key, value in features.items()}),),
                )
                result = cursor.fetchone()[0]
                result = json.loads(result) if isinstance(result, str) else result
                if result.get("class") not in {"helpful", "unhelpful"}:
                    raise _ValidationError("Classifier returned an unknown label")
                probabilities = {key: float(value) for key, value in result.get("probability", {}).items()}
                if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities.values()):
                    raise _ValidationError("Classifier returned invalid probabilities")
                return Prediction("snowflake", self.model_version, result["class"], probabilities)
            finally:
                cursor.close()

    async def train(self, plan: TrainingPlan) -> dict[str, Any]:
        """Manual train/evaluate on real exported subjective helpfulness observations.

        No acceptance labels; callers supply an explicit label definition and a
        mapping grouping related tasks before this potentially billable operation.
        The artifact expires no later than the earliest contributing observation.
        Training does not set model_version; promotion is a separate config change.
        """
        _identifier(plan.version)
        if plan.label_definition != "user_reported_helpfulness":
            raise _ValidationError("Training target must explicitly be user_reported_helpfulness")
        if plan.minimum_per_class < 20 or not 0.1 <= plan.test_fraction <= 0.4:
            raise _ValidationError("Insufficient minimum data or invalid held-out fraction")
        async with self._lock:
            return await asyncio.to_thread(self._train, plan)

    def _train(self, plan):
        version = _identifier(plan.version)
        model = _identifier(self.prefix + "_MODEL_" + version)
        created_model = False
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                self._setup(cursor)
                cursor.execute(f"SELECT VERSION FROM {self.prefix}_MODELS WHERE VERSION=%s", (version,))
                if cursor.fetchone():
                    raise _ValidationError("Model version already exists; choose a new version")
                cursor.execute(f"""SELECT REQUEST_ID,TIMESTAMP,EXPIRES_AT,{FEATURE_COLUMNS},OBSERVED_RESULT
                    FROM {self.prefix}_EVENTS WHERE EVENT_TYPE='observed'
                    AND OBSERVED_RESULT IN ('helpful','unhelpful') AND EXPIRES_AT>CURRENT_TIMESTAMP()
                    QUALIFY ROW_NUMBER() OVER(PARTITION BY REQUEST_ID ORDER BY TIMESTAMP DESC,EVENT_ID DESC)=1""")
                records = cursor.fetchall()
                if any(row[0] not in plan.task_groups for row in records):
                    raise _ValidationError("Every labeled request requires an explicit related-task group")
                counts = {
                    label: sum(row[-1] == label for row in records) for label in ("helpful", "unhelpful")
                }
                if min(counts.values()) < plan.minimum_per_class:
                    raise ClassifierColdStart("Insufficient independently observed labels for training")
                groups = {}
                for row in records:
                    group = plan.task_groups[row[0]]
                    minimum, maximum = groups.get(group, (row[1], row[1]))
                    groups[group] = (min(minimum, row[1]), max(maximum, row[1]))
                ordered_times = sorted(row[1] for row in records)
                cutoff = ordered_times[
                    min(len(ordered_times) - 1, int(len(ordered_times) * (1 - plan.test_fraction)))
                ]
                train_groups = {group for group, (_, maximum) in groups.items() if maximum < cutoff}
                test_groups = {group for group, (minimum, _) in groups.items() if minimum >= cutoff}
                train = [row for row in records if plan.task_groups[row[0]] in train_groups]
                test = [row for row in records if plan.task_groups[row[0]] in test_groups]
                if not test or {row[-1] for row in train} != {"helpful", "unhelpful"}:
                    raise ClassifierColdStart(
                        "Grouped temporal split lacks training classes or held-out tasks"
                    )
                cursor.execute(f"""CREATE TEMPORARY TABLE {self.prefix}_TRAIN (
                    TASK_TYPE VARCHAR,MISSING_CONSTRAINTS_COUNT NUMBER,CANDIDATE_COUNT NUMBER,
                    RELEVANT_COUNT NUMBER,BEST_RETRIEVAL_SCORE FLOAT,ENHANCEMENT_TYPE VARCHAR,
                    MODEL_VERSION VARCHAR,LABEL VARCHAR) DATA_RETENTION_TIME_IN_DAYS=0""")
                cursor.executemany(
                    f"INSERT INTO {self.prefix}_TRAIN VALUES({','.join(['%s'] * 8)})",
                    [tuple(row[3:]) for row in train],
                )
                cursor.execute(f"""CREATE SNOWFLAKE.ML.CLASSIFICATION {model}(
                    INPUT_DATA=>SYSTEM$REFERENCE('TABLE','{self.prefix}_TRAIN'),TARGET_COLNAME=>'LABEL',
                    CONFIG_OBJECT=>{{'evaluate':TRUE,'on_error':'ABORT'}})""")
                created_model = True
                report = self._evaluate_rows(cursor, model, train, test)
                expiry = min(_timestamp(row[2]) for row in records)
                report.update(
                    version=version,
                    target=plan.label_definition,
                    feature_schema=1,
                    label_provenance="explicit_user_observation",
                    split_strategy="grouped_temporal",
                    test_fraction=plan.test_fraction,
                    train_rows=len(train),
                    test_rows=len(test),
                    class_counts=counts,
                    excluded_boundary_rows=len(records) - len(train) - len(test),
                    window_start=min(_timestamp(row[1]) for row in records).isoformat(),
                    window_end=max(_timestamp(row[1]) for row in records).isoformat(),
                    expires_at=expiry.isoformat(),
                )
                cursor.execute(
                    f"""INSERT INTO {self.prefix}_MODELS(VERSION,OBJECT_NAME,CREATED_AT,EXPIRES_AT,REPORT)
                    SELECT %s,%s,CURRENT_TIMESTAMP(),%s,PARSE_JSON(%s)""",
                    (version, model, expiry, json.dumps(report)),
                )
                connection.commit()
                return report
            except Exception:
                # A failed evaluation/registration must not leave an untracked model
                # holding learned information beyond retention.
                if created_model:
                    try:
                        cursor.execute(f"DROP SNOWFLAKE.ML.CLASSIFICATION IF EXISTS {model}")
                    except Exception:  # noqa: BLE001 - preserve original training failure.
                        logging.getLogger(__name__).error("snowflake_failed_model_drop_failed")
                raise
            finally:
                cursor.close()

    def _evaluate_rows(self, cursor, model, train, test):
        baseline = max(("helpful", "unhelpful"), key=lambda label: sum(row[-1] == label for row in train))
        correct = baseline_correct = 0
        slices = {}
        confusion = {
            label: {predicted: 0 for predicted in ("helpful", "unhelpful")}
            for label in ("helpful", "unhelpful")
        }
        for row in test:
            cursor.execute(
                f"SELECT {model}!PREDICT(INPUT_DATA=>PARSE_JSON(%s))",
                (json.dumps(dict(zip((key.upper() for key in FEATURE_KEYS), row[3:-1]))),),
            )
            result = cursor.fetchone()[0]
            result = json.loads(result) if isinstance(result, str) else result
            predicted = result["class"]
            if predicted not in confusion:
                raise _ValidationError("Classifier returned invalid held-out prediction")
            correct += predicted == row[-1]
            baseline_correct += baseline == row[-1]
            confusion[row[-1]][predicted] += 1
            category = row[3]
            slice_count, slice_correct = slices.get(category, (0, 0))
            slices[category] = (slice_count + 1, slice_correct + (predicted == row[-1]))
        cursor.execute(f"CALL {model}!SHOW_EVALUATION_METRICS()")
        # Snowflake's native random split is supplementary; publish the explicit
        # grouped temporal held-out evaluation as the primary result.
        native = [[str(value) for value in row] for row in cursor.fetchall()]
        per_class = {}
        for label, actual_predictions in confusion.items():
            true_positive = actual_predictions[label]
            predicted_count = sum(confusion[actual][label] for actual in confusion)
            actual_count = sum(actual_predictions.values())
            per_class[label] = {
                "precision": true_positive / predicted_count if predicted_count else None,
                "recall": true_positive / actual_count if actual_count else None,
                "support": actual_count,
            }
        proportion = correct / len(test)
        z = 1.96
        denominator = 1 + z * z / len(test)
        center = (proportion + z * z / (2 * len(test))) / denominator
        margin = (
            z
            * math.sqrt(proportion * (1 - proportion) / len(test) + z * z / (4 * len(test) ** 2))
            / denominator
        )
        return {
            "held_out_accuracy": proportion,
            "accuracy_95pct_wilson_interval": [center - margin, center + margin],
            "slice_metrics": {
                category: {"support": count, "accuracy": successes / count}
                for category, (count, successes) in slices.items()
            },
            "baseline_accuracy": baseline_correct / len(test),
            "baseline_label": baseline,
            "confusion_matrix": confusion,
            "per_class": per_class,
            "snowflake_random_split_metrics": native,
            "promotion": "requires_review",
        }

    async def evaluate(self, version: str) -> dict[str, Any] | None:
        version = _identifier(version)
        return await asyncio.to_thread(self._evaluation_report, version)

    def _evaluation_report(self, version):
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"""SELECT REPORT FROM {self.prefix}_MODELS WHERE VERSION=%s
                    AND EXPIRES_AT>CURRENT_TIMESTAMP() ORDER BY CREATED_AT DESC LIMIT 1""",
                    (version,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return json.loads(row[0]) if isinstance(row[0], str) else row[0]
            finally:
                cursor.close()


async def _main() -> int:
    """Executable operations; credentials come exclusively from backend env."""
    import argparse
    from pathlib import Path

    from dotenv import load_dotenv

    from ..config import Config
    from ..db import PostgresRepository

    parser = argparse.ArgumentParser(description="Prompt Enhance Snowflake operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("export")
    commands.add_parser("cleanup")
    train_parser = commands.add_parser("train")
    train_parser.add_argument("--version", required=True)
    train_parser.add_argument("--task-groups", required=True, type=Path)
    train_parser.add_argument("--label-definition", required=True, choices=["user_reported_helpfulness"])
    train_parser.add_argument("--minimum-per-class", type=int, default=20)
    evaluation_parser = commands.add_parser("evaluate")
    evaluation_parser.add_argument("--version", required=True)
    prediction_parser = commands.add_parser("predict")
    prediction_parser.add_argument("--features", required=True, type=Path)
    args = parser.parse_args()
    load_dotenv(Path.cwd() / ".env", override=False)
    config = Config.from_env()
    classifier = SnowflakeClassifier(
        config.snowflake_connection(), model_version=config.snowflake_model_version
    )
    try:
        if args.command == "status":
            result = {"configured": classifier.configured, "status": await classifier.status()}
        elif args.command == "export":
            if not config.database_url:
                raise _ValidationError("DATABASE_URL is required")
            repository = PostgresRepository(
                config.database_url,
                embedding_model=config.embedding_model,
                embedding_dimensions=config.embedding_dimensions,
                auto_migrate=False,
            )
            await repository.open()
            total, cursor = 0, None
            try:
                while True:
                    page = await repository.export_outcomes(limit=500, cursor=cursor)
                    total += await classifier.export(page.items)
                    if page.next_cursor is None:
                        break
                    cursor = page.next_cursor
            finally:
                await repository.close()
            result = {"processed_events": total}
        elif args.command == "cleanup":
            result = {"purged_records": await classifier.cleanup()}
        elif args.command == "train":
            plan = TrainingPlan(
                args.version,
                json.loads(args.task_groups.read_text()),
                args.label_definition,
                args.minimum_per_class,
            )
            result = await classifier.train(plan)
        elif args.command == "evaluate":
            result = await classifier.evaluate(args.version)
        else:
            result = asdict(await classifier.predict(json.loads(args.features.read_text())))
        print(json.dumps(result, default=str))
        return 0
    except (SnowflakeUnavailable, ClassifierColdStart, ValueError) as error:
        # Validation messages are fixed strings, never provider/SQL/input payloads.
        print(json.dumps({"error": type(error).__name__, "message": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
