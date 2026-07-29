"""Deterministic aggregation of multiple agent results."""

from __future__ import annotations

from ai_education.domain.enums import StandardStatus
from ai_education.domain.protocols import AgentResponse, ErrorDetail, Evidence, WarningDetail


class ResultAggregator:
    def aggregate(
        self,
        results: dict[str, AgentResponse],
    ) -> tuple[StandardStatus, dict, list[Evidence], list[WarningDetail], list[ErrorDetail]]:
        statuses = [response.status for response in results.values()]
        if statuses and all(status == StandardStatus.SUCCESS for status in statuses):
            status = StandardStatus.SUCCESS
        elif any(status == StandardStatus.MANUAL_REVIEW_REQUIRED for status in statuses):
            status = StandardStatus.MANUAL_REVIEW_REQUIRED
        elif any(status == StandardStatus.NEED_MORE_INFORMATION for status in statuses):
            status = StandardStatus.NEED_MORE_INFORMATION
        elif any(status == StandardStatus.SUCCESS for status in statuses):
            status = StandardStatus.PARTIAL_SUCCESS
        elif any(status == StandardStatus.CONFLICT for status in statuses):
            status = StandardStatus.CONFLICT
        else:
            status = StandardStatus.FAILED

        evidence_by_source: dict[tuple[str, str], Evidence] = {}
        warnings: list[WarningDetail] = []
        errors: list[ErrorDetail] = []
        agent_results: dict[str, dict] = {}
        for task_id, response in results.items():
            agent_results[task_id] = {
                "agent_role": response.agent_role,
                "status": response.status,
                "result": response.result,
                "data_version": response.data_version,
            }
            for item in response.evidence:
                evidence_by_source[(item.source_type, item.source_id)] = item
            warnings.extend(response.warnings)
            errors.extend(response.errors)
        return (
            status,
            {"agent_results": agent_results},
            list(evidence_by_source.values()),
            warnings,
            errors,
        )
