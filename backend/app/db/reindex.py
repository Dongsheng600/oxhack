"""Explicit same-dimension embedding profile backfill and atomic activation.

Usage: python -m app.db.reindex --model MODEL --vectors vectors.json [--activate]
Vectors are generated externally with the exact target model and indexed by tag
name; this command never invents vectors or silently changes model dimensions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from ..ports import EmbeddingProfileMismatch
from .common import canonical_tag, vector_literal


async def reindex(repository, *, model: str, vectors: dict[str, list[float]], activate=False) -> str:
    prepared = {
        canonical_tag(tag): vector_literal(vector, repository.embedding_dimensions)
        for tag, vector in vectors.items()
    }
    async with repository.pool.connection() as connection:  # noqa: SIM117 - explicit activation transaction.
        async with connection.transaction():
            await connection.execute("SELECT pg_advisory_xact_lock(734276183)")
            row = await (
                await connection.execute(
                    """INSERT INTO embedding_profiles(id,model,dimensions,metric,active)
                VALUES(%s,%s,%s,'cosine',false) ON CONFLICT(model,dimensions,normalization_version)
                DO UPDATE SET model=EXCLUDED.model RETURNING id,active""",
                    (uuid4(), model, repository.embedding_dimensions),
                )
            ).fetchone()
            if row["active"]:
                raise EmbeddingProfileMismatch(
                    "Target profile is already active; choose a new versioned model"
                )
            profile_id = row["id"]
            # FOR UPDATE waits for all in-flight saves/retrievals to complete; each
            # pins its profile with FOR SHARE for its entire transaction.
            if activate:
                await connection.execute("SELECT id FROM embedding_profiles WHERE active FOR UPDATE")
            tags = await (
                await connection.execute("SELECT id,canonical_name FROM tags ORDER BY canonical_name")
            ).fetchall()
            for tag in tags:
                if tag["canonical_name"] in prepared:
                    await connection.execute(
                        """INSERT INTO tag_embeddings(tag_id,profile_id,embedding) VALUES(%s,%s,%s::vector)
                        ON CONFLICT(tag_id,profile_id) DO UPDATE SET embedding=EXCLUDED.embedding""",
                        (tag["id"], profile_id, prepared[tag["canonical_name"]]),
                    )
            if activate:
                missing = await (
                    await connection.execute(
                        """SELECT count(*) AS count FROM tags t
                    WHERE EXISTS(SELECT 1 FROM knowledge_tags kt WHERE kt.tag_id=t.id)
                    AND NOT EXISTS(SELECT 1 FROM tag_embeddings te WHERE te.tag_id=t.id AND te.profile_id=%s)""",
                        (profile_id,),
                    )
                ).fetchone()
                if missing["count"]:
                    raise EmbeddingProfileMismatch(
                        "Target profile is incomplete; backfill every linked tag before activation"
                    )
                await connection.execute("UPDATE embedding_profiles SET active=false WHERE active")
                await connection.execute(
                    "UPDATE embedding_profiles SET active=true WHERE id=%s", (profile_id,)
                )
            return str(profile_id)


async def main():
    from dotenv import load_dotenv

    from .repository import PostgresRepository

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--vectors", required=True, type=Path)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    load_dotenv(Path.cwd() / ".env", override=False)
    repository = PostgresRepository(
        os.environ["DATABASE_URL"],
        embedding_model=os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        embedding_dimensions=int(os.environ.get("EMBEDDING_DIMENSIONS", "768")),
        auto_migrate=False,
    )
    await repository.open()
    try:
        identifier = await reindex(
            repository, model=args.model, vectors=json.loads(args.vectors.read_text()), activate=args.activate
        )
        print(json.dumps({"profile_id": identifier, "active": args.activate}))
    finally:
        await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
