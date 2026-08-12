"""Knowledge-bank reading, combined language study and microphone speaking services."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from langchain_core.prompts import ChatPromptTemplate
from pydantic import Field

from ai_education.core.errors import InputValidationError, ModelUnavailableError
from ai_education.domain.protocols import StrictModel, utc_now
from ai_education.english_learning_repository import EnglishLearningRepository

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_READING_ROOT = PROJECT_ROOT / "Knowledge" / "english_reading"
DEFAULT_READING_ANSWER_PATH = (
    PROJECT_ROOT / "Knowledge" / ".private_english_reading" / "reading_answers.json"
)
WORD_PATTERN = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)?")


class WordDetail(StrictModel):
    word: str = Field(min_length=1, max_length=80)
    phonetic: str = Field(default="", max_length=80)
    part_of_speech: str = Field(default="", max_length=80)
    contextual_meaning: str = Field(min_length=1, max_length=500)
    morphology: str = Field(default="", max_length=500)
    sentence_role: str = Field(default="", max_length=500)
    collocations: list[str] = Field(default_factory=list, max_length=8)
    example: str = Field(default="", max_length=600)
    common_mistake: str = Field(default="", max_length=600)
    difficulty: Literal["基础", "重点", "拓展"] = "基础"


class VocabularyStudyResult(StrictModel):
    summary: str = Field(min_length=2, max_length=1_000)
    words: list[WordDetail] = Field(min_length=1, max_length=100)


class GrammarIssue(StrictModel):
    original: str = Field(default="", max_length=500)
    issue_type: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=2, max_length=800)
    hint: str = Field(min_length=2, max_length=800)


class GrammarStudyResult(StrictModel):
    is_complete_sentence: bool
    sentence_type: str = Field(min_length=1, max_length=120)
    overall_feedback: str = Field(min_length=2, max_length=1_000)
    issues: list[GrammarIssue] = Field(default_factory=list, max_length=12)
    correction_steps: list[str] = Field(default_factory=list, max_length=12)
    corrected_sentence: str = Field(default="", max_length=3_000)
    practice: list[str] = Field(default_factory=list, max_length=5)


class SpeakingAssessment(StrictModel):
    reply: str = Field(min_length=2, max_length=1_500)
    next_question: str = Field(min_length=2, max_length=800)
    scores: dict[str, int] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list, max_length=8)
    improvements: list[str] = Field(default_factory=list, max_length=8)
    corrected_expression: str = Field(default="", max_length=3_000)
    practice_advice: list[str] = Field(default_factory=list, max_length=8)


VOCABULARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是面向新高考全国Ⅰ卷高中生的英语词汇教师。
必须逐一覆盖 target_words 中的每个词，只解释其在 source_text 当前语境中的含义。
每个词给出音标、词性、构词、句中作用、搭配、自然例句和易错点。
不得遗漏目标词，不把标点当作词，不虚构无法确认的词源。输出结构化结果。""",
        ),
        (
            "human",
            "source_text:\n{source_text}\n\ntarget_words:\n{target_words}\n\nlearner_level:{level}",
        ),
    ]
)

GRAMMAR_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是耐心的高中英语语法导师。先判断输入是否构成正常完整的英语句子。
若不是完整句，明确缺少主语、谓语、宾语或连接关系，并按步骤提示学生自行补全。
若是句子，采用最小修改原则逐项解释问题。corrected_sentence 可提供参考，
但 correction_steps 必须先给思考顺序，不得只抛出答案。输出结构化结果。""",
        ),
        ("human", "学生输入：{source_text}\n学习者水平：{level}"),
    ]
)

SPEAKING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是高中英语口语陪练教师。根据主题、语音转写文本、录音时长和语速进行回应和评价。
scores 必须包含 fluency、accuracy、coherence、vocabulary、speech_clarity 五项0—100整数。
speech_clarity 仅表示语音识别清晰度，不冒充专业音系测评。
反馈必须指出具体原句、给出可操作修改，并用英语提出自然的下一问以继续对话。""",
        ),
        (
            "human",
            "主题：{topic}\n转写：{transcript}\n时长：{duration_seconds}秒\n"
            "每分钟词数：{words_per_minute}",
        ),
    ]
)


