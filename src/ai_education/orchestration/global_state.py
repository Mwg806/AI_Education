"""Versioned global-state adapter supporting optimistic synchronization."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_education.core.errors import DataConflictError


class GlobalStateStore:
    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._revisions: dict[str, int] = {}

    def read(self, student_id: str) -> tuple[int, dict[str, Any]]:
        return self._revisions.get(student_id, 0), deepcopy(self._states.get(student_id, {}))

    def compare_and_swap(
        self,
        student_id: str,
        *,
        expected_revision: int,
        updates: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        current_revision = self._revisions.get(student_id, 0)
        if current_revision != expected_revision:
            raise DataConflictError(
                "全局状态版本冲突",
                details={
                    "expected_revision": expected_revision,
                    "current_revision": current_revision,
                },
            )
        state = deepcopy(self._states.get(student_id, {}))
        self._deep_merge(state, updates)
        next_revision = current_revision + 1
        self._states[student_id] = state
        self._revisions[student_id] = next_revision
        return next_revision, deepcopy(state)

    def _deep_merge(self, target: dict[str, Any], updates: dict[str, Any]) -> None:
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = deepcopy(value)
