from __future__ import annotations

import json
import re
from pathlib import Path


BANK_ROOT = Path(__file__).resolve().parents[1] / "Knowledge" / "Exam" / "高考真题" / "diagnose"
HUMANITIES = ("chinese", "history", "geography", "ideology_politics")
TAG_RE = re.compile(r"<[^>]+>")
MATERIAL_REFERENCE = re.compile(
    r"(?:下列对(?:文本|原文|文章)|(?<!一)文中|原文中|材料[一二三四]?(?:相关|中)|"
    r"根据图|上述材料|这首(?:诗|词)|该诗|该文(?!学))"
)
EXAM_DIRECTION = re.compile(
    r"^\s*(?:\d{1,2}\s*[.．、]\s*)?(?:答题时请|请按照题号顺序|作图可先|保持卡面清洁)"
)


def _plain(markup: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", markup)).strip()


def test_humanities_questions_include_required_material_and_options() -> None:
    report = json.loads((BANK_ROOT / "integrity_report.json").read_text(encoding="utf-8"))
    assert report["valid"] is True

    for subject in HUMANITIES:
        papers = sorted((BANK_ROOT / subject).glob("*.json"))
        assert len(papers) == 10
        for paper_path in papers:
            paper = json.loads(paper_path.read_text(encoding="utf-8"))
            assert len(paper["questions"]) == 20
            for question in paper["questions"]:
                stem_html = question["stem_html"]
                stem_plain = _plain(stem_html)
                assert not EXAM_DIRECTION.match(stem_plain), question["question_id"]
                if question["type"] == "multiple_choice":
                    assert [option["key"] for option in question["options"]] == list("ABCD")
                    assert all(_plain(option["content_html"]) or "<img" in option["content_html"] for option in question["options"])
                if MATERIAL_REFERENCE.search(stem_plain) and len(stem_plain) < 160:
                    assert "exam-shared-context" in stem_html or "<img" in stem_html, (
                        f"{question['question_id']} 引用了材料但题面没有携带材料"
                    )


def test_first_chinese_paper_no_longer_contains_bare_text_references() -> None:
    paper = json.loads(
        (BANK_ROOT / "chinese" / "gaokao_diag_chinese_01.json").read_text(encoding="utf-8")
    )
    referenced = [
        question
        for question in paper["questions"]
        if MATERIAL_REFERENCE.search(_plain(question["stem_html"]))
    ]
    assert referenced
    assert all(
        "exam-shared-context" in question["stem_html"] or len(_plain(question["stem_html"])) >= 160
        for question in referenced
    )