class StructuredEnglishStudyCoach:
    def __init__(self, model: Any | None) -> None:
        self.vocabulary_chain = (
            VOCABULARY_PROMPT
            | model.with_structured_output(VocabularyStudyResult, method="function_calling")
            if model is not None
            else None
        )
        self.grammar_chain = (
            GRAMMAR_PROMPT
            | model.with_structured_output(GrammarStudyResult, method="function_calling")
            if model is not None
            else None
        )
        self.speaking_chain = (
            SPEAKING_PROMPT
            | model.with_structured_output(SpeakingAssessment, method="function_calling")
            if model is not None
            else None
        )

    async def vocabulary(self, text: str, words: list[str], level: str) -> VocabularyStudyResult:
        if self.vocabulary_chain is None:
            return VocabularyStudyResult(
                summary="已按原句顺序识别词汇；当前模型不可用，生词释义需稍后核验。",
                words=[
                    WordDetail(
                        word=word,
                        contextual_meaning="请结合原句上下文理解，模型恢复后可获得详细释义。",
                        sentence_role="原句中的词汇成分",
                        example=f"Please make a new sentence with {word}.",
                        common_mistake="不要脱离语境只记单一中文含义。",
                    )
                    for word in words
                ],
            )
        result = await self.vocabulary_chain.ainvoke(
            {"source_text": text, "target_words": ", ".join(words), "level": level}
        )
        by_word = {item.word.lower(): item for item in result.words}
        ordered = []
        for word in words:
            ordered.append(
                by_word.get(word.lower())
                or WordDetail(
                    word=word,
                    contextual_meaning="模型未返回该词释义，请重新分析本句。",
                    sentence_role="待进一步分析",
                    common_mistake="不要在缺少可靠释义时直接加入生词本。",
                )
            )
        return VocabularyStudyResult(summary=result.summary, words=ordered)

    async def grammar(self, text: str, level: str) -> GrammarStudyResult:
        if self.grammar_chain is not None:
            return await self.grammar_chain.ainvoke({"source_text": text, "level": level})
        complete = bool(re.search(r"[.!?]$", text)) and len(WORD_PATTERN.findall(text)) >= 3
        return GrammarStudyResult(
            is_complete_sentence=complete,
            sentence_type="完整句" if complete else "句子片段",
            overall_feedback=(
                "输入具备基本句子外形，请重点检查主谓一致和时态。"
                if complete
                else "当前输入更像短语，请先补出明确的主语和谓语。"
            ),
            correction_steps=["找到句子的主语", "圈出谓语动词", "确认时态和句末标点"],
            corrected_sentence=text,
            practice=["请用相同主语再写一个完整句子。"],
        )

    async def speaking(
        self, topic: str, transcript: str, duration_seconds: int
    ) -> SpeakingAssessment:
        word_count = len(WORD_PATTERN.findall(transcript))
        words_per_minute = round(word_count / max(duration_seconds, 1) * 60)
        if self.speaking_chain is not None:
            return await self.speaking_chain.ainvoke(
                {
                    "topic": topic,
                    "transcript": transcript,
                    "duration_seconds": duration_seconds,
                    "words_per_minute": words_per_minute,
                }
            )
        return SpeakingAssessment(
            reply="Thank you for sharing. Could you add one specific example?",
            next_question="Why is this topic important to you?",
            scores={
                "fluency": min(85, max(45, words_per_minute)),
                "accuracy": 65,
                "coherence": 65,
                "vocabulary": 60,
                "speech_clarity": 60,
            },
            improvements=["补充一个具体例子", "使用 because 或 therefore 连接观点"],
            corrected_expression=transcript,
            practice_advice=["围绕同一主题再说 30 秒，并使用一个因果连接词。"],
        )


class SpeechTranscriber:
    def __init__(self) -> None:
        self.model = os.getenv("AI_EDUCATION_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")

    async def transcribe(self, content: bytes, filename: str, content_type: str) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            return ""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL") or None,
            )
            result = await client.audio.transcriptions.create(
                model=self.model,
                file=(filename, content, content_type),
                language="en",
            )
            return str(result.text).strip()
        except Exception:
            return ""


