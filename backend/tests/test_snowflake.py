from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.integrations.snowflake import (
    ClassifierColdStart,
    SnowflakeClassifier,
    SnowflakeUnavailable,
    TrainingPlan,
)

pytestmark = pytest.mark.asyncio


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.batches = []
        self.rowcount = 2
        self.rows = []
        self.registered = False
        self.labels = []
        self.permanent_tables = False

    def execute(self, sql, parameters=None):
        self.calls.append((sql, parameters))
        if "FROM INFORMATION_SCHEMA.TABLES" in sql:
            self.rows = [(int(self.permanent_tables),)]
        elif sql == "SELECT 1":
            self.rows = [(1,)]
        elif "SELECT OBJECT_NAME" in sql and "EXPIRES_AT<=" in sql:
            self.rows = [("PROMPT_ENHANCE_MODEL_OLD",)]
        elif "SELECT OBJECT_NAME" in sql:
            self.rows = [("PROMPT_ENHANCE_MODEL_V1",)] if self.registered else []
        elif "SELECT VERSION" in sql:
            self.rows = [("V1",)] if self.registered else []
        elif "SELECT REQUEST_ID,TIMESTAMP" in sql:
            self.rows = self.labels
        elif "!PREDICT" in sql:
            self.rows = [
                (json.dumps({"class": "helpful", "probability": {"helpful": 0.8, "unhelpful": 0.2}}),)
            ]
        elif "SHOW_EVALUATION_METRICS" in sql:
            self.rows = [("test", "helpful", "precision", 0.8)]
        elif "SELECT REPORT" in sql:
            self.rows = []
        return self

    def executemany(self, sql, rows):
        self.batches.append((sql, list(rows)))
        return self

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.current = FakeCursor()
        self.closed = False
        self.committed = False

    def cursor(self):
        return self.current

    def close(self):
        self.closed = True

    def commit(self):
        self.committed = True


def features():
    return {
        "task_type": "coding",
        "missing_constraints_count": 1,
        "candidate_count": 2,
        "relevant_count": 1,
        "best_retrieval_score": 0.8,
        "enhancement_type": "multiple_choice",
        "model_version": "gemini-test",
    }


def exported_event(**updates):
    now = datetime.now(UTC)
    return dict(
        event_id="event-1",
        request_id="request-1",
        event_type="observed",
        observed_result="helpful",
        timestamp=now,
        expires_at=now + timedelta(days=30),
        feature_schema=1,
        features=features(),
        **updates,
    )


async def test_unconfigured_and_untrained_classifier_are_honest_baseline():
    adapter = SnowflakeClassifier()
    assert not adapter.configured
    assert await adapter.status() == "not_configured"
    assert (await adapter.predict(features())).source == "baseline"
    assert await adapter.cleanup() == 0
    connection = FakeConnection()
    configured = SnowflakeClassifier(connection_factory=lambda **kwargs: connection)
    assert await configured.status() == "ready"
    assert (await configured.predict(features())).source == "baseline"
    assert connection.closed


