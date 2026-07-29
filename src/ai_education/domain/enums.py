"""Stable enums shared across protocols, graphs, services and API."""

from __future__ import annotations

from enum import StrEnum


class AgentLifecycleStatus(StrEnum):
    NEW = "NEW"
    ONBOARDING = "ONBOARDING"
    GOAL_COLLECTING = "GOAL_COLLECTING"
    GOAL_READY = "GOAL_READY"
    ASSESSMENT_PENDING = "ASSESSMENT_PENDING"
    KNOWLEDGE_PROFILE_READY = "KNOWLEDGE_PROFILE_READY"
    TIME_PROFILE_READY = "TIME_PROFILE_READY"
    PLAN_GENERATING = "PLAN_GENERATING"
    PLAN_DRAFT = "PLAN_DRAFT"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    PLAN_ACTIVE = "PLAN_ACTIVE"
    PLAN_ADJUST_PENDING = "PLAN_ADJUST_PENDING"
    STAGE_COMPLETED = "STAGE_COMPLETED"
    PLAN_COMPLETED = "PLAN_COMPLETED"
    PAUSED = "PAUSED"
    WAITING_FOR_DATA = "WAITING_FOR_DATA"
    DATA_CONFLICT_PENDING = "DATA_CONFLICT_PENDING"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    FAILED = "FAILED"


class StandardStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    NEED_MORE_INFORMATION = "need_more_information"
    CONFLICT = "conflict"
    FAILED = "failed"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class AgentRole(StrEnum):
    PERSONALIZED_LEARNING_PLANNER = "personalized_learning_planner"
    TEACHING_EXPLAINER = "teaching_explainer"
    QUESTION_GENERATOR = "question_generator"
    ASSESSMENT_GRADER = "assessment_grader"
    LEARNING_COMPANION = "learning_companion"
    CAREER_PLANNER = "career_planner"
    TEACHER_ASSISTANT = "teacher_assistant"
    CONTENT_SAFETY = "content_safety"


class MessageType(StrEnum):
    COMMAND = "command"
    QUERY = "query"
    EVENT = "event"
    RESULT = "result"
    ERROR = "error"


class ActorType(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    GUARDIAN = "guardian"
    ADMIN = "admin"
    AGENT = "agent"
    SYSTEM = "system"


class Subject(StrEnum):
    CHINESE = "chinese"
    MATHEMATICS = "mathematics"
    FOREIGN_LANGUAGE = "foreign_language"
    PHYSICS = "physics"
    HISTORY = "history"
    IDEOLOGY_POLITICS = "ideology_politics"
    GEOGRAPHY = "geography"
    CHEMISTRY = "chemistry"
    BIOLOGY = "biology"


class Grade(StrEnum):
    GRADE_10 = "grade_10"
    GRADE_11 = "grade_11"
    GRADE_12 = "grade_12"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    PAUSED = "paused"
    COMPLETED = "completed"


class AdjustmentLevel(StrEnum):
    TASK_SWAP = "task_swap"
    DAILY_SHIFT = "daily_shift"
    WEEKLY_REPLAN = "weekly_replan"
    STAGE_REPLAN = "stage_replan"
    FULL_REPLAN = "full_replan"
