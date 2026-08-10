"""Context assembly for the conversational career mentor."""

from __future__ import annotations

from typing import Any

from ai_education.llm.career_education import (
    GeneratedCareerReply,
    StructuredCareerMentorGenerator,
)
from ai_education.programming_learning_repository import ProgrammingLearningRepository


async def generate_contextual_career_reply(
    *,
    generator: StructuredCareerMentorGenerator,
    repository: ProgrammingLearningRepository,
    student_id: str,
    job: dict[str, Any],
    profile: dict[str, Any],
    skills: list[dict[str, Any]],
    user_message: str,
) -> tuple[GeneratedCareerReply | None, int]:
    dialogue_records = repository.list_records(
        student_id, record_type="v1_career_dialogue", limit=8
    )
    conversation_history = [
        {
            "student": item["payload"].get("user_message", ""),
            "mentor": item["payload"].get("answer", ""),
        }
        for item in reversed(dialogue_records)
    ]
    recent_activity = [
        {
            "type": item["record_type"],
            "status": item["status"],
            "title": item["payload"].get("title")
            or item["payload"].get("question_title")
            or "学习记录",
        }
        for item in repository.list_records(student_id, limit=12)
        if item["record_type"] in {"v1_project_session", "v1_coding_submission"}
    ][:6]
    if not generator.available:
        return None, len(conversation_history)
    try:
        generated = await generator.generate(
            {
                "target_job": {
                    "job_id": job["job_id"],
                    "name": job["name"],
                    "description": job["description"],
                },
                "learner_profile": {
                    "identity": profile["identity"],
                    "education_stage": profile["education_stage"],
                    "programming_level": profile["programming_level"],
                    "known_languages": profile["known_languages"],
                    "weekly_hours": profile["weekly_hours"],
                    "learning_goal": profile["learning_goal"],
                    "target_period_weeks": profile["target_period_weeks"],
                },
                "skill_evidence": [
                    {
                        "skill_id": item["skill_id"],
                        "name": item["name"],
                        "mastery": item["mastery"],
                        "evidence_count": item["evidence_count"],
                    }
                    for item in skills
                ],
                "recent_activity": recent_activity,
                "conversation_history": conversation_history,
                "user_message": user_message,
            }
        )
    except Exception:
        return None, len(conversation_history)
    return generated, len(conversation_history)