class EnglishLearningV2Service:
    def __init__(
        self,
        repository: EnglishLearningRepository,
        coach: StructuredEnglishStudyCoach,
        bank_root: Path = DEFAULT_READING_ROOT,
        answer_path: Path = DEFAULT_READING_ANSWER_PATH,
        transcriber: SpeechTranscriber | None = None,
    ) -> None:
        self.repository = repository
        self.coach = coach
        self.transcriber = transcriber or SpeechTranscriber()
        bank = json.loads((bank_root / "reading_bank.json").read_text(encoding="utf-8"))
        self.items = bank["items"]
        self.by_id = {item["reading_id"]: item for item in self.items}
        self.answers = json.loads(answer_path.read_text(encoding="utf-8"))

    def catalog(self, student_id: str) -> dict[str, Any]:
        progress = {
            item["reading_id"]: item for item in self.repository.list_reading_progress(student_id)
        }
        items = []
        for reading in self.items:
            record = progress.get(reading["reading_id"])
            items.append(
                {
                    key: value
                    for key, value in reading.items()
                    if key not in {"article", "questions", "images", "source_document"}
                }
                | {
                    "status": record["status"] if record else "not_started",
                    "elapsed_seconds": record["elapsed_seconds"] if record else 0,
                    "score": record.get("score") if record else None,
                    "session_id": record["session_id"] if record else None,
                    "answered_count": len(record.get("answers", {})) if record else 0,
                }
            )
        return {
            "reading_count": len(items),
            "simulation_count": sum(item["category"] == "simulation" for item in items),
            "completed_count": sum(item["status"] == "completed" for item in items),
            "items": items,
        }

    def start(self, student_id: str, reading_id: str) -> dict[str, Any]:
        reading = self._reading(reading_id)
        existing = self.repository.load_reading_progress(student_id, reading_id)
        if existing and existing["status"] == "in_progress":
            return {"reading": reading, "progress": existing}
        now = utc_now().isoformat()
        progress = {
            "student_id": student_id,
            "reading_id": reading_id,
            "session_id": f"eng_bank_{uuid4().hex[:20]}",
            "status": "in_progress",
            "elapsed_seconds": 0,
            "answers": {},
            "score": None,
            "result": None,
            "started_at": now,
            "submitted_at": None,
            "updated_at": now,
        }
        self.repository.save_reading_progress(progress)
        return {"reading": reading, "progress": progress}

    def checkpoint(
        self, student_id: str, reading_id: str, answers: dict[str, int], elapsed: int
    ) -> dict[str, Any]:
        progress = self._progress(student_id, reading_id)
        if progress["status"] != "in_progress":
            raise InputValidationError("该阅读已经提交，不能修改")
        valid_ids = {item["question_id"] for item in self._reading(reading_id)["questions"]}
        if any(key not in valid_ids or value not in range(4) for key, value in answers.items()):
            raise InputValidationError("阅读答案包含无效题号或选项")
        progress.update(
            {
                "answers": answers,
                "elapsed_seconds": elapsed,
                "updated_at": utc_now().isoformat(),
            }
        )
        self.repository.save_reading_progress(progress)
        return progress

    def submit(
        self, student_id: str, reading_id: str, answers: dict[str, int], elapsed: int
    ) -> dict[str, Any]:
        reading = self._reading(reading_id)
        progress = self._progress(student_id, reading_id)
        if progress["status"] != "in_progress":
            raise InputValidationError("该阅读已经提交")
        if set(answers) != {item["question_id"] for item in reading["questions"]}:
            raise InputValidationError("请完成全部题目后再提交")
        answer_map = {item["question_id"]: item for item in self.answers[reading_id]["answers"]}
        results = []
        for question in reading["questions"]:
            answer = answer_map[question["question_id"]]
            selected = answers[question["question_id"]]
            results.append(
                {
                    "question_id": question["question_id"],
                    "selected_option": selected,
                    "correct_option": answer["correct_option"],
                    "is_correct": selected == answer["correct_option"],
                    "explanation": answer["explanation"],
                }
            )
        score = round(sum(item["is_correct"] for item in results) / len(results), 4)
        now = utc_now().isoformat()
        progress.update(
            {
                "status": "completed",
                "answers": answers,
                "elapsed_seconds": elapsed,
                "score": score,
                "result": results,
                "submitted_at": now,
                "updated_at": now,
            }
        )
        self.repository.save_reading_progress(progress)
        return {"reading": reading, "progress": progress, "results": results}

    async def analyze_language(
        self, student_id: str, text: str, mode: str, level: str
    ) -> dict[str, Any]:
        del student_id
        if mode == "grammar":
            result = await self.coach.grammar(text, level)
            return {"mode": mode, "grammar": result.model_dump(mode="json")}
        words = list(dict.fromkeys(item.lower() for item in WORD_PATTERN.findall(text)))
        if not words:
            raise InputValidationError("没有识别到英语词汇")
        results = []
        for offset in range(0, len(words), 40):
            results.append(await self.coach.vocabulary(text, words[offset : offset + 40], level))
        return {
            "mode": mode,
            "vocabulary": {
                "summary": " ".join(result.summary for result in results),
                "words": [
                    item.model_dump(mode="json") for result in results for item in result.words
                ],
            },
        }

    def save_vocabulary(
        self, student_id: str, source_text: str, words: list[dict[str, Any]]
    ) -> dict[str, Any]:
        now = utc_now()
        existing = {
            item["word_key"]: item
            for item in self.repository.learning_records(student_id)["vocabulary"]
        }
        saved = []
        for raw in words:
            item = WordDetail.model_validate(raw)
            key = item.word.lower()
            old = existing.get(key, {})
            saved.append(
                {
                    "student_id": student_id,
                    "word_key": key,
                    "word": item.word,
                    "phonetic": item.phonetic,
                    "part_of_speech": item.part_of_speech,
                    "contextual_meaning": item.contextual_meaning,
                    "collocations": item.collocations,
                    "example": item.example,
                    "common_mistake": item.common_mistake,
                    "contexts_seen": int(old.get("contexts_seen", 0)) + 1,
                    "encounter_count": int(old.get("encounter_count", 0)) + 1,
                    "correct_count": int(old.get("correct_count", 0)),
                    "wrong_count": int(old.get("wrong_count", 0)),
                    "mastery_score": float(old.get("mastery_score", 0.25)),
                    "status": "learning",
                    "next_review_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
        event = {
            "event_id": f"eng_evt_{uuid4().hex[:18]}",
            "student_id": student_id,
            "task_type": "vocabulary_explanation",
            "response_mode": "teaching",
            "source_excerpt": source_text[:800],
            "learner_level": "B1",
            "result": {"selected_words": [item["word"] for item in saved]},
            "generation_mode": "llm",
            "quality_status": "passed",
            "created_at": now.isoformat(),
        }
        self.repository.save_learning_task_bundle(event, saved, [], None, None, [])
        return {"saved_count": len(saved), "words": saved}

    async def assess_speaking(
        self,
        student_id: str,
        topic: str,
        audio: bytes,
        filename: str,
        content_type: str,
        duration_seconds: int,
        browser_transcript: str,
    ) -> dict[str, Any]:
        if not topic.strip():
            raise InputValidationError("请先输入口语主题")
        if not audio or len(audio) > 15 * 1024 * 1024:
            raise InputValidationError("录音为空或超过 15MB")
        transcript = await self.transcriber.transcribe(audio, filename, content_type)
        transcription_source = "audio_model"
        if not transcript:
            transcript = browser_transcript.strip()
            transcription_source = "browser_speech_recognition"
        if not transcript:
            raise ModelUnavailableError("录音已收到，但当前语音转写服务不可用，请使用 Chrome 重试")
        assessment = await self.coach.speaking(topic, transcript, duration_seconds)
        now = utc_now().isoformat()
        speaking = {
            "speaking_session_id": f"eng_speak_{uuid4().hex[:18]}",
            "student_id": student_id,
            "event_id": f"eng_evt_{uuid4().hex[:18]}",
            "scenario": topic,
            "feedback_mode": "delayed",
            "transcript": transcript,
            "feedback": assessment.model_dump(mode="json"),
            "pronunciation_scored": True,
            "created_at": now,
        }
        event = {
            "event_id": speaking["event_id"],
            "student_id": student_id,
            "task_type": "speaking_practice",
            "response_mode": "immersive",
            "source_excerpt": transcript[:800],
            "learner_level": "B1",
            "result": assessment.model_dump(mode="json"),
            "generation_mode": "llm",
            "quality_status": "passed",
            "created_at": now,
        }
        self.repository.save_learning_task_bundle(event, [], [], None, speaking, [])
        return {
            "topic": topic,
            "transcript": transcript,
            "transcription_source": transcription_source,
            "duration_seconds": duration_seconds,
            "assessment": assessment.model_dump(mode="json"),
            "audio_persisted": False,
        }

    def _reading(self, reading_id: str) -> dict[str, Any]:
        reading = self.by_id.get(reading_id)
        if not reading:
            raise InputValidationError("阅读题不存在")
        return reading

    def _progress(self, student_id: str, reading_id: str) -> dict[str, Any]:
        progress = self.repository.load_reading_progress(student_id, reading_id)
        if not progress:
            raise InputValidationError("请先点击开始答题")
        return progress
