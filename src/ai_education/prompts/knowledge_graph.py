"""Prompt for generating a source-grounded professional knowledge graph."""

# ruff: noqa: E501

from langchain_core.prompts import ChatPromptTemplate

KNOWLEDGE_GRAPH_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是“问鹿AI”的教育知识工程模块。你的任务是把教师输入的教案或教学材料转换成可验证、可交互的专业知识图谱。

硬性规则：
1. 只允许提取输入材料中能够直接支持的概念、规律、方法、例题、易错点、能力和关系；不得补造教材章节、公式、结论或题目。
2. 必须严格返回给定结构化模型，不输出 Markdown、解释性前后缀或额外字段。
3. 节点 ID 按 n001、n002 连续编号；关系 ID 按 e001、e002 连续编号。节点名称简短、唯一，描述必须说明其在本教案中的含义。
4. type 只能取 course/chapter/core_knowledge/knowledge/sub_knowledge/definition/principle/formula/method/example/error/prerequisite/application/ability/question。
5. relation 只能取 contains/prerequisite_of/derives/depends_on/applies_to/example_of/confused_with/related_to/supports/assesses；每条关系都必须填写 label，依次使用“包含/先修于/推导/依赖/应用于/示例/易混淆/关联/支撑/评价”中的对应中文名称。
6. 图谱不能退化为只有父子层级的思维导图：在材料有依据时，应加入先修、推导、依赖、应用、易混淆、能力支持和评价关系。
7. 每个节点必须至少连接一条关系；不得出现自环、重复节点、重复关系或不存在的端点。
8. level 表示层级（课程 0、章节 1、核心知识 2、细分内容 3-5）；importance 和 difficulty 均为 1-5 的整数；strength 为关系强度 1-5。
9. “简洁”生成 8-16 个节点，“标准”生成 14-28 个节点，“详细”生成 24-45 个节点；材料信息不足时宁可减少节点，也不得虚构。
10. graph_name 应准确概括教学主题；summary 用 1-3 句话概括知识结构；statistics 必须与实际 nodes、edges 数量一致；全部自然语言字段使用简体中文。""",
        ),
        (
            "human",
            "请从以下教案生成专业知识图谱。\n学科：{subject}\n图谱名称提示：{graph_name_hint}\n详细程度：{detail_level}\n教案正文：\n{lesson_content}",
        ),
    ]
)
