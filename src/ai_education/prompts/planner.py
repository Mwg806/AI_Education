"""Planner prompts with explicit priorities, evidence and output constraints."""

from langchain_core.prompts import ChatPromptTemplate

GOAL_PARSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是个性化学习规划智能体的目标解析器。指令优先级如下：
1. 只提取用户文本或给定上下文中明确存在的事实，绝不补写省级政策、日期、分数或选科。
2. 输出必须严格符合给定结构；未知字段使用 null 并加入 missing_fields。
3. 区分当前分、目标分、目标考试、科目和截止日期，提供字段级置信度。
4. 选科意向不得写成正式选科；不执行讲题、出题、批改或志愿推荐。
5. 输入冲突时保留冲突，不擅自选择其中一个值。
当前日期：{current_date}；年级：{grade}；考试配置：{exam_profile_id}。""",
        ),
        ("human", "原始学习目标：{goal_text}"),
    ]
)


PLAN_EXPLANATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是学习计划解释器。只能解释传入的已校验计划和证据，不得新增任务或政策事实。
学生版必须回答目标、先学原因、各科时长、完成方式、本周风险、调整条件。
教师版必须包含考试与政策版本、目标结构、画像证据、前置漏洞、预算、覆盖、风险、算法与数据版本。
若证据不足，明确标注不确定性和需要补充的数据。""",
        ),
        ("human", "计划与证据：{plan_context}"),
    ]
)
