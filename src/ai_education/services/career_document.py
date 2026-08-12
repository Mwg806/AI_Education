"""Safe local document extraction boundary for project-training submissions."""

from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from ai_education.config import PROJECT_ROOT
from ai_education.core.errors import InputValidationError

MAX_PROJECT_UPLOAD_BYTES = 2 * 1024 * 1024
ALLOWED_SUFFIXES = {".md", ".txt", ".docx"}
UPLOAD_ROOT = PROJECT_ROOT / "data" / "agent6_uploads"


def extract_project_upload(
    *,
    filename: str,
    content_type: str | None,
    content: bytes,
    student_id: str,
    session_id: str,
) -> tuple[str, dict[str, str | int]]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise InputValidationError("仅支持 .md、.txt 和 .docx 项目回答文档")
    if not content or len(content) > MAX_PROJECT_UPLOAD_BYTES:
        raise InputValidationError("上传文件必须为 1 字节至 2MB")
    if suffix in {".md", ".txt"}:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InputValidationError("文本文件必须使用 UTF-8 编码") from exc
    else:
        text = _docx_text(content)
    if len(text.strip()) < 50:
        raise InputValidationError("文档有效回答内容过少")
    safe_student = re.sub(r"[^A-Za-z0-9_-]", "_", student_id)[:64]
    safe_session = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:96]
    directory = UPLOAD_ROOT / safe_student / safe_session
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f"answer_{uuid4().hex}{suffix}"
    path = directory / stored_name
    path.write_bytes(content)
    return text, {
        "original_name": Path(filename).name[:180],
        "stored_name": stored_name,
        "content_type": content_type or "application/octet-stream",
        "size_bytes": len(content),
        "storage_key": str(path.relative_to(PROJECT_ROOT)),
    }


def _docx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise InputValidationError("DOCX 文件损坏或结构不受支持") from exc
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(f"{namespace}p"):
        parts = [node.text or "" for node in paragraph.iter(f"{namespace}t")]
        if parts:
            paragraphs.append("".join(parts))
    return "\n".join(paragraphs)
