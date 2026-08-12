#!/usr/bin/env python3
"""Offline deterministic routing evaluation; no model or network required."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

from ai_education.config import PROJECT_ROOT, Settings
from ai_education.domain.multi_agent import UnifiedStudentProfile
from ai_education.orchestration.intent_router import IntentRouter
from ai_education.services.shared.model_router import ModelRouter


async def main() -> int:
    settings = replace(Settings.from_env(), llm_enabled=False, llm_model="")
    router = IntentRouter(ModelRouter(settings))
    cases = [
        json.loads(line)
        for line in (PROJECT_ROOT / "evals" / "orchestration_routing_v1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    passed = 0
    failures = []
    for case in cases:
        decision = await router.route(
            case["message"],
            UnifiedStudentProfile(user_id=f"eval_{case['id']}"),
            {"actor_type": case.get("actor_type", "student")},
        )
        actual_agents = [item.value for item in decision.required_agents]
        ok = actual_agents == case["agents"] and decision.execution_mode == case["mode"]
        passed += int(ok)
        if not ok:
            failures.append(
                {
                    "id": case["id"],
                    "expected": [case["agents"], case["mode"]],
                    "actual": [actual_agents, decision.execution_mode],
                }
            )
    print(
        json.dumps(
            {"passed": passed, "total": len(cases), "failures": failures}, ensure_ascii=False
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
