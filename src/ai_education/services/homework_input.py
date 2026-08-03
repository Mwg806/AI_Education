"""Bounded image validation and optional OCR for homework uploads."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

from ai_education.core.errors import InputValidationError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class HomeworkImageService:
    """Process images in memory; raw uploads and EXIF metadata are not persisted."""

    def __init__(self) -> None:
        self._ocr: Any | None = None

    def process(self, content: bytes, content_type: str | None) -> dict[str, Any]:
        if not content or len(content) > MAX_IMAGE_BYTES:
            raise InputValidationError("图片为空或超过 10MB 限制")
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise InputValidationError("仅支持 JPG、PNG 或 WebP 题目图片")
        try:
            from PIL import Image, ImageStat

            image = Image.open(BytesIO(content))
            image.verify()
            image = Image.open(BytesIO(content)).convert("RGB")
        except Exception as exc:
            raise InputValidationError("图片文件损坏或格式不可识别") from exc

        width, height = image.size
        warnings: list[str] = []
        if min(width, height) < 700:
            warnings.append("图片分辨率偏低，请确认关键文字和公式")
        grayscale = image.convert("L")
        variance = float(ImageStat.Stat(grayscale).var[0])
        if variance < 220:
            warnings.append("图片对比度或清晰度偏低")

        text, confidence = self._extract_ocr(image)
        if confidence < 0.8:
            warnings.append("OCR 关键内容置信度不足；将由多模态模型结合原图判断")
        model_image = image.copy()
        model_image.thumbnail((2048, 2048))
        encoded = BytesIO()
        model_image.save(encoded, format="JPEG", quality=90, optimize=True)
        data_url = "data:image/jpeg;base64," + base64.b64encode(encoded.getvalue()).decode()
        return {
            "text": text,
            "confidence": round(confidence, 3),
            "warnings": warnings,
            "data_url": data_url,
            "quality": {
                "width": width,
                "height": height,
                "contrast_variance": round(variance, 2),
                "processable": bool(text),
            },
        }

    def _extract_ocr(self, image: Any) -> tuple[str, float]:
        try:
            if self._ocr is None:
                from rapidocr_onnxruntime import RapidOCR

                self._ocr = RapidOCR()
            import numpy as np

            result, _ = self._ocr(np.asarray(image))
            if not result:
                return "", 0.0
            texts = [str(line[1]).strip() for line in result if len(line) >= 3 and line[1]]
            confidences = [float(line[2]) for line in result if len(line) >= 3]
            confidence = sum(confidences) / len(confidences) if confidences else 0.0
            return "\n".join(texts)[:20_000], confidence
        except Exception:
            return "", 0.0