async def test_export_is_merge_bound_feature_only_and_ignores_expired():
    connection = FakeConnection()
    adapter = SnowflakeClassifier(connection_factory=lambda **kwargs: connection)
    event = exported_event()
    event["features"]["prompt"] = "RAW_PROMPT_SENTINEL"
    event["content"] = "RAW_KNOWLEDGE_SENTINEL"
    expired = exported_event()
    expired["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    assert await adapter.export([event, expired]) == 1
    sql, rows = connection.current.batches[0]
    assert "MERGE INTO" in sql and "ON t.EVENT_ID=s.EVENT_ID" in sql
    assert rows[0][0] == "event-1"
    assert "RAW_PROMPT_SENTINEL" not in repr(connection.current.calls) + repr(rows)
    assert "RAW_KNOWLEDGE_SENTINEL" not in repr(rows)
    assert any(
        "TRANSIENT TABLE" in sql and "DATA_RETENTION_TIME_IN_DAYS=0" in sql
        for sql, _ in connection.current.calls
    )
    assert connection.committed


async def test_acceptance_cannot_be_a_quality_label_or_arbitrary_feature_text():
    connection = FakeConnection()
    adapter = SnowflakeClassifier(connection_factory=lambda **kwargs: connection)
    event = exported_event()
    event["event_type"] = "accepted"
    with pytest.raises(ValueError):
        await adapter.export([event])
    event = exported_event()
    event["features"]["task_type"] = "raw prompt paragraph"
    with pytest.raises(ValueError):
        await adapter.export([event])
    assert not connection.current.calls


async def test_prediction_uses_only_live_registered_model_and_derived_features():
    connection = FakeConnection()
    adapter = SnowflakeClassifier(connection_factory=lambda **kwargs: connection, model_version="v1")
    assert (await adapter.predict(features())).source == "baseline"
    assert await adapter.active_model_version() is None
    connection.current.registered = True
    assert await adapter.active_model_version() == "V1"
    result = await adapter.predict(features())
    assert result.source == "snowflake" and result.predicted_class == "helpful"
    prediction_call = next((sql, params) for sql, params in connection.current.calls if "!PREDICT" in sql)
    assert "PARSE_JSON(%s)" in prediction_call[0]
    assert json.loads(prediction_call[1][0])["TASK_TYPE"] == "coding"
    assert any("EXPIRES_AT>CURRENT_TIMESTAMP()" in sql for sql, _ in connection.current.calls)


async def test_cleanup_drops_expired_models_and_events():
    connection = FakeConnection()
    adapter = SnowflakeClassifier(connection_factory=lambda **kwargs: connection)
    assert await adapter.cleanup() == 4
    assert any(
        "DROP SNOWFLAKE.ML.CLASSIFICATION IF EXISTS PROMPT_ENHANCE_MODEL_OLD" in sql
        for sql, _ in connection.current.calls
    )
    assert any(
        "DELETE FROM PROMPT_ENHANCE_EVENTS WHERE EXPIRES_AT<=" in sql for sql, _ in connection.current.calls
    )


async def test_training_requires_target_groups_and_sufficient_actual_labels():
    connection = FakeConnection()
    adapter = SnowflakeClassifier(connection_factory=lambda **kwargs: connection)
    with pytest.raises(ValueError):
        await adapter.train(TrainingPlan("v1", {}, "acceptance"))
    with pytest.raises(ClassifierColdStart):
        await adapter.train(TrainingPlan("v1", {}, "user_reported_helpfulness"))
    assert not any("CREATE SNOWFLAKE.ML.CLASSIFICATION" in sql for sql, _ in connection.current.calls)


async def test_real_training_sql_heldout_and_expiring_registry_contract():
    connection = FakeConnection()
    now = datetime.now(UTC)
    rows = []
    groups = {}
    for index in range(50):
        identifier = "request-" + str(index)
        groups[identifier] = "task-" + str(index // 2)
        rows.append(
            (
                identifier,
                now - timedelta(hours=50 - index),
                now + timedelta(days=20),
                *features().values(),
                "helpful" if index % 2 else "unhelpful",
            )
        )
    connection.current.labels = rows
    adapter = SnowflakeClassifier(connection_factory=lambda **kwargs: connection)
    report = await adapter.train(TrainingPlan("v1", groups, "user_reported_helpfulness"))
    assert report["train_rows"] + report["test_rows"] == 50
    assert report["target"] == "user_reported_helpfulness"
    assert report["promotion"] == "requires_review"
    assert report["baseline_accuracy"] == 0.5
    assert any("SYSTEM$REFERENCE" in sql for sql, _ in connection.current.calls)
    assert any("INSERT INTO PROMPT_ENHANCE_MODELS" in sql for sql, _ in connection.current.calls)
    training_rows = connection.current.batches[0][1]
    assert all(len(row) == 8 for row in training_rows)
    assert adapter.model_version is None


async def test_driver_error_sanitized():
    def broken(**kwargs):
        raise RuntimeError("SECRET raw provider detail")

    adapter = SnowflakeClassifier(connection_factory=broken)
    assert await adapter.status() == "unavailable"
    with pytest.raises(SnowflakeUnavailable, match="Snowflake operation failed") as captured:
        await adapter.export([exported_event()])
    assert "SECRET" not in str(captured.value)


async def test_live_snowflake_connection_opt_in():
    import os

    if os.environ.get("SNOWFLAKE_LIVE") != "1":
        pytest.skip("Set SNOWFLAKE_LIVE=1 with real backend credentials for live Snowflake readiness")
    from app.config import Config

    configuration = Config.from_env().snowflake_connection()
    assert configuration, "Live Snowflake test requires backend environment credentials"
    adapter = SnowflakeClassifier(configuration)
    assert await adapter.status() == "ready"


async def test_existing_permanent_export_table_cannot_extend_retention():
    connection = FakeConnection()
    connection.current.permanent_tables = True
    adapter = SnowflakeClassifier(connection_factory=lambda **kwargs: connection)
    with pytest.raises(ValueError, match="must be transient"):
        await adapter.export([exported_event()])
    assert not connection.current.batches
