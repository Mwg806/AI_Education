"""Safe in-memory extraction for English reading materials."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from ai_education.core.errors import InputValidationError
from ai_education.services.homework_input import HomeworkImageService

MAX_MATERIAL_BYTES = 10 * 1024 * 1024
TEXT_TYPES = {"text/plain", "text/markdown"}
PDF_TYPES = {"application/pdf"}


class EnglishMaterialService:
    """Extract bounded text without persisting the raw student upload."""

    def __init__(self, image_service: HomeworkImageService | None = None) -> None:
        self.image_service = image_service or HomeworkImageService()

    def extract(
        self, content: bytes, content_type: str | None, filename: str | None
    ) -> dict[str, Any]:
        if not content or len(content) > MAX_MATERIAL_BYTES:
            raise InputValidationError("阅读材料为空或超过 10MB 限制")
        safe_name = Path(filename or "阅读材料").name[:180]
        media_type = (content_type or "").split(";", 1)[0].lower()
        warnings: list[str] = []
        source_type = "text"
        if media_type in PDF_TYPES or safe_name.lower().endswith(".pdf"):
            source_type = "pdf"
            try:
                reader = PdfReader(BytesIO(content))
                text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)
            except Exception as exc:
                raise InputValidationError("PDF 文件损坏、加密或无法提取文字") from exc
            if len(reader.pages) > 20:
                warnings.append("材料超过 20 页，本次只保留前 15000 字符用于训练")
        elif media_type.startswith("image/"):
            source_type = "image"
            result = self.image_service.process(content, media_type)
            text = str(result.get("text", ""))
            warnings.extend(result.get("warnings", []))
        elif media_type in TEXT_TYPES or safe_name.lower().endswith((".txt", ".md")):
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    text = content.decode("gb18030")
                except UnicodeDecodeError as exc:
                    raise InputValidationError("文本文件编码无法识别，请使用 UTF-8") from exc
        else:
            raise InputValidationError("仅支持 PDF、TXT、Markdown、JPG、PNG 或 WebP 阅读材料")

        normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()[:15_000]
        if len(normalized) < 80:
            raise InputValidationError("未提取到足够的英语正文，请检查文件清晰度或直接粘贴文本")
        english_letters = sum(
            character.isascii() and character.isalpha() for character in normalized
        )
        if english_letters / max(1, len(normalized)) < 0.35:
            warnings.append("材料中的英语正文比例较低，请在开始训练前核对提取结果")
        return {
            "filename": safe_name,
            "source_type": source_type,
            "text": normalized,
            "character_count": len(normalized),
            "warnings": warnings,
            "raw_upload_persisted": False,
        }
