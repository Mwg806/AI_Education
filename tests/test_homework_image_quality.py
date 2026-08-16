from __future__ import annotations

from io import BytesIO

from PIL import Image

from ai_education.services.homework_input import HomeworkImageService


class PredictableOcrImageService(HomeworkImageService):
    def __init__(self, confidence: float) -> None:
        super().__init__()
        self.confidence = confidence

    def _extract_ocr(self, image: object) -> tuple[str, float]:
        return "已识别的题目与解题步骤", self.confidence


def image_bytes(size: tuple[int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_clear_narrow_crop_is_not_rejected_by_short_side_alone() -> None:
    result = PredictableOcrImageService(0.95).process(image_bytes((1_600, 500)), "image/png")

    assert result["warnings"] == []
    assert result["quality"]["short_side"] == 500
    assert result["quality"]["resolution_review_required"] is False


def test_genuinely_small_image_still_requires_resolution_review() -> None:
    result = PredictableOcrImageService(0.95).process(image_bytes((600, 400)), "image/png")

    assert any("有效分辨率偏低" in warning for warning in result["warnings"])
    assert result["quality"]["resolution_review_required"] is True


def test_borderline_image_uses_ocr_confidence_as_supporting_evidence() -> None:
    payload = image_bytes((800, 500))
    clear = PredictableOcrImageService(0.92).process(payload, "image/png")
    uncertain = PredictableOcrImageService(0.55).process(payload, "image/png")

    assert clear["quality"]["resolution_review_required"] is False
    assert uncertain["quality"]["resolution_review_required"] is True
    assert any("OCR" in warning for warning in uncertain["warnings"])
