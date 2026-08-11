"""Build a public reading bank and a server-only answer bank from the local 5·3 DOCX."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from docx import Document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    PROJECT_ROOT / "Knowledge/title/2026五年高考三年模拟53A、B版新高考全套资料/B版/新高考/"
    "教师版/2026版.新高考版.高考总复习.英语.5·3B版/题型册/专题一_阅读理解/"
    "1_专题资料包/2_专题一  阅读理解.docx"
)
OUTPUT = PROJECT_ROOT / "Knowledge/english_reading"
PRIVATE_OUTPUT = PROJECT_ROOT / "Knowledge/.private_english_reading"
HEADING = re.compile(r"^Passage\s+\d+\((?P<label>[^)]+)\)\s*主题\s*(?P<topic>.+?)\s*$")
QUESTION = re.compile(r"^(?P<number>\d{1,2})[.．、]\s*(?P<body>.+)$", re.S)
OPTION = re.compile(r"(?<![A-Za-z])([A-D])[.．]\s*")
ANSWER = re.compile(r"^(\d{1,2})[.．、]\s*([A-D])(?:\s|　|$)")


def clean(value: str) -> str:
    return re.sub(r"[ \t　]+", " ", value).strip()


def paragraph_images(document: Document, paragraph: object) -> list[tuple[str, bytes]]:
    images: list[tuple[str, bytes]] = []
    for blip in paragraph._p.xpath(".//a:blip"):  # type: ignore[attr-defined]
        relationship_id = blip.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
        )
        if not relationship_id:
            continue
        part = document.part.related_parts.get(relationship_id)
        if part is not None:
            images.append((str(part.partname), part.blob))
    return images


def parse_question(lines: list[str], answers: dict[int, str]) -> dict | None:
    joined = clean(" ".join(lines))
    match = QUESTION.match(joined)
    if not match:
        return None
    number = int(match.group("number"))
    body = match.group("body")
    markers = list(OPTION.finditer(body))
    if len(markers) != 4 or number not in answers:
        return None
    stem = clean(body[: markers[0].start()])
    options = [
        clean(body[marker.end() : markers[index + 1].start() if index < 3 else None])
        for index, marker in enumerate(markers)
    ]
    if not stem or any(not item for item in options):
        return None
    return {
        "question_id": f"q{number}",
        "number": number,
        "stem": stem,
        "options": options,
    }


def main() -> None:
    document = Document(SOURCE)
    paragraphs = document.paragraphs
    simulation_index = next(
        (index for index, item in enumerate(paragraphs) if clean(item.text) == "三年模拟"),
        len(paragraphs),
    )
    heading_indexes = [
        index for index, paragraph in enumerate(paragraphs) if HEADING.match(clean(paragraph.text))
    ]
    public_items: list[dict] = []
    private_answers: dict[str, dict] = {}
    assets_dir = OUTPUT / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    for position, start in enumerate(heading_indexes):
        end = (
            heading_indexes[position + 1]
            if position + 1 < len(heading_indexes)
            else len(paragraphs)
        )
        heading = HEADING.match(clean(paragraphs[start].text))
        assert heading is not None
        block = paragraphs[start + 1 : end]
        answer_index = next(
            (index for index, paragraph in enumerate(block) if clean(paragraph.text) == "答案"),
            -1,
        )
        if answer_index < 0:
            continue
        answer_map: dict[int, str] = {}
        explanation_map: dict[int, str] = {}
        for paragraph in block[answer_index + 1 :]:
            line = clean(paragraph.text)
            match = ANSWER.match(line)
            if not match:
                continue
            number = int(match.group(1))
            answer_map[number] = match.group(2)
            explanation_map[number] = clean(line[match.end() :])

        before_answers = block[:answer_index]
        first_question = next(
            (
                index
                for index, paragraph in enumerate(before_answers)
                if QUESTION.match(clean(paragraph.text))
            ),
            -1,
        )
        if first_question < 1:
            continue
        article_lines = [
            clean(paragraph.text)
            for paragraph in before_answers[:first_question]
            if clean(paragraph.text)
        ]
        question_groups: list[list[str]] = []
        for paragraph in before_answers[first_question:]:
            line = clean(paragraph.text)
            if not line:
                continue
            if QUESTION.match(line):
                question_groups.append([line])
            elif question_groups:
                question_groups[-1].append(line)
        questions = [
            parsed
            for group in question_groups
            if (parsed := parse_question(group, answer_map)) is not None
        ]
        if len(questions) < 2 or len(article_lines) < 2:
            continue

        label = clean(heading.group("label"))
        source_name, section = (
            [clean(item) for item in re.split(r"[,，]", label)[-2:]]
            if re.search(r"[,，]", label)
            else (label, "")
        )
        reading_id = (
            "eng_read_"
            + hashlib.sha256((label + "\n" + "\n".join(article_lines)).encode()).hexdigest()[:18]
        )
        image_urls: list[str] = []
        seen_images: set[str] = set()
        for paragraph in before_answers[:first_question]:
            for part_name, blob in paragraph_images(document, paragraph):
                digest = hashlib.sha256(blob).hexdigest()[:16]
                if digest in seen_images:
                    continue
                seen_images.add(digest)
                suffix = Path(part_name).suffix.lower() or ".png"
                filename = f"{reading_id}_{digest}{suffix}"
                (assets_dir / filename).write_bytes(blob)
                image_urls.append(f"/api/v1/english-learning/reading-assets/{filename}")

        word_count = len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)?", " ".join(article_lines)))
        difficulty_score = min(0.92, max(0.35, 0.42 + word_count / 1_500))
        title = f"{source_name}英语阅读{section}" if section else f"{source_name}英语阅读"
        public_items.append(
            {
                "reading_id": reading_id,
                "title": title,
                "source_label": label,
                "year": int(re.search(r"20\d{2}", label).group())
                if re.search(r"20\d{2}", label)
                else None,
                "section": section,
                "topic": clean(heading.group("topic")),
                "category": "simulation" if start > simulation_index else "past_exam",
                "article": "\n\n".join(article_lines),
                "images": image_urls,
                "questions": questions,
                "question_count": len(questions),
                "word_count": word_count,
                "difficulty": round(difficulty_score, 3),
                "source_document": SOURCE.name,
            }
        )
        private_answers[reading_id] = {
            "reading_id": reading_id,
            "answers": [
                {
                    "question_id": question["question_id"],
                    "correct_option": ord(answer_map[question["number"]]) - 65,
                    "explanation": explanation_map.get(question["number"], ""),
                }
                for question in questions
            ],
        }

    public_items.sort(
        key=lambda item: (
            item["category"] != "simulation",
            -(item["year"] or 0),
            item["title"],
        )
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "reading_bank.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source_document": SOURCE.name,
                "reading_count": len(public_items),
                "simulation_count": sum(item["category"] == "simulation" for item in public_items),
                "items": public_items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    PRIVATE_OUTPUT.mkdir(parents=True, exist_ok=True)
    (PRIVATE_OUTPUT / "reading_answers.json").write_text(
        json.dumps(private_answers, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"built {len(public_items)} readings "
        f"({sum(item['category'] == 'simulation' for item in public_items)} simulations)"
    )


if __name__ == "__main__":
    main()
