#!/usr/bin/env python3
"""Replay pending learning-event outbox records into versioned student profiles."""

from __future__ import annotations

import argparse
import asyncio

from ai_education.config import Settings
from ai_education.mysql_persistence import MySQLPersistence
from ai_education.services.shared.learning_event_service import LearningEventService
from ai_education.services.shared.student_profile_service import StudentProfileService
from ai_education.shared_learning_repository import SharedLearningRepository


async def replay(limit: int, *, apply: bool) -> int:
    settings = Settings.from_env()
    if not settings.mysql_enabled:
        raise SystemExit("AI_EDUCATION_MYSQL_ENABLED 未开启")
    repository = SharedLearningRepository(MySQLPersistence(settings))
    pending = repository.list_pending_event_outbox(limit)
    if not apply:
        print(
            {
                "mode": "dry-run",
                "pending": len(pending),
                "event_ids": [r["event_id"] for r in pending],
            }
        )
        return 0
    service = LearningEventService(repository, StudentProfileService(repository))
    print(await service.replay_pending_outbox(limit))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return asyncio.run(replay(max(1, min(args.limit, 500)), apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
