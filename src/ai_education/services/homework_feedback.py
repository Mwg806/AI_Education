"""Deterministic, content-aware feedback used when no external LLM is enabled."""

from __future__ import annotations

from dataclasses import dataclass

from ai_education.domain.enums import Subject
from ai_education.prompts.homework import SUBJECT_POLICIES


@dataclass(frozen=True, slots=True)
class ContentFeedback:
    topic: str
    method: str
    checkpoint: str


RULES: dict[Subject, list[tuple[tuple[str, ...], ContentFeedback]]] = {
    Subject.MATHEMATICS: [
        (
            ("导数", "单调", "极值"),
            ContentFeedback(
                "导数与函数单调性",
                "先确认定义域，写出导函数并求临界点，再分区间判断导数正负。",
                "临界点是否完整、导数符号是否与单调性结论一致",
            ),
        ),
        (
            ("数列", "通项", "前n项"),
            ContentFeedback(
                "数列",
                "先分清递推关系、通项和前 n 项和，再选择作差、作商或递推变形。",
                "下标范围和首项是否满足变形后的关系",
            ),
        ),
        (
            ("概率", "随机"),
            ContentFeedback(
                "概率与统计",
                "先明确样本空间和事件，再判断使用古典概型、条件概率还是分布模型。",
                "事件是否互斥、独立以及概率和是否为 1",
            ),
        ),
    ],
    Subject.PHYSICS: [
        (
            ("电路", "电流", "电压"),
            ContentFeedback(
                "电路及其应用",
                "先标出节点、电流方向和连接方式，再分清内外电路与测量量。",
                "串并联关系、欧姆定律适用对象和单位",
            ),
        ),
        (
            ("力", "速度", "加速度"),
            ContentFeedback(
                "力与运动",
                "先选研究对象、画受力图并规定正方向，再分过程列规律。",
                "受力是否遗漏以及矢量正负号是否统一",
            ),
        ),
    ],
    Subject.CHEMISTRY: [
        (
            ("有机", "官能团", "烃"),
            ContentFeedback(
                "有机化学基础",
                "先识别官能团和反应条件，再判断反应类型与可能产物。",
                "原子守恒、价键数和反应条件",
            ),
        ),
        (
            ("离子", "溶液", "反应"),
            ContentFeedback(
                "离子反应与溶液",
                "先判断电解质强弱和物质状态，再按守恒写离子关系。",
                "电荷、元素和电子是否同时守恒",
            ),
        ),
    ],
    Subject.BIOLOGY: [
        (
            ("遗传", "基因", "dna"),
            ContentFeedback(
                "遗传的分子基础",
                "先确定遗传过程和材料信息，再区分事实条件与概率推断。",
                "基因型、表现型和比例的对应关系",
            ),
        ),
        (
            ("细胞", "代谢"),
            ContentFeedback(
                "细胞结构与代谢",
                "先定位结构与过程，再沿物质、能量和信息变化分析。",
                "发生场所、反应条件和变量控制",
            ),
        ),
    ],
    Subject.CHINESE: [
        (
            ("诗", "意象"),
            ContentFeedback(
                "古代诗歌阅读",
                "结合题干定位意象、语言或手法，再用诗句证据解释表达效果。",
                "是否形成证据—分析—情感或作用的完整链条",
            ),
        ),
        (
            ("文言", "翻译"),
            ContentFeedback(
                "文言文阅读",
                "先落实关键词、句式和语境，再组织通顺译文。",
                "古今异义、词类活用和省略成分",
            ),
        ),
    ],
    Subject.FOREIGN_LANGUAGE: [
        (
            ("grammar", "语法", "时态"),
            ContentFeedback(
                "英语语法",
                "先判断设空处的句法成分，再结合时态、语态和固定搭配。",
                "主谓一致、非谓语逻辑主语和上下文时态",
            ),
        ),
        (
            ("read", "阅读"),
            ContentFeedback(
                "阅读理解",
                "先定位题干关键词对应段落，再区分原文事实、同义改写和推断。",
                "选项是否扩大、偷换或脱离原文范围",
            ),
        ),
    ],
    Subject.HISTORY: [
        (
            ("材料", "历史", "时期"),
            ContentFeedback(
                "历史材料题",
                "先定位时空背景与材料立场，再提取变化、原因和影响。",
                "每个判断是否有材料或史实依据",
            ),
        ),
    ],
    Subject.GEOGRAPHY: [
        (
            ("气候", "地形", "区域"),
            ContentFeedback(
                "区域地理综合",
                "先读区域位置、图例和变量，再建立自然与人文要素因果链。",
                "方向、尺度、时间变化和因果方向",
            ),
        ),
    ],
    Subject.IDEOLOGY_POLITICS: [
        (
            ("材料", "哲学", "经济", "政治"),
            ContentFeedback(
                "思想政治材料题",
                "用材料关键词限定理论范围，再按理论、材料对应和结论组织。",
                "理论表述是否准确且与材料逐点对应",
            ),
        ),
    ],
    Subject.TECHNOLOGY: [
        (
            ("算法", "设计", "系统"),
            ContentFeedback(
                "技术与设计",
                "先明确输入、处理、输出和约束，再评价方案。",
                "流程完整性、边界条件和评价指标",
            ),
        ),
    ],
}


def content_feedback(subject: Subject, stem: str, work: str = "") -> ContentFeedback:
    text = f"{stem}\n{work}".lower()
    for markers, feedback in RULES.get(subject, []):
        if any(marker in text for marker in markers):
            return feedback
    return ContentFeedback(
        topic=f"{subject.value}综合题",
        method=SUBJECT_POLICIES[subject],
        checkpoint="题干条件、所求目标与当前步骤使用的方法是否一一对应",
    )
