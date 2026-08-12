"""Searchable, source-traceable index over the curated nine-subject lesson collection."""

from __future__ import annotations

import csv
import hashlib
import re
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader

from ai_education.core.errors import InputValidationError
from ai_education.domain.enums import Subject
from ai_education.domain.teacher_preparation import TeachingResourceReference

DEFAULT_TEACHING_RESOURCE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "Knowledge"
    / "teacher"
    / "高中九科优秀教案汇编_v3_化学生物政治升级版"
)

SUBJECT_NAME_MAP = {
    "语文": Subject.CHINESE,
    "数学": Subject.MATHEMATICS,
    "英语": Subject.FOREIGN_LANGUAGE,
    "物理": Subject.PHYSICS,
    "化学": Subject.CHEMISTRY,
    "生物": Subject.BIOLOGY,
    "思想政治": Subject.IDEOLOGY_POLITICS,
    "历史": Subject.HISTORY,
    "地理": Subject.GEOGRAPHY,
}


class TeachingKnowledgeBase:
    """Small deterministic retrieval layer for 27 curated teaching PDFs."""

    def __init__(self, root: Path = DEFAULT_TEACHING_RESOURCE_ROOT) -> None:
        self.root = root
        self._records = self._load_catalog()
        self._checksums = self._load_checksums()

    @property
    def available(self) -> bool:
        return len(self._records) == 27 and all(
            (self.root / item["relative_path"]).is_file() for item in self._records
        )

    def _load_catalog(self) -> list[dict]:
        catalog = self.root / "00_教案总目录与来源.csv"
        if not catalog.is_file():
            raise InputValidationError("教师优秀教案目录不存在")
        with catalog.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        records: list[dict] = []
        for row in rows:
            subject = SUBJECT_NAME_MAP.get((row.get("学科") or "").strip())
            if subject is None:
                continue
            records.append(
                {
                    "subject": subject,
                    "title": (row.get("文件名") or "").removesuffix(".pdf"),
                    "page_count": int(row.get("页数") or 1),
                    "material_type": (row.get("材料类型") or "来源待核验").strip(),
                    "source_organization": (row.get("来源机构/文献") or "来源待核验").strip(),
                    "source_location": (row.get("来源定位") or "来源待核验").strip(),
                    "source_url": (row.get("原始来源链接") or "").strip(),
                    "relative_path": (row.get("相对路径") or "").strip(),
                }
            )
        return records

    def _load_checksums(self) -> dict[str, str]:
        manifest = self.root / "00_SHA256校验.txt"
        if not manifest.is_file():
            return {}
        checksums: dict[str, str] = {}
        for line in manifest.read_text(encoding="utf-8").splitlines():
            digest, separator, relative_path = line.partition("  ")
            if separator and re.fullmatch(r"[0-9a-f]{64}", digest):
                checksums[relative_path.strip()] = digest
        return checksums

    def catalog(self) -> dict:
        subjects = []
        for subject in SUBJECT_NAME_MAP.values():
            resources = [item for item in self._records if item["subject"] == subject]
            subjects.append(
                {
                    "subject": subject.value,
                    "resource_count": len(resources),
                    "resources": [
                        {
                            "title": item["title"],
                            "page_count": item["page_count"],
                            "material_type": item["material_type"],
                            "source_organization": item["source_organization"],
                        }
                        for item in resources
                    ],
                }
            )
        return {
            "status": "ready" if self.available else "incomplete",
            "resource_count": len(self._records),
            "subject_count": len([item for item in subjects if item["resource_count"]]),
            "subjects": subjects,
            "source_policy": "teaching_reference_with_attribution",
        }

    def search(
        self,
        query: str,
        *,
        subject: Subject,
        limit: int = 3,
    ) -> list[TeachingResourceReference]:
        clean_query = query.strip()
        if not clean_query:
            raise InputValidationError("教案检索词不能为空")
        candidates = [item for item in self._records if item["subject"] == subject]
        if not candidates:
            raise InputValidationError(f"优秀教案库暂不支持学科：{subject.value}")
        tokens = self._query_tokens(clean_query)
        ranked = sorted(
            candidates,
            key=lambda item: (
                self._score(item, clean_query, tokens),
                -item["page_count"],
                item["title"],
            ),
            reverse=True,
        )
        results: list[TeachingResourceReference] = []
        for item in ranked[: max(1, min(limit, 6))]:
            relative_path = item["relative_path"]
            digest = self._checksums.get(relative_path, "")
            material_type = item["material_type"]
            results.append(
                TeachingResourceReference(
                    resource_id=(
                        "teaching_ref_"
                        f"{(digest or hashlib.sha256(relative_path.encode()).hexdigest())[:14]}"
                    ),
                    subject=subject,
                    title=item["title"],
                    material_type=material_type,
                    source_organization=item["source_organization"],
                    source_location=item["source_location"],
                    source_url=item["source_url"],
                    relative_path=relative_path,
                    page_count=item["page_count"],
                    excerpt=self._relevant_excerpt(relative_path, tokens),
                    copyright_status=(
                        "original_optimized_reference"
                        if "原创优化" in material_type
                        else "public_teaching_reference"
                    ),
                    checksum_verified=self._checksum_verified(relative_path),
                )
            )
        return results

    @staticmethod
    def _query_tokens(query: str) -> list[str]:
        parts = [
            item.lower()
            for item in re.split(r"[\s,，。；;：:、/（）()\[\]-]+", query)
            if len(item.strip()) >= 2
        ]
        compact = re.sub(r"\s+", "", query.lower())
        bigrams = [compact[index : index + 2] for index in range(max(0, len(compact) - 1))]
        return list(dict.fromkeys([*parts, *bigrams]))[:30]

    @staticmethod
    def _score(item: dict, query: str, tokens: list[str]) -> int:
        title = item["title"].lower()
        haystack = " ".join(
            [
                title,
                item["material_type"].lower(),
                item["source_location"].lower(),
                item["source_organization"].lower(),
            ]
        )
        score = 20 if query.lower() in title else 0
        score += sum(5 for token in tokens if token in title)
        score += sum(1 for token in tokens if token in haystack)
        return score

    @lru_cache(maxsize=64)  # noqa: B019 - singleton service has process lifetime
    def _extract_text(self, relative_path: str) -> str:
        path = (self.root / relative_path).resolve()
        if self.root.resolve() not in path.parents or not path.is_file():
            raise InputValidationError("教案资源路径无效")
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return re.sub(r"[ \t]+", " ", text).strip()

    def _relevant_excerpt(self, relative_path: str, tokens: list[str]) -> str:
        text = self._extract_text(relative_path)
        lower = text.lower()
        positions = [lower.find(token) for token in tokens if lower.find(token) >= 0]
        start = max(0, min(positions) - 500) if positions else 0
        return text[start : start + 5_500]

    @lru_cache(maxsize=64)  # noqa: B019 - singleton service has process lifetime
    def _checksum_verified(self, relative_path: str) -> bool:
        expected = self._checksums.get(relative_path)
        if not expected:
            return False
        path = self.root / relative_path
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return digest == expected

    def verify_integrity(self) -> dict:
        failures = [
            item["relative_path"]
            for item in self._records
            if not self._checksum_verified(item["relative_path"])
        ]
        return {
            "valid": not failures and len(self._records) == 27,
            "resource_count": len(self._records),
            "verified_count": len(self._records) - len(failures),
            "failures": failures,
        }
