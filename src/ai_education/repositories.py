"""In-memory reference repositories with version and idempotency guarantees."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_education.core.errors import DataConflictError
from ai_education.domain.enums import PlanStatus
from ai_education.domain.models import (
    KnowledgeProfile,
    LearningPlan,
    OnboardingSession,
    StudentAcademicProfile,
    TimeProfile,
)


class PlannerRepository:
    """Reference storage adapter; replaceable by a transactional database adapter."""

    def __init__(self) -> None:
        self.students: dict[str, StudentAcademicProfile] = {}
        self.knowledge_profiles: dict[str, KnowledgeProfile] = {}
        self.time_profiles: dict[str, TimeProfile] = {}
        self.plans: dict[str, list[LearningPlan]] = {}
        self.onboarding: dict[str, OnboardingSession] = {}
        self.idempotency_results: dict[str, dict[str, Any]] = {}
        self.processed_event_ids: set[str] = set()

    def save_student(self, profile: StudentAcademicProfile) -> StudentAcademicProfile:
        current = self.students.get(profile.student_id)
        if current and profile.profile_version < current.profile_version:
            raise DataConflictError("学生画像版本落后于当前版本")
        self.students[profile.student_id] = deepcopy(profile)
        return deepcopy(profile)

    def save_knowledge_profile(self, profile: KnowledgeProfile) -> KnowledgeProfile:
        self.knowledge_profiles[profile.student_id] = deepcopy(profile)
        return deepcopy(profile)

    def save_time_profile(self, profile: TimeProfile) -> TimeProfile:
        self.time_profiles[profile.student_id] = deepcopy(profile)
        return deepcopy(profile)

    def save_plan(self, plan: LearningPlan) -> LearningPlan:
        versions = self.plans.setdefault(plan.plan_id, [])
        if versions and plan.version <= versions[-1].version:
            raise DataConflictError(
                "计划更新必须创建更高版本",
                details={"current_version": versions[-1].version, "incoming": plan.version},
            )
        versions.append(deepcopy(plan))
        return deepcopy(plan)

    def get_plan(self, plan_id: str, version: int | None = None) -> LearningPlan | None:
        versions = self.plans.get(plan_id, [])
        if not versions:
            return None
        if version is None:
            return deepcopy(versions[-1])
        return next((deepcopy(item) for item in versions if item.version == version), None)

    def active_plan_for_student(self, student_id: str) -> LearningPlan | None:
        candidates = [
            versions[-1]
            for versions in self.plans.values()
            if versions
            and versions[-1].student_id == student_id
            and versions[-1].status in {PlanStatus.ACTIVE, PlanStatus.WAITING_FOR_CONFIRMATION}
        ]
        return deepcopy(max(candidates, key=lambda item: item.created_at)) if candidates else None

    def save_onboarding(self, session: OnboardingSession) -> OnboardingSession:
        self.onboarding[session.onboarding_id] = deepcopy(session)
        return deepcopy(session)

    def get_onboarding(self, onboarding_id: str) -> OnboardingSession | None:
        session = self.onboarding.get(onboarding_id)
        return deepcopy(session) if session else None

    def get_idempotent(self, key: str | None) -> dict[str, Any] | None:
        return deepcopy(self.idempotency_results.get(key)) if key else None

    def put_idempotent(self, key: str | None, result: dict[str, Any]) -> None:
        if key:
            self.idempotency_results[key] = deepcopy(result)
