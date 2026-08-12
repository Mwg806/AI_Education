# 新高考全国Ⅰ卷高中英语阅读与语言学习 Agent

## 全链路需求规格与工具调用方案

---

## 1. 文档概述

### 1.1 文档目标

本文定义面向“个性化学习与教学辅助”多 Agent 系统的“高中英语阅读与语言学习 Agent”完整需求规格。

目标用户限定为：

* 中国大陆普通高中学生；
* 主要参加新高考全国Ⅰ卷英语考试；
* 母语以中文为主；
* 学习阶段覆盖高一、高二、高三；
* 学习目标包括校内同步学习、阶段考试、高考一轮复习、二轮复习和考前冲刺。

系统覆盖以下核心场景：

1. 阅读理解与七选五辅导；
2. 高中英语词汇、语法和语篇学习；
3. 应用文写作与读后续写批改；
4. 听力与口语表达训练；
5. 学习状态追踪、错题管理和间隔复习；
6. 首次能力测评与高考分项能力画像；
7. 日常训练、阶段复习和模拟考试分析；
8. 教师端教学辅助、学情分析和任务干预。

本文所有功能均拆分到可独立封装为工具的子任务粒度，并明确：

* 处理逻辑；
* 算法依据；
* Agent 调用方式；
* 触发条件；
* 调用边界；
* 输入输出规范；
* 状态更新规则。

---

## 2. 产品目标与设计边界

### 2.1 核心产品目标

系统核心目标不是单纯提高泛化英语水平，而是：

> 在符合普通高中英语课程要求的基础上，通过可解释的能力测评、题型诊断、个性化训练和长期学习追踪，提高学生在新高考全国Ⅰ卷英语中的稳定得分能力，同时发展阅读、表达、思维和自主学习能力。

### 2.2 默认考试对象

系统默认考试配置为：

```json
{
  "country": "CN",
  "education_stage": "senior_high_school",
  "subject": "english",
  "paper_family": "NEW_GAOKAO",
  "paper_variant": "NATIONAL_I",
  "curriculum_standard": "CN_HIGH_SCHOOL_ENGLISH_2017_2020",
  "exam_year": 2027
}
```

系统不得将题型数量、分值、听力实施方式等信息永久写死在 Prompt 中。

每个学习周期开始前，应调用：

```text
exam.resolve_paper_profile
```

根据以下信息加载当前适用配置：

* 高考年份；
* 学生省份；
* 试卷类型；
* 听力考试实施方式；
* 当前题型结构；
* 各题型分值；
* 写作任务要求；
* 省级实施差异。

### 2.3 系统禁止事项

系统不得：

* 仅使用 CEFR 等级评价中国高中生；
* 根据一次练习直接预测高考总分；
* 将刷题数量直接视为能力提升；
* 将所有生词都列为学习目标；
* 只根据关键词匹配判断阅读答案；
* 将语法正确性作为读后续写的唯一评价依据；
* 默认替学生完成整篇作文；
* 将 ASR 转写错误直接判定为学生语法错误；
* 将口语流利度直接折算为高考成绩；
* 在没有文本证据的情况下生成正式阅读题；
* 在未校验原意的情况下自动重写学生作文；
* 根据单次错误将某知识点判定为长期薄弱项。

---

# 3. 系统总体架构

## 3.1 Agent 角色设计

| Agent                       | 核心职责                   | 调用边界           |
| --------------------------- | ---------------------- | -------------- |
| Learning Orchestrator Agent | 意图识别、任务拆解、工具编排、会话控制    | 不直接生成能力分数或掌握结论 |
| Exam Profile Agent          | 解析省份、年份和全国Ⅰ卷考试配置       | 不参与学习内容生成      |
| Placement Assessment Agent  | 首次能力测评、自适应选题、能力估计      | 不负责长期复习计划      |
| Language Analysis Agent     | 文本解析、词汇语法标注、长难句分析、难度匹配 | 不判断学生是否已掌握     |
| Reading Tutor Agent         | 阅读理解、七选五、阅读策略、错因讲解     | 不负责作文整体改写      |
| Writing Coach Agent         | 应用文和读后续写批改、反馈和评分       | 不得默认代写         |
| Listening Coach Agent       | 听力材料生成、证据定位、错因分析       | 不根据听力结果评价发音    |
| Speaking Coach Agent        | 语音分析、口语陪练、表达反馈         | 不直接折算高考书面卷分数   |
| Learner Model Agent         | 掌握度更新、能力画像、证据聚合        | 不生成具体题目        |
| Review Scheduler Agent      | 遗忘风险计算、复习任务调度          | 不修改原始测评证据      |
| Quality Guard Agent         | 校验题目、评分、改写越界和低置信结论     | 不替代主业务 Agent   |
| Teacher Copilot Agent       | 学情汇总、教学建议、任务布置和教师覆盖    | 高影响决策需保留人工确认   |

## 3.2 系统结构

```text
学生端 / 教师端
        │
        ▼
Learning Orchestrator Agent
        │
        ├── Exam Profile Agent
        ├── Placement Assessment Agent
        ├── Language Analysis Agent
        ├── Reading Tutor Agent
        ├── Writing Coach Agent
        ├── Listening Coach Agent
        ├── Speaking Coach Agent
        ├── Learner Model Agent
        ├── Review Scheduler Agent
        └── Quality Guard Agent
                │
                ▼
Tool Layer
        ├── 文本语言分析工具
        ├── 高考题型生成与校验工具
        ├── 阅读作答评分工具
        ├── 写作分析与评分工具
        ├── ASR 与语音分析工具
        ├── 掌握度计算工具
        ├── 复习调度工具
        ├── 试卷配置服务
        ├── 学习者状态存储
        └── 教学分析数据仓库
```

---

# 4. 公共数据模型

## 4.1 学习者基础画像

```json
{
  "learner_id": "stu_001",
  "native_language": "zh-CN",
  "target_language": "en",
  "grade": 11,
  "province_code": "GD",
  "exam_year": 2027,
  "paper_variant": "NEW_GAOKAO_NATIONAL_I",
  "textbook_version": "PEP_2019",
  "learning_phase": "GRADE_11_DEVELOPMENT",
  "current_total_score": 102,
  "target_total_score": 125,
  "daily_available_minutes": 35,
  "preferences": {
    "explanation_language": "zh-CN",
    "feedback_style": "guided",
    "show_sentence_structure": true,
    "show_phonetics": true
  }
}
```

`learning_phase` 取值：

```text
GRADE_10_FOUNDATION
GRADE_11_DEVELOPMENT
GRADE_12_FIRST_ROUND_REVIEW
GRADE_12_SECOND_ROUND_REVIEW
PRE_EXAM_SPRINT
```

## 4.2 高考分项能力画像

```json
{
  "section_abilities": {
    "listening": 0.68,
    "reading_multiple_choice": 0.72,
    "reading_seven_of_five": 0.55,
    "cloze": 0.63,
    "grammar_filling": 0.58,
    "practical_writing": 0.66,
    "reading_continuation": 0.51
  },
  "reading_subskills": {
    "detail_location": 0.81,
    "main_idea": 0.71,
    "inference": 0.54,
    "author_attitude": 0.49,
    "word_meaning_in_context": 0.64,
    "text_structure": 0.57
  }
}
```

## 4.3 知识点模型

```json
{
  "knowledge_component_id": "grammar.en.non_finite.participle",
  "type": "grammar",
  "language": "en",
  "canonical_name": "非谓语动词：分词",
  "gaokao_task_links": [
    "GRAMMAR_FILLING",
    "READING_COMPLEX_SENTENCE",
    "PRACTICAL_WRITING",
    "READING_CONTINUATION"
  ],
  "prerequisites": [
    "grammar.en.sentence_components",
    "grammar.en.voice"
  ],
  "difficulty": 0.67
}
```

## 4.4 掌握状态模型

```json
{
  "learner_id": "stu_001",
  "knowledge_component_id": "grammar.en.non_finite.participle",
  "mastery_probability": 0.62,
  "stability_days": 4.6,
  "evidence_count": 7,
  "last_reviewed_at": "2026-07-29T09:00:00+08:00",
  "next_review_at": "2026-08-02T09:00:00+08:00",
  "recent_error_types": [
    "active_passive_confusion",
    "predicate_non_predicate_confusion"
  ],
  "confidence": 0.81
}
```

## 4.5 学习证据模型

```json
{
  "evidence_id": "evd_001",
  "learner_id": "stu_001",
  "session_id": "ses_001",
  "task_id": "task_003",
  "task_type": "GRAMMAR_FILLING",
  "knowledge_component_id": "grammar.en.non_finite.participle",
  "score": 0.75,
  "independence_level": "location_hint",
  "response_time_ms": 18400,
  "hint_count": 1,
  "item_difficulty": 0.64,
  "confidence": 0.91,
  "created_at": "2026-07-29T10:12:20+08:00"
}
```

## 4.6 通用工具调用协议

请求：

```json
{
  "request_id": "req_001",
  "session_id": "ses_001",
  "learner_id": "stu_001",
  "caller_agent": "reading_tutor_agent",
  "locale": "zh-CN",
  "target_language": "en",
  "task_context": {
    "scenario": "reading_multiple_choice",
    "session_mode": "daily_training",
    "exam_profile_id": "exam_2027_gd_national_1"
  },
  "payload": {},
  "constraints": {
    "max_latency_ms": 5000,
    "required_confidence": 0.75
  }
}
```

返回：

```json
{
  "request_id": "req_001",
  "tool_name": "gaokao.diagnose_reading_distractor",
  "status": "success",
  "result": {},
  "evidence": [],
  "confidence": 0.88,
  "warnings": [],
  "recommended_next_actions": []
}
```

---

# 5. 模块一：语言基础解析模块

## 5.1 模块定位

语言基础解析模块是阅读、完形、语法填空、写作、听力和口语任务的基础分析层。

该模块将原始文本转化为：

* 词汇结构；
* 语法结构；
* 长难句结构；
* 篇章结构；
* 高中课标词汇覆盖情况；
* 高考题型适配度；
* 对当前学生的相对难度；
* 可教学的核心词汇、语块和语法点。

该模块只分析文本本身，不直接判断学生是否已经掌握相关知识。

---

## 5.2 子任务拆解

### 5.2.1 文本预处理与语言识别

**工具：**

```text
language.detect_and_normalize
```

**触发条件：**

* 学生上传文章；
* 教师导入阅读材料；
* OCR 识别试卷；
* ASR 转写听力或口语内容；
* 学生提交作文。

**处理逻辑：**

1. Unicode 规范化；
2. 清除异常空格和无意义控制字符；
3. 保留学生原始拼写和语法错误；
4. 识别中英文混合内容；
5. 划分段落和句子；
6. 标记疑似 OCR 或 ASR 错误；
7. 生成字符位置映射。

**算法依据：**

* 字符级语言识别；
* 句子边界模型；
* 标点规则；
* OCR 噪声模式；
* 子词语言模型。

**调用边界：**

* 不得自动修正学生语言错误；
* 只能处理编码、空格和明显格式噪声；
* 疑似转写错误必须标记，不直接替换。

---

### 5.2.2 词法、形态与句法标注

**工具：**

```text
language.annotate_linguistic_features
```

**处理逻辑：**

* 分词；
* 词形还原；
* 词性标注；
* 时态、语态、单复数和人称标注；
* 依存句法分析；
* 从句识别；
* 非谓语结构识别；
* 命名实体识别；
* 指代关系分析；
* 逻辑连接词识别。

**输出示例：**

```json
{
  "text": "Having completed the experiment",
  "tokens": [
    {
      "text": "Having",
      "lemma": "have",
      "pos": "AUX",
      "morphology": {
        "form": "gerund"
      },
      "dependency": {
        "relation": "aux",
        "head_token_index": 1
      }
    }
  ]
}
```

**调用边界：**

* 不把复杂句式自动视为错误；
* 不直接输出教学结论；
* 低置信句法结构必须返回备选解析。

---

### 5.2.3 文本难度分级

**工具：**

```text
language.score_text_difficulty
```

**处理逻辑：**

分别计算：

* 词汇难度；
* 句法难度；
* 篇章衔接难度；
* 概念密度；
* 背景知识需求；
* 高考任务适配度；
* 学生相对认知负荷。

难度模型：

```text
D_text =
  w1 × lexical_sophistication
+ w2 × syntactic_complexity
+ w3 × discourse_complexity
+ w4 × conceptual_density
+ w5 × background_knowledge_requirement
```

相对负荷：

```text
RelativeLoad = D_text - LearnerAbility
```

建议解释：

|       相对负荷 | 使用方式          |
| ---------: | ------------- |
|     ≤ -0.5 | 适合速度和流利度训练    |
| -0.5 至 0.2 | 可独立完成         |
|  0.2 至 0.7 | 最佳挑战区         |
|  0.7 至 1.2 | 需要词汇、长难句或策略支架 |
|      > 1.2 | 应分段、加注或替换材料   |

**调用边界：**

* 不得只用平均句长或单一可读性公式；
* 无学生画像时只能输出绝对难度；
* 不得仅根据生词数量判断文章难度。

---

### 5.2.4 高中词汇覆盖率分析

**工具：**

```text
gaokao.analyze_vocabulary_requirements
```

**处理逻辑：**

识别：

* 高中课标词汇；
* 已掌握词；
* 学习中词；
* 未知高频词；
* 熟词生义；
* 派生词；
* 词性转换；
* 超纲但可推测词；
* 专有名词；
* 完形高价值词；
* 写作可迁移词块。

**输出：**

```json
{
  "known_coverage_ratio": 0.94,
  "critical_unknown_words": [],
  "familiar_words_with_new_meanings": [],
  "derivations": [],
  "low_priority_unknown_words": [],
  "writing_transfer_chunks": []
}
```

**调用边界：**

* 不将专有名词列为必背词；
* 不将所有未知词加入复习；
* 必须区分“影响理解的词”和“不影响主旨的词”。

---

### 5.2.5 核心词汇抽取

**工具：**

```text
language.extract_core_vocabulary
```

排序依据：

```text
Priority =
  0.30 × semantic_centrality
+ 0.20 × comprehension_impact
+ 0.20 × learner_unknown_probability
+ 0.15 × transfer_value
+ 0.10 × recurrence
- 0.05 × proper_noun_penalty
```

输出字段：

* 单词或短语；
* 文章内具体含义；
* 词性；
* 原文例句；
* 构词法；
* 同义替换；
* 高考常见考法；
* 写作迁移价值。

**推荐数量：**

* 每 300 词提取 5—12 个；
* 高一偏少且讲解充分；
* 高三冲刺阶段优先提取高频考法和易错义项。

---

### 5.2.6 固定搭配与语块抽取

**工具：**

```text
language.extract_collocations
```

识别类型：

* 动词搭配；
* 介词搭配；
* 形容词搭配；
* 名词短语；
* 逻辑连接语；
* 高考写作语块；
* 完形填空高频语块；
* 读后续写动作和情绪表达。

**算法依据：**

* 依存模板；
* 搭配词典；
* PMI；
* t-score；
* 上下文完整性；
* 高中语料频率。

**调用边界：**

* 低频偶然组合不得标为固定搭配；
* 不鼓励学生机械堆砌所谓高级表达。

---

### 5.2.7 语法点抽取

**工具：**

```text
language.extract_grammar_points
```

重点识别：

* 时态与语态；
* 主谓一致；
* 名词性从句；
* 定语从句；
* 状语从句；
* 非谓语动词；
* 特殊句式；
* 情态动词；
* 代词和指代；
* 冠词、介词和连词；
* 构词和词性转换。

输出：

```json
{
  "grammar_point": "non_finite_participle",
  "evidence_span": {},
  "difficulty": 0.68,
  "gaokao_relevance": [
    "GRAMMAR_FILLING",
    "READING_LONG_SENTENCE"
  ],
  "prerequisites": [],
  "teaching_priority": 0.83
}
```

**调用边界：**

文本中出现某语法结构，不代表必须讲解。需要结合：

* 当前任务目标；
* 学生最近错误；
* 语法点高考价值；
* 学生掌握概率。

---

### 5.2.8 长难句分析

**工具：**

```text
gaokao.analyze_long_complex_sentences
```

处理步骤：

1. 找主语和谓语；
2. 提取主句主干；
3. 标记从句；
4. 标记非谓语；
5. 标记插入语、同位语和倒装；
6. 恢复省略成分；
7. 划分意群；
8. 标记逻辑关系；
9. 生成中文理解提示；
10. 映射阅读失分风险。

输出：

```json
{
  "sentence": "...",
  "main_clause": "...",
  "subordinate_clauses": [],
  "non_finite_structures": [],
  "logical_relations": [
    "contrast",
    "cause"
  ],
  "gaokao_risks": [
    "REFERENCE_RESOLUTION",
    "LOGICAL_RELATION"
  ],
  "explanation_steps": []
}
```

---

### 5.2.9 文本与高考题型映射

**工具：**

```text
gaokao.map_text_to_exam_skills
```

判断材料是否适合生成：

* 阅读理解选择题；
* 七选五；
* 完形填空；
* 语法填空；
* 应用文素材；
* 读后续写素材；
* 听力材料。

输出：

```json
{
  "recommended_task_types": [
    {
      "type": "READING_INFERENCE",
      "suitability": 0.91
    },
    {
      "type": "SEVEN_OF_FIVE",
      "suitability": 0.74
    }
  ],
  "unsuitable_task_types": [
    {
      "type": "READING_CONTINUATION",
      "reason": "缺少完整人物冲突和情节发展"
    }
  ]
}
```

---

### 5.2.10 学习内容适配

**工具：**

```text
language.adapt_content
```

适配模式：

```text
GLOSS_ONLY
SENTENCE_SEGMENTATION
LONG_SENTENCE_SCAFFOLDING
LEXICAL_SIMPLIFICATION
BILINGUAL_SUPPORT
GRADED_REWRITE
```

**处理边界：**

* 不得改变作者态度；
* 不得改变事实关系；
* 不得删除答题必要信息；
* 不得删除目标语法结构；
* 正式模拟题不得使用改写后文本替代原文，除非任务本身明确为分级阅读训练。

---

## 5.3 对应工具设计

```text
language.detect_and_normalize
  → language.annotate_linguistic_features
  → language.score_text_difficulty
  → gaokao.analyze_vocabulary_requirements
  → language.extract_core_vocabulary
  → language.extract_collocations
  → language.extract_grammar_points
  → gaokao.analyze_long_complex_sentences
  → gaokao.map_text_to_exam_skills
```

条件调用：

```json
{
  "condition": "relative_load > 0.7",
  "actions": [
    "language.adapt_content"
  ]
}
```

---

## 5.4 输入输出规范

输入：

```json
{
  "text": "Original learning material...",
  "source_type": "reading_article",
  "exam_profile_id": "exam_2027_gd_national_1",
  "learner_profile": {
    "grade": 11,
    "reading_ability": 0.62,
    "learning_phase": "GRADE_11_DEVELOPMENT"
  },
  "options": {
    "include_vocabulary": true,
    "include_collocations": true,
    "include_grammar": true,
    "include_long_sentences": true
  }
}
```

输出：

```json
{
  "difficulty": {
    "absolute_score": 0.71,
    "relative_load": 0.59,
    "dimensions": {
      "lexical": 0.72,
      "syntactic": 0.76,
      "discourse": 0.58,
      "conceptual": 0.61
    }
  },
  "vocabulary_coverage": {
    "known_ratio": 0.93,
    "critical_unknown_count": 7
  },
  "core_vocabulary": [],
  "collocations": [],
  "grammar_points": [],
  "complex_sentences": [],
  "exam_skill_mapping": [],
  "adaptation_recommendation": {
    "required": true,
    "mode": "LONG_SENTENCE_SCAFFOLDING"
  },
  "confidence": 0.89
}
```

---

# 6. 模块二：阅读理解辅导模块

## 6.1 模块定位

阅读理解模块负责：

* 阅读理解选择题训练；
* 七选五训练；
* 阅读策略指导；
* 答案评价；
* 文本证据定位；
* 干扰项分析；
* 理解盲区诊断；
* 同技能变式练习；
* 阅读能力状态更新。

系统不仅判断对错，还必须解释：

1. 正确答案来自哪里；
2. 学生为什么会选错；
3. 错误选项使用了什么干扰机制；
4. 下次应使用什么阅读策略。

---

## 6.2 阅读能力分类

### 6.2.1 阅读理解能力

```text
DETAIL_LOCATION
MAIN_IDEA
BEST_TITLE
WRITING_PURPOSE
INFERENCE
AUTHOR_ATTITUDE
WORD_MEANING_IN_CONTEXT
REFERENCE_RESOLUTION
TEXT_STRUCTURE
EXAMPLE_FUNCTION
SOURCE_OR_GENRE_JUDGMENT
```

### 6.2.2 七选五能力

```text
PARAGRAPH_MAIN_IDEA
PRONOUN_REFERENCE
LEXICAL_COHESION
LOGICAL_CONNECTOR
PARALLEL_STRUCTURE
CHRONOLOGICAL_ORDER
CAUSE_EFFECT
GENERAL_SPECIFIC_RELATION
QUESTION_ANSWER_RELATION
```

---

## 6.3 子任务拆解

### 6.3.1 阅读任务蓝图生成

**工具：**

```text
reading.build_question_blueprint
```

根据以下条件分配题型：

* 文本结构；
* 文章体裁；
* 学生弱项；
* 训练时间；
* 高考阶段；
* 当前练习目标；
* 题目难度。

输出：

```json
{
  "question_distribution": {
    "detail": 2,
    "main_idea": 1,
    "inference": 1,
    "attitude": 0
  },
  "target_paragraphs": [],
  "difficulty_distribution": []
}
```

---

### 6.3.2 阅读理解选择题生成

**工具：**

```text
gaokao.generate_reading_multiple_choice
```

处理逻辑：

1. 确定目标阅读能力；
2. 选择文本证据；
3. 生成题干；
4. 生成正确答案；
5. 生成三个具有区分度的干扰项；
6. 标记干扰项机制；
7. 校验唯一答案；
8. 校验题目难度。

干扰项类型：

```text
NO_TEXT_EVIDENCE
PARTIAL_INFORMATION
OVERGENERALIZATION
OVER_INFERENCE
CONCEPT_SUBSTITUTION
SUBJECT_SUBSTITUTION
CAUSE_EFFECT_REVERSAL
EMOTIONAL_GUESS
BACKGROUND_KNOWLEDGE_OVERRIDE
KEYWORD_MATCHING
```

输出：

```json
{
  "question_type": "INFERENCE",
  "stem": "...",
  "options": {
    "A": "...",
    "B": "...",
    "C": "...",
    "D": "..."
  },
  "correct_option": "B",
  "evidence_spans": [],
  "reasoning_chain": [],
  "distractor_analysis": {
    "A": "无中生有",
    "C": "偷换主体",
    "D": "过度推断"
  }
}
```

---

### 6.3.3 七选五任务生成

**工具：**

```text
gaokao.generate_seven_of_five
```

处理步骤：

1. 分析段落结构；
2. 提取中心句和支撑句；
3. 识别代词、连接词和词汇复现；
4. 选取适合挖空的位置；
5. 生成正确选项；
6. 生成冗余干扰项；
7. 执行选项回填；
8. 校验唯一性；
9. 校验段落逻辑完整性。

**调用边界：**

* 不得只依据词汇重复制造正确选项；
* 必须至少存在语义和逻辑双重证据；
* 回填后必须保持语法和篇章连贯。

---

### 6.3.4 题目质量校验

**工具：**

```text
reading.validate_question_quality
```

校验：

* 是否可回答；
* 是否有唯一答案；
* 是否存在完整证据；
* 干扰项是否合理；
* 题干是否清楚；
* 是否符合目标难度；
* 是否出现超出文本的信息；
* 是否与全国Ⅰ卷题型风格匹配。

未通过校验的题目不得进入：

* 正式测评；
* 模拟考试；
* 分数预测样本。

---

### 6.3.5 学生答案评估

**工具：**

```text
reading.evaluate_answer
```

选择题输出：

* 是否正确；
* 正确答案；
* 学生选项；
* 证据匹配；
* 题型能力标签；
* 预计错因。

简答题评分：

```text
AnswerScore =
  0.45 × key_proposition_coverage
+ 0.25 × evidence_consistency
+ 0.15 × semantic_correctness
+ 0.10 × completeness
+ 0.05 × expression_clarity
```

阅读理解任务中，学生存在轻微语法表达错误时，不得直接判为理解错误。

---

### 6.3.6 阅读干扰项诊断

**工具：**

```text
gaokao.diagnose_reading_distractor
```

输入：

* 原文；
* 题干；
* 正确选项；
* 学生选项；
* 作答时间；
* 学生高亮或定位记录。

输出：

```json
{
  "error_type": "PARTIAL_INFORMATION",
  "student_reasoning_estimate": "学生只关注第二段局部信息",
  "correct_evidence": [],
  "incorrect_option_trap": "局部正确但不能概括全文",
  "recommended_strategy": "比较选项覆盖范围与全文主题"
}
```

---

### 6.3.7 七选五错因诊断

**工具：**

```text
gaokao.diagnose_seven_of_five_gap
```

错误类型：

```text
PRONOUN_REFERENCE_MISSED
CONNECTOR_RELATION_MISREAD
LEXICAL_COHESION_MISSED
PARAGRAPH_FUNCTION_MISREAD
PARALLEL_STRUCTURE_MISSED
LOCAL_MATCH_GLOBAL_CONFLICT
OPTION_REUSE_LOGIC_ERROR
```

---

### 6.3.8 阅读策略诊断

**工具：**

```text
reading.diagnose_strategy_use
```

触发条件：

* 连续两题错误；
* 单题停留时间异常；
* 频繁更改答案；
* 只高亮题干关键词；
* 不返回原文定位；
* 学生主动请求帮助。

识别策略问题：

* 逐词翻译；
* 只看关键词；
* 忽略转折；
* 忽略代词；
* 过度依赖常识；
* 缺乏证据定位；
* 不区分局部信息和全文主旨；
* 推理超过文本边界。

---

### 6.3.9 分层提示生成

**工具：**

```text
reading.generate_progressive_hint
```

提示等级：

1. `STRATEGY_HINT`：提示使用何种方法；
2. `LOCATION_HINT`：提示相关段落；
3. `RELATION_HINT`：提示逻辑关系；
4. `PARTIAL_REASONING_HINT`：提供部分推理；
5. `WORKED_EXPLANATION`：完整讲解。

调用边界：

* 正式测评不得使用完整讲解；
* 前三级不直接泄露答案；
* 查看提示后的正确作答必须降低证据权重。

---

### 6.3.10 理解盲区定位

**工具：**

```text
reading.locate_comprehension_gap
```

盲区分类：

```text
LEXICAL_BLOCK
LONG_SENTENCE_PARSE_FAILURE
REFERENCE_RESOLUTION_FAILURE
DETAIL_OMISSION
MAIN_IDEA_OVERGENERALIZATION
MAIN_IDEA_TOO_NARROW
INFERENCE_CHAIN_BREAK
ATTITUDE_MISREAD
BACKGROUND_KNOWLEDGE_GAP
ANSWER_EXPRESSION_LIMITATION
CARELESS_RESPONSE
```

调用边界：

* 单次错误只能作为当前任务诊断；
* 至少多次同类证据才能形成长期弱项；
* 粗心与能力缺陷必须区分。

---

### 6.3.11 针对性讲解与变式题

**工具：**

```text
reading.explain_comprehension_gap
reading.generate_transfer_item
```

讲解结构：

```text
学生原选择
→ 为什么看似合理
→ 它与原文哪里不一致
→ 正确证据
→ 正确推理过程
→ 可迁移策略
→ 同技能变式题
```

---

## 6.4 对应工具设计

```text
language.score_text_difficulty
  → gaokao.map_text_to_exam_skills
  → reading.build_question_blueprint
  → gaokao.generate_reading_multiple_choice
     或 gaokao.generate_seven_of_five
  → reading.validate_question_quality
  → 学生作答
  → reading.evaluate_answer
  → gaokao.diagnose_reading_distractor
     或 gaokao.diagnose_seven_of_five_gap
  → reading.locate_comprehension_gap
  → reading.generate_progressive_hint
  → reading.generate_transfer_item
  → tracking.update_mastery
```

触发规则：

```json
{
  "rules": [
    {
      "when": "answer.correct == true && hint_count == 0",
      "actions": [
        "tracking.update_mastery"
      ]
    },
    {
      "when": "answer.correct == false",
      "actions": [
        "gaokao.diagnose_reading_distractor",
        "reading.locate_comprehension_gap",
        "reading.generate_progressive_hint"
      ]
    },
    {
      "when": "same_error_type_count >= 2",
      "actions": [
        "reading.explain_comprehension_gap",
        "reading.generate_transfer_item",
        "tracking.create_remediation_task"
      ]
    }
  ]
}
```

---

## 6.5 输入输出规范

输入：

```json
{
  "article_id": "article_001",
  "question_id": "q_001",
  "student_answer": "C",
  "response_time_ms": 86000,
  "hint_count": 0,
  "interaction_trace": {
    "highlighted_spans": [],
    "answer_changes": 1
  }
}
```

输出：

```json
{
  "is_correct": false,
  "correct_option": "B",
  "selected_option": "C",
  "skill": "MAIN_IDEA",
  "error_type": "PARTIAL_INFORMATION",
  "evidence_spans": [],
  "diagnosis": "学生将第二段的局部内容当作全文主旨",
  "recommended_hint_level": 2,
  "mastery_evidence": {
    "knowledge_component_id": "reading.main_idea",
    "evidence_strength": 0.78
  },
  "confidence": 0.9
}
```

---

# 7. 模块三：写作批改与优化模块

## 7.1 模块定位

写作模块分别支持：

```text
PRACTICAL_WRITING
READING_CONTINUATION
```

应用文和读后续写必须使用不同的任务分析和评分逻辑。

系统操作分为：

```text
CORRECTION
IMPROVEMENT
REWRITE
```

默认只进行：

* 明确错误纠正；
* 不改变原意的表达优化。

完整重写必须由学生或教师明确触发。

---

## 7.2 通用写作子任务

### 7.2.1 写作任务解析

**工具：**

```text
writing.parse_task_context
```

识别：

* 写作类型；
* 写作身份；
* 交际对象；
* 写作目的；
* 内容要求；
* 段落要求；
* 字数约束；
* 文体和语域；
* 读后续写段首句约束。

---

### 7.2.2 拼写和词形错误检测

**工具：**

```text
writing.detect_spelling_morphology_errors
```

识别：

* 拼写；
* 大小写；
* 单复数；
* 比较级；
* 过去式和过去分词；
* 派生词；
* 词性误用。

低置信专有名词只标记为疑似问题，不得自动更改。

---

### 7.2.3 语法错误检测

**工具：**

```text
writing.detect_grammar_errors
```

覆盖：

* 主谓一致；
* 时态；
* 语态；
* 冠词；
* 介词；
* 非谓语；
* 从句；
* 代词；
* 语序；
* 标点；
* 句子边界。

调用边界：

* 风格问题不得标记为语法错误；
* 多种形式均正确时返回备选；
* 不能只给正确答案，必须说明规则。

---

### 7.2.4 修正候选排序

**工具：**

```text
writing.rank_correction_candidates
```

排序公式：

```text
CandidateScore =
  0.35 × grammaticality
+ 0.30 × semantic_preservation
+ 0.15 × register_fit
+ 0.10 × minimal_edit
+ 0.10 × learner_level_fit
```

---

### 7.2.5 句式质量分析

**工具：**

```text
writing.analyze_sentence_style
```

识别：

* 句式过度单一；
* 碎片句；
* 逗号连接句；
* 句子过长；
* 重复句首；
* 从句层级失控；
* 不自然的被动语态；
* 机械使用复杂句。

---

### 7.2.6 用词和搭配分析

**工具：**

```text
writing.analyze_lexical_quality
```

识别：

* 重复用词；
* 中式英语；
* 搭配错误；
* 模糊词；
* 语域不当；
* 过度生僻词；
* 词义使用不准确；
* 可迁移高频语块。

调用边界：

* 不为追求所谓高级而替换自然表达；
* 优先保证准确、得体和清楚。

---

### 7.2.7 篇章结构分析

**工具：**

```text
writing.analyze_discourse_structure
```

分析：

* 段落功能；
* 内容要点；
* 信息顺序；
* 逻辑衔接；
* 主题一致；
* 是否存在跳跃；
* 是否存在无关信息；
* 开头和结尾是否完成交际目标。

---

### 7.2.8 原意保护检测

**工具：**

```text
writing.verify_meaning_preservation
```

检测：

```text
NEW_FACT_ADDED
STANCE_INTENSIFIED
STANCE_WEAKENED
NEGATION_CHANGED
ACTOR_CHANGED
TIME_CHANGED
CAUSALITY_CHANGED
CERTAINTY_CHANGED
SCOPE_CHANGED
```

修改出现以下情况时必须阻断自动替换：

* 新增事实；
* 改变人物；
* 改变时间；
* 改变因果；
* 改变情绪或态度；
* 改变事件结果；
* 改变学生原有观点。

---

## 7.3 应用文写作子模块

### 7.3.1 应用文要求检查

**工具：**

```text
gaokao.check_practical_writing_requirements
```

检查：

* 是否覆盖全部内容要点；
* 是否身份正确；
* 是否交际对象正确；
* 是否语气得体；
* 是否完成请求、建议、邀请、感谢等交际目的；
* 是否存在格式问题；
* 是否加入大量无关信息；
* 是否超出题目设定。

输出：

```json
{
  "covered_requirements": [],
  "missing_requirements": [],
  "register_issues": [],
  "format_issues": [],
  "task_completion_score": 0.72
}
```

---

### 7.3.2 应用文评分

**工具：**

```text
gaokao.score_practical_writing
```

评分维度：

* 内容要点覆盖；
* 交际目的达成；
* 对象和语域；
* 信息组织；
* 语言准确性；
* 词汇和句式；
* 连贯衔接；
* 格式和字数约束。

正式评分必须返回：

* 各维度分；
* 评分依据；
* 原文证据；
* 置信度；
* 分数区间。

---

## 7.4 读后续写子模块

### 7.4.1 原文故事解析

**工具：**

```text
gaokao.parse_continuation_story
```

提取：

* 人物；
* 人物关系；
* 时间；
* 地点；
* 核心冲突；
* 人物目标；
* 情绪曲线；
* 关键物品；
* 伏笔；
* 未解决问题；
* 两个段落首句；
* 原文不可改变的事实。

---

### 7.4.2 续写情节规划

**工具：**

```text
gaokao.plan_continuation_plot
```

输出：

```json
{
  "paragraph_1": {
    "goal": "推进冲突并形成转折",
    "required_events": [],
    "emotion_curve": [
      "anxious",
      "surprised",
      "hopeful"
    ],
    "bridge_to_next_paragraph": "..."
  },
  "paragraph_2": {
    "goal": "解决冲突并完成主题收束",
    "required_events": [],
    "theme_resolution": "..."
  }
}
```

调用边界：

* 不自动替学生生成完整故事；
* 默认只给情节骨架、问题提示和局部语言支架；
* 学生明确请求范文时才允许生成示例文本。

---

### 7.4.3 续写一致性检查

**工具：**

```text
gaokao.verify_continuation_consistency
```

检查：

* 与原文人物设定是否一致；
* 与段首句是否衔接；
* 人物行为是否合理；
* 时间和地点是否冲突；
* 情节是否跳跃；
* 伏笔是否得到合理使用；
* 结局是否过度突兀；
* 是否新增无法解释的关键人物或事实。

---

### 7.4.4 读后续写评分

**工具：**

```text
gaokao.score_reading_continuation
```

评分维度：

* 原文内容一致性；
* 段首句衔接；
* 情节合理性；
* 情节完整性；
* 人物和情绪发展；
* 主题一致；
* 语言准确；
* 表达丰富；
* 篇章连贯。

---

## 7.5 逐句批注与整体反馈

### 7.5.1 逐句批注

**工具：**

```text
writing.generate_sentence_annotations
```

每句输出：

```text
原句
→ 错误或问题
→ 中文解释
→ 最小修改
→ 可选优化
→ 原意保持分
```

### 7.5.2 整体提升建议

**工具：**

```text
writing.generate_global_feedback
```

输出限制：

* 先指出具体优点；
* 最多提供三个优先改进点；
* 区分“必须修正”和“可选优化”；
* 给出下一次可执行练习；
* 不一次展示所有低价值问题。

---

## 7.6 推荐“双稿制”流程

```text
学生提交第一稿
→ 保存自然表现证据
→ 检测问题
→ 先提示学生自改
→ 显示最小修正
→ 学生提交第二稿
→ 比较两稿
→ 评价迁移效果
→ 更新掌握状态
```

证据更新规则：

* 第一稿反映自然能力；
* 第二稿反映学习迁移；
* 有提示的第二稿按提示等级降低权重；
* 系统生成范文不能作为学生掌握证据。

---

## 7.7 对应工具设计

应用文流程：

```text
writing.parse_task_context
  → gaokao.check_practical_writing_requirements
  → writing.detect_spelling_morphology_errors
  → writing.detect_grammar_errors
  → writing.analyze_sentence_style
  → writing.analyze_lexical_quality
  → writing.analyze_discourse_structure
  → writing.verify_meaning_preservation
  → writing.generate_sentence_annotations
  → gaokao.score_practical_writing
  → writing.generate_global_feedback
```

续写流程：

```text
gaokao.parse_continuation_story
  → gaokao.plan_continuation_plot
  → 学生写作
  → gaokao.verify_continuation_consistency
  → writing.detect_grammar_errors
  → writing.analyze_lexical_quality
  → writing.verify_meaning_preservation
  → gaokao.score_reading_continuation
  → writing.generate_sentence_annotations
  → writing.generate_global_feedback
```

---

## 7.8 输入输出规范

输入：

```json
{
  "writing_type": "PRACTICAL_WRITING",
  "prompt": "...",
  "student_text": "...",
  "exam_profile_id": "exam_2027_gd_national_1",
  "feedback_options": {
    "mode": "DEEP_REVIEW",
    "preserve_meaning": true,
    "allow_full_rewrite": false,
    "explanation_language": "zh-CN"
  }
}
```

输出：

```json
{
  "task_completion": {
    "covered_requirements": [],
    "missing_requirements": []
  },
  "sentence_annotations": [],
  "global_feedback": {
    "strengths": [],
    "priority_improvements": []
  },
  "scores": {
    "content": 0.75,
    "organization": 0.68,
    "grammar": 0.62,
    "vocabulary": 0.66,
    "coherence": 0.71
  },
  "meaning_preservation": 0.95,
  "confidence": 0.9
}
```

---

# 8. 模块四：听说联动与口语表达训练模块

## 8.1 模块定位

该模块包含两部分：

1. 高考听力训练；
2. 促进英语自动化表达的口语训练。

听力是高考能力模块，口语训练主要服务于：

* 辨音；
* 语块自动化；
* 听力反应速度；
* 长句意群切分；
* 写作素材口头组织；
* 读后续写复述；
* 英语表达流畅度。

除非学生所在省份存在独立听说考试或口试，口语成绩不得直接折算为高考总分预测。

---

## 8.2 听力训练子任务

### 8.2.1 听力任务生成

**工具：**

```text
listening.generate_gaokao_task
```

输入：

* 目标场景；
* 目标题型；
* 学生水平；
* 听力文本长度；
* 语速；
* 干扰项类型；
* 当前考试配置。

题型能力：

```text
DETAIL_LISTENING
MAIN_IDEA_LISTENING
SPEAKER_RELATION
LOCATION_JUDGMENT
PURPOSE_JUDGMENT
ATTITUDE_JUDGMENT
NUMBER_AND_TIME
INFERENCE_LISTENING
```

---

### 8.2.2 音频特征分析

**工具：**

```text
listening.transcribe_audio_features
```

提取：

* 词级时间戳；
* 重音信息；
* 同义替换；
* 转折位置；
* 数字时间表达；
* 干扰信息；
* 说话人变化；
* 关键信息密度。

---

### 8.2.3 听力答案评价

**工具：**

```text
listening.evaluate_answer
```

输出：

* 对错；
* 正确证据的时间区间；
* 同义替换；
* 学生遗漏的信息；
* 干扰项来源。

---

### 8.2.4 听力错因诊断

**工具：**

```text
listening.diagnose_distractor
```

错误类型：

```text
NUMBER_OR_TIME_MISHEARD
LOCATION_MISHEARD
IDENTITY_CONFUSION
ATTITUDE_MISREAD
PURPOSE_MISREAD
DISTRACTOR_CAPTURED
TURNING_POINT_MISSED
SYNONYM_NOT_RECOGNIZED
INFERENCE_FAILURE
NOTE_TAKING_FAILURE
```

---

### 8.2.5 听力证据定位

**工具：**

```text
listening.locate_evidence
```

输出：

* 证据开始时间；
* 证据结束时间；
* 原音频表达；
* 题目表达；
* 同义转换说明；
* 干扰项出现时间。

---

### 8.2.6 听力支架调整

**工具：**

```text
listening.adjust_playback_support
```

支架方式：

* 正常播放；
* 分段播放；
* 降速播放；
* 显示关键词；
* 显示问题预测；
* 播放后显示部分文本；
* 完整精听复盘。

正式测评模式下不得使用降速或文本提示。

---

## 8.3 口语表达训练子任务

### 8.3.1 话题生成

**工具：**

```text
speaking.generate_topic
```

话题来源：

* 高中教材主题语境；
* 阅读文章；
* 应用文写作主题；
* 读后续写情节；
* 校园生活；
* 社会与文化；
* 人与自然；
* 人与社会；
* 人与自我。

---

### 8.3.2 场景生成

**工具：**

```text
speaking.generate_scenario
```

输出：

```json
{
  "scenario_id": "scn_school_activity_001",
  "setting": "school_club",
  "learner_role": "student_organizer",
  "agent_role": "exchange_student",
  "goal": "introduce a school activity",
  "required_functions": [
    "describe_activity",
    "give_time_and_place",
    "invite_participation"
  ],
  "difficulty": 0.58
}
```

---

### 8.3.3 对话回合规划

**工具：**

```text
speaking.plan_next_turn
```

根据：

* 对话目标完成度；
* 学生回答长度；
* 语法准确度；
* 提示依赖；
* 学习目标；
* 最近错误。

选择：

* 追问；
* 澄清；
* 提供支架；
* 增加条件；
* 降低难度；
* 结束任务。

系统默认不在每一句后打断纠错。

---

### 8.3.4 音频质量检测

**工具：**

```text
speaking.check_audio_quality
```

检测：

* 信噪比；
* 音量；
* 削波；
* 静音比例；
* 多人说话；
* 音频截断。

音频质量不合格时，不得输出精确发音分。

---

### 8.3.5 语音转写与对齐

**工具：**

```text
speaking.transcribe_and_align
```

输出：

* 转写；
* ASR 置信度；
* 词级时间戳；
* 音素级对齐；
* 低置信片段；
* 候选转写。

低置信转写不得直接进入语法扣分。

---

### 8.3.6 发音评分

**工具：**

```text
speaking.score_pronunciation
```

评价：

* 音素准确性；
* 单词重音；
* 句子重音；
* 意群；
* 连读；
* 弱读；
* 语调。

反馈每轮最多选择 1—3 个最影响理解或最具迁移价值的问题。

---

### 8.3.7 流利度评分

**工具：**

```text
speaking.score_fluency
```

特征：

```text
speech_rate
articulation_rate
mean_length_of_run
silent_pause_ratio
filled_pause_rate
repair_rate
pause_boundary_accuracy
```

语速快不等于流利。必须结合：

* 停顿位置；
* 语义完整性；
* 自我修正；
* 表达连贯度。

---

### 8.3.8 词汇、语法和互动评分

工具：

```text
speaking.score_lexical_richness
speaking.score_spoken_grammar
speaking.score_interaction
```

调用边界：

* 短回答不输出稳定词汇丰富度分；
* 自然口语省略不能按书面语错误处理；
* 单轮独白不输出互动能力分；
* ASR 低置信词不判定语法错误。

---

### 8.3.9 口语反馈聚合

**工具：**

```text
speaking.aggregate_feedback
```

输出：

* 做得好的表达；
* 一个主要发音问题；
* 一个主要语言问题；
* 一个可复用语块；
* 下一轮任务目标。

---

## 8.4 渐进式口语陪练流程

### 阶段一：跟读与模仿

```text
播放示范
→ 学生跟读
→ 音素和意群对齐
→ 反馈关键问题
→ 再次跟读
```

### 阶段二：句型替换

```text
提供句型
→ 替换人物、时间、地点或原因
→ 检测结构
→ 减少提示
```

### 阶段三：半开放表达

```text
给出问题
→ 学生自由回答
→ Agent 追问
→ 回合结束后反馈
```

### 阶段四：任务型对话

```text
设置交际目标
→ 多轮交流
→ 加入意外条件
→ 判断是否完成任务
```

### 阶段五：阅读和写作迁移

```text
复述阅读文章
→ 口头概括主旨
→ 口头规划应用文
→ 复述续写情节
→ 转化为书面表达
```

升级条件：

```text
最近三次任务完成度 ≥ 0.80
且目标语言准确率 ≥ 0.75
且提示依赖率 ≤ 0.30
```

---

## 8.5 对应工具设计

听力流程：

```text
listening.generate_gaokao_task
  → 学生听音作答
  → listening.evaluate_answer
  → listening.locate_evidence
  → listening.diagnose_distractor
  → listening.adjust_playback_support
  → tracking.update_mastery
```

口语流程：

```text
speaking.generate_topic
  → speaking.generate_scenario
  → speaking.plan_next_turn
  → speaking.check_audio_quality
  → speaking.transcribe_and_align
  → speaking.score_pronunciation
  → speaking.score_fluency
  → speaking.score_lexical_richness
  → speaking.score_spoken_grammar
  → speaking.score_interaction
  → speaking.aggregate_feedback
  → speaking.adjust_practice_difficulty
```

---

## 8.6 输入输出规范

输入：

```json
{
  "audio_uri": "storage://audio/session001/turn03.wav",
  "scenario_id": "scn_school_activity_001",
  "learner_profile": {
    "grade": 11,
    "speaking_ability": 0.56
  },
  "feedback_mode": "END_OF_TURN"
}
```

输出：

```json
{
  "transcript": {
    "text": "...",
    "confidence": 0.91
  },
  "scores": {
    "pronunciation": 0.73,
    "fluency": 0.68,
    "lexical_richness": 0.61,
    "grammar_accuracy": 0.7,
    "interaction": 0.82
  },
  "priority_feedback": [],
  "next_turn_plan": {
    "agent_intent": "ASK_FOR_EXAMPLE",
    "difficulty_change": 0.04,
    "provide_hint": false
  },
  "confidence": 0.86
}
```

---

# 9. 模块五：学习追踪与复习模块

## 9.1 模块定位

该模块将阅读、七选五、完形、语法填空、写作、听力和口语表现统一为长期学习状态。

系统同时维护：

1. 词汇和语法知识掌握状态；
2. 阅读、听力、写作子技能状态；
3. 高考题型能力状态；
4. 错误模式；
5. 复习到期状态；
6. 时间管理表现；
7. 预计分数区间；
8. 学习计划完成情况。

---

## 9.2 子任务拆解

### 9.2.1 学习证据标准化

**工具：**

```text
tracking.normalize_learning_evidence
```

将不同任务统一映射为：

* 知识点；
* 技能；
* 题型；
* 得分；
* 难度；
* 提示依赖；
* 响应时间；
* 是否独立完成；
* 证据置信度。

无明确知识点映射的任务只能更新综合任务表现，不能修改具体知识点掌握度。

---

### 9.2.2 知识点与技能归因

**工具：**

```text
tracking.attribute_evidence_to_skills
```

例如一道语法填空题可能同时涉及：

* 非谓语动词；
* 主被动关系；
* 句子成分识别；
* 语境判断。

系统需要分配不同证据权重，而不是只更新一个标签。

---

### 9.2.3 动态掌握度更新

**工具：**

```text
tracking.update_mastery
```

基础更新：

```text
P(L | correct) =
  P(correct | L) × P(L)
  --------------------------------
  P(correct | L) × P(L)
  + P(correct | not L) × P(not L)
```

学习转移：

```text
P(L_next) =
  P(L | observation)
  + [1 - P(L | observation)] × P(learn)
```

有效证据：

```text
EffectiveEvidence =
  RawScore
× IndependenceWeight
× ItemDiagnosticity
× Confidence
```

提示权重：

| 作答状态      |   权重 |
| --------- | ---: |
| 独立完成      | 1.00 |
| 策略提示后完成   | 0.80 |
| 定位提示后完成   | 0.65 |
| 部分答案提示后完成 | 0.35 |
| 看完整答案后模仿  | 0.15 |

调用边界：

* 单次粗心错误不能大幅降低掌握度；
* 查看完整答案后的正确作答不能视为真正掌握；
* 自动生成范文不产生学生掌握证据；
* 相同题目重复作答需要降低证据权重。

---

### 9.2.4 错误模式聚类

**工具：**

```text
tracking.cluster_error_patterns
```

聚类维度：

* 错误类型；
* 知识点；
* 题型；
* 文章体裁；
* 作答时间；
* 是否存在时间压力；
* 是否反复出现；
* 是否能在提示后修正。

输出：

```json
{
  "stable_patterns": [],
  "occasional_errors": [],
  "possible_carelessness": [],
  "transfer_failures": []
}
```

---

### 9.2.5 遗忘风险估计

**工具：**

```text
tracking.estimate_forgetting_risk
```

基础模型：

```text
RecallProbability(t) = exp(-t / Stability)
```

影响因素：

* 距上次复习时间；
* 历史成功次数；
* 历史失败次数；
* 作答独立程度；
* 知识点难度；
* 任务迁移情况；
* 最近使用频率。

---

### 9.2.6 复习计划调度

**工具：**

```text
tracking.schedule_gaokao_review
```

优先级：

```text
Priority =
  0.25 × expected_score_gain
+ 0.20 × weakness_severity
+ 0.15 × forgetting_risk
+ 0.15 × exam_relevance
+ 0.10 × recurrence
+ 0.10 × prerequisite_importance
+ 0.05 × time_urgency
```

复习任务需要平衡：

* 到期复习；
* 当前课程内容；
* 高考重点题型；
* 学生弱项；
* 新知识学习；
* 考试临近程度。

---

### 9.2.7 复习任务生成

**工具：**

```text
tracking.generate_review_task
```

任务层级：

1. 识别；
2. 提取；
3. 语境应用；
4. 高考题型应用；
5. 写作或口语迁移。

例如词汇复习不能只生成中英互译，还应包括：

* 熟词生义；
* 语境判断；
* 搭配选择；
* 阅读同义替换；
* 写作输出。

---

### 9.2.8 高考失分分析

**工具：**

```text
gaokao.analyze_score_loss
```

分类：

```text
KNOWLEDGE_GAP
READING_SKILL_GAP
WRITING_SKILL_GAP
CARELESSNESS
TIME_PRESSURE
STRATEGY_ERROR
FORMAT_VIOLATION
TASK_MISUNDERSTANDING
```

调用边界：

* 错误不能全部归因于知识不会；
* 学生在限时条件下错误，但不限时能答对时，应优先标记时间或自动化问题；
* 多次无提示错误才可确认为稳定知识缺口。

---

### 9.2.9 时间分配分析

**工具：**

```text
gaokao.analyze_time_allocation
```

分析：

* 每部分耗时；
* 单题异常停留；
* 提前提交；
* 未完成题目；
* 答案修改次数；
* 正确率与耗时关系；
* 作文规划时间；
* 读后续写未完成风险。

---

### 9.2.10 分项成绩预测

**工具：**

```text
gaokao.predict_section_scores
```

预测前置条件：

* 至少两次独立训练；
* 题型一致；
* 题目难度经过校准；
* 无答案泄露；
* 有足够样本；
* 有近期数据。

输出必须使用区间：

```json
{
  "predicted_total_score": {
    "value": 108,
    "confidence_interval": [
      101,
      115
    ]
  },
  "section_predictions": {},
  "confidence": 0.76
}
```

不得只给单点分数，不得根据一次考试推断稳定水平。

---

### 9.2.11 语言能力画像构建

**工具：**

```text
tracking.build_language_profile
```

输出：

* 高考分项能力；
* 阅读子技能；
* 听力子技能；
* 写作子技能；
* 稳定知识点；
* 不稳定知识点；
* 错误模式；
* 预计可提分点；
* 数据充分度；
* 置信区间。

---

### 9.2.12 阶段报告生成

**工具：**

```text
tracking.generate_stage_report
```

学生版报告：

* 本阶段完成内容；
* 得分变化；
* 主要进步；
* 最重要弱项；
* 下阶段任务；
* 可执行建议。

教师版报告增加：

* 班级对比；
* 知识点共性错误；
* 题型失分分布；
* 学生分层；
* 作业建议；
* 教师干预建议；
* 数据充分度。

---

## 9.3 对应工具设计

状态更新：

```text
业务评分工具
  → tracking.normalize_learning_evidence
  → tracking.attribute_evidence_to_skills
  → tracking.update_mastery
  → tracking.cluster_error_patterns
  → tracking.estimate_forgetting_risk
  → tracking.schedule_gaokao_review
```

每日计划：

```text
tracking.get_due_reviews
  → tracking.get_recent_error_patterns
  → gaokao.analyze_score_loss
  → tracking.schedule_gaokao_review
  → tracking.generate_review_task
  → planning.compose_daily_session
```

阶段报告：

```text
tracking.build_language_profile
  → gaokao.predict_section_scores
  → gaokao.analyze_time_allocation
  → tracking.generate_stage_report
  → Quality Guard Agent 校验
```

---

## 9.4 输入输出规范

输入：

```json
{
  "learner_id": "stu_001",
  "knowledge_component_id": "grammar.en.non_finite.participle",
  "current_state": {
    "mastery_probability": 0.62,
    "stability_days": 4.2
  },
  "evidence": {
    "task_type": "GRAMMAR_FILLING",
    "score": 0.85,
    "item_difficulty": 0.66,
    "independence_level": "STRATEGY_HINT",
    "response_time_ms": 15000,
    "confidence": 0.93
  }
}
```

输出：

```json
{
  "knowledge_component_id": "grammar.en.non_finite.participle",
  "previous_mastery_probability": 0.62,
  "updated_mastery_probability": 0.69,
  "previous_stability_days": 4.2,
  "updated_stability_days": 5.1,
  "next_review_at": "2026-08-03T09:00:00+08:00",
  "update_reasons": [
    "CORRECT_RESPONSE",
    "MODERATE_ITEM_DIFFICULTY",
    "LOW_HINT_DEPENDENCY"
  ],
  "confidence": 0.88
}
```

---

# 10. 首次能力测评初始化工作流

## 10.1 初始化目标

首次测评应建立：

* 当前高考总分区间；
* 各题型能力；
* 阅读子技能；
* 听力子技能；
* 词汇和语法基础；
* 应用文基础；
* 读后续写基础；
* 时间管理基线；
* 稳定强项；
* 优先薄弱项；
* 第一阶段学习计划；
* 初始复习队列。

---

## 10.2 阶段一：基本信息采集

采集：

* 年级；
* 省份；
* 高考年份；
* 教材版本；
* 最近三次英语成绩；
* 当前目标分；
* 校内教学进度；
* 每日学习时间；
* 是否支持音频；
* 是否存在特殊考试安排。

工具链：

```text
exam.resolve_paper_profile
→ profile.validate_preferences
→ tracking.initialize_learner_profile
```

---

## 10.3 阶段二：快速筛选

工具：

```text
assessment.generate_screening_items
assessment.score_screening
assessment.initialize_ability_prior
```

筛选内容：

* 基础词汇；
* 核心语法；
* 短篇阅读；
* 简单七选五；
* 基础写作判断。

输出：

```json
{
  "ability_prior": {
    "mean": 0.15,
    "standard_error": 0.72,
    "candidate_score_band": [
      85,
      110
    ]
  }
}
```

---

## 10.4 阶段三：自适应词汇和语法测评

循环：

```text
assessment.select_next_item
→ 学生作答
→ assessment.score_item
→ assessment.update_ability
→ assessment.check_stop_condition
```

选题依据：

* 题目难度接近当前能力；
* 尚未测量的知识点；
* 高考高频知识；
* 具有区分度的知识点；
* 前置知识关系。

终止条件：

* 标准误差达到阈值；
* 达到最大题量；
* 学生疲劳；
* 题目区分度不足；
* 学生主动结束。

---

## 10.5 阶段四：阅读与七选五测评

流程：

```text
language.score_text_difficulty
→ gaokao.generate_reading_multiple_choice
→ gaokao.generate_seven_of_five
→ reading.validate_question_quality
→ 学生限时作答
→ reading.evaluate_answer
→ gaokao.diagnose_reading_distractor
→ assessment.estimate_reading_subskills
```

测评模式：

* 禁止完整提示；
* 记录作答时间；
* 记录答案修改；
* 记录证据定位；
* 记录是否只凭关键词选择。

---

## 10.6 阶段五：完形和语法填空测评

需要诊断：

* 语境词义；
* 搭配；
* 篇章逻辑；
* 代词；
* 冠词；
* 介词；
* 时态语态；
* 非谓语；
* 从句；
* 词性转换。

工具链：

```text
assessment.generate_cloze_items
→ assessment.generate_grammar_filling_items
→ assessment.score_item
→ tracking.attribute_evidence_to_skills
```

---

## 10.7 阶段六：应用文测评

流程：

```text
assessment.generate_practical_writing_prompt
→ 学生独立写作
→ gaokao.check_practical_writing_requirements
→ writing.detect_grammar_errors
→ writing.analyze_discourse_structure
→ gaokao.score_practical_writing
```

首次正式测评时，写作过程中不提供实时纠错。

---

## 10.8 阶段七：读后续写测评

流程：

```text
assessment.select_continuation_prompt
→ gaokao.parse_continuation_story
→ 学生独立写作
→ gaokao.verify_continuation_consistency
→ gaokao.score_reading_continuation
```

测量：

* 原文理解；
* 情节规划；
* 人物一致性；
* 语言表达；
* 篇章连贯；
* 完成时间。

---

## 10.9 阶段八：听力测评

流程：

```text
listening.generate_gaokao_task
→ 学生作答
→ listening.evaluate_answer
→ listening.diagnose_distractor
→ assessment.estimate_listening_subskills
```

若当前设备或环境不支持音频：

```json
{
  "listening_status": "NOT_ASSESSED",
  "reason": "AUDIO_UNAVAILABLE"
}
```

不得根据阅读或口语文本推断听力水平。

---

## 10.10 阶段九：画像初始化

```text
tracking.normalize_learning_evidence
→ tracking.attribute_evidence_to_skills
→ tracking.update_mastery
→ tracking.build_language_profile
→ gaokao.predict_section_scores
→ planning.generate_initial_learning_plan
→ tracking.schedule_gaokao_review
```

首次画像输出：

```json
{
  "current_score_band": "95-110",
  "target_score": 125,
  "stable_strengths": [
    "READING_DETAIL_LOCATION"
  ],
  "priority_gaps": [
    {
      "skill": "READING_INFERENCE",
      "confidence": 0.84
    },
    {
      "skill": "SEVEN_OF_FIVE_LOGICAL_COHESION",
      "confidence": 0.81
    },
    {
      "skill": "CONTINUATION_PLOT_COHERENCE",
      "confidence": 0.76
    }
  ],
  "recommended_plan": {
    "foundation_ratio": 0.3,
    "exam_drill_ratio": 0.45,
    "review_ratio": 0.25
  }
}
```

---

# 11. 日常训练迭代工作流

## 11.1 每日会话初始化

```text
exam.resolve_paper_profile
→ tracking.get_due_reviews
→ tracking.get_recent_error_patterns
→ tracking.build_language_profile
→ planning.compose_daily_session
```

推荐初始配比：

```text
40% 到期复习
35% 当前主目标训练
15% 薄弱项补救
10% 兴趣阅读或自主选择
```

系统根据以下因素动态调整：

* 距离高考时间；
* 当前年级；
* 最近考试；
* 到期复习量；
* 教师任务；
* 当日可用时间；
* 最近疲劳度；
* 最近完成率。

---

## 11.2 阅读日常训练

```text
选择文章
→ 语言分析
→ 判断难度
→ 必要时提供词汇或长难句支架
→ 生成阅读题
→ 学生作答
→ 判断对错
→ 干扰项诊断
→ 提示或讲解
→ 同技能变式题
→ 更新掌握状态
→ 安排复习
```

触发规则：

| 条件        | 系统动作       |
| --------- | ---------- |
| 相对负荷高     | 增加词汇和长难句支架 |
| 事实题错误     | 训练证据定位     |
| 主旨题选择局部信息 | 对比全文与局部信息  |
| 推理题连续错误   | 显式展示推理链    |
| 态度题错误     | 标记评价词和情态表达 |
| 熟词生义导致错误  | 创建词义复习任务   |
| 同类错误重复    | 生成专项补救任务   |

---

## 11.3 七选五日常训练

```text
分析全文结构
→ 学生先判断段落功能
→ 完成选项
→ 诊断错误
→ 标记衔接线索
→ 重新排序和回填
→ 生成同类变式题
```

重点训练：

* 先看段落功能；
* 再看逻辑关系；
* 再看代词和词汇复现；
* 最后检查全文一致性。

---

## 11.4 写作日常训练

```text
审题
→ 提取内容要求
→ 学生完成第一稿
→ 系统诊断
→ 学生自改
→ 系统提供最小修改
→ 学生完成第二稿
→ 两稿对比
→ 更新知识状态
```

应用文触发：

* 遗漏要点时，下一次强制使用审题清单；
* 语气不当时，增加交际对象训练；
* 格式错误时，创建低频短复习，不应大量占用时间。

续写触发：

* 情节偏离时，先训练人物、冲突和伏笔抽取；
* 段首句衔接差时，先要求写每段第一句后的事件目标；
* 语言正确但情节薄弱时，不应只推送语法练习。

---

## 11.5 听力日常训练

```text
听前预测
→ 第一遍完整听
→ 学生作答
→ 第二遍证据定位
→ 分析同义替换和干扰项
→ 精听关键片段
→ 复述或跟读
→ 更新听力状态
```

---

## 11.6 口语辅助训练

```text
阅读或写作主题输入
→ 口头复述
→ Agent 追问
→ 记录表达问题
→ 回合结束反馈
→ 重说关键句
→ 将口头内容迁移为写作表达
```

---

## 11.7 会话结束更新

```text
收集全部任务证据
→ 标准化
→ 知识点和技能归因
→ 更新掌握度
→ 更新错误模式
→ 计算遗忘风险
→ 更新复习队列
→ 生成学习摘要
```

摘要内容：

* 今日完成内容；
* 两个以内主要进步；
* 一个最优先问题；
* 新增复习项目；
* 下次建议；
* 当前目标完成进度。

---

# 12. 周期性训练与模拟考试

## 12.1 训练周期

| 周期     | 任务            |
| ------ | ------------- |
| 每日     | 短时复习和专项训练     |
| 每周     | 题型组合训练        |
| 每两至四周  | 阶段能力诊断        |
| 月度或阶段末 | 限时整卷模拟        |
| 考前     | 稳定性、时间和高频错误训练 |

## 12.2 模拟考试流程

```text
加载试卷配置
→ 锁定正式测评模式
→ 全程记录时间
→ 禁用教学提示
→ 完成试卷
→ 自动评分和人工评分接口
→ 失分结构分析
→ 时间结构分析
→ 错误模式更新
→ 预测分更新
→ 生成下一阶段计划
```

## 12.3 模考后分析

必须区分：

* 知识不会；
* 策略错误；
* 阅读证据定位失败；
* 写作任务理解错误；
* 时间压力；
* 粗心；
* 题目异常；
* 偶发波动。

单次模考下降不直接判定能力退步。

---

# 13. Agent 调用与触发规则

## 13.1 意图路由

| 学生请求          | 首选 Agent                | 必要工具                             |
| ------------- | ----------------------- | -------------------------------- |
| “帮我分析这篇阅读”    | Reading Tutor Agent     | 语言分析工具                           |
| “这篇文章适合高考训练吗” | Language Analysis Agent | `gaokao.map_text_to_exam_skills` |
| “为什么这题选B”     | Reading Tutor Agent     | 阅读答案和干扰项诊断                       |
| “帮我改应用文”      | Writing Coach Agent     | 应用文要求检查和评分                       |
| “帮我看读后续写”     | Writing Coach Agent     | 故事解析和一致性校验                       |
| “陪我练听力”       | Listening Coach Agent   | 听力生成和评价工具                        |
| “陪我练口语”       | Speaking Coach Agent    | 场景和语音分析工具                        |
| “我该复习什么”      | Review Scheduler Agent  | 失分分析和复习调度                        |
| “我现在大概多少分”    | Learner Model Agent     | 分项预测工具                           |
| “生成阶段报告”      | Learner Model Agent     | 能力画像和报告工具                        |

---

## 13.2 强制工具调用规则

| 结论         | 强制工具                                  |
| ---------- | ------------------------------------- |
| 材料是否适合全国Ⅰ卷 | `gaokao.map_text_to_exam_skills`      |
| 文章对学生是否过难  | `language.score_text_difficulty`      |
| 阅读答案是否正确   | `reading.evaluate_answer`             |
| 阅读为什么选错    | `gaokao.diagnose_reading_distractor`  |
| 七选五错因      | `gaokao.diagnose_seven_of_five_gap`   |
| 应用文分数      | `gaokao.score_practical_writing`      |
| 续写分数       | `gaokao.score_reading_continuation`   |
| 修改是否改变原意   | `writing.verify_meaning_preservation` |
| 发音分数       | `speaking.score_pronunciation`        |
| 听力错因       | `listening.diagnose_distractor`       |
| 知识点是否掌握    | `tracking.update_mastery`             |
| 应何时复习      | `tracking.schedule_gaokao_review`     |
| 当前预计分数     | `gaokao.predict_section_scores`       |

---

## 13.3 置信度规则

```text
confidence ≥ 0.85
可直接展示，并作为正常权重更新状态。

0.65 ≤ confidence < 0.85
展示不确定性，状态更新采用折扣权重。

confidence < 0.65
不进行高影响状态更新；
请求补充证据；
或返回保守结论。
```

---

# 14. 工具接口目录

## 14.1 考试配置

```text
exam.resolve_paper_profile
exam.validate_task_against_profile
```

## 14.2 语言解析

```text
language.detect_and_normalize
language.annotate_linguistic_features
language.score_text_difficulty
language.extract_core_vocabulary
language.extract_collocations
language.extract_grammar_points
language.adapt_content
gaokao.analyze_vocabulary_requirements
gaokao.analyze_long_complex_sentences
gaokao.map_text_to_exam_skills
```

## 14.3 阅读和七选五

```text
reading.build_question_blueprint
gaokao.generate_reading_multiple_choice
gaokao.generate_seven_of_five
reading.validate_question_quality
reading.evaluate_answer
gaokao.diagnose_reading_distractor
gaokao.diagnose_seven_of_five_gap
reading.diagnose_strategy_use
reading.generate_progressive_hint
reading.locate_comprehension_gap
reading.explain_comprehension_gap
reading.generate_transfer_item
```

## 14.4 写作

```text
writing.parse_task_context
writing.detect_spelling_morphology_errors
writing.detect_grammar_errors
writing.rank_correction_candidates
writing.analyze_sentence_style
writing.analyze_lexical_quality
writing.analyze_discourse_structure
writing.verify_meaning_preservation
writing.generate_sentence_annotations
writing.generate_global_feedback
gaokao.check_practical_writing_requirements
gaokao.score_practical_writing
gaokao.parse_continuation_story
gaokao.plan_continuation_plot
gaokao.verify_continuation_consistency
gaokao.score_reading_continuation
```

## 14.5 听力与口语

```text
listening.generate_gaokao_task
listening.transcribe_audio_features
listening.evaluate_answer
listening.locate_evidence
listening.diagnose_distractor
listening.analyze_note_taking
listening.adjust_playback_support
speaking.generate_topic
speaking.generate_scenario
speaking.plan_next_turn
speaking.check_audio_quality
speaking.transcribe_and_align
speaking.score_pronunciation
speaking.score_fluency
speaking.score_lexical_richness
speaking.score_spoken_grammar
speaking.score_interaction
speaking.aggregate_feedback
speaking.adjust_practice_difficulty
```

## 14.6 学习追踪

```text
tracking.normalize_learning_evidence
tracking.attribute_evidence_to_skills
tracking.update_mastery
tracking.cluster_error_patterns
tracking.estimate_forgetting_risk
tracking.schedule_gaokao_review
tracking.generate_review_task
tracking.build_language_profile
tracking.generate_stage_report
gaokao.analyze_score_loss
gaokao.analyze_time_allocation
gaokao.predict_section_scores
```

---

# 15. 非功能性要求

## 15.1 性能要求

| 操作        |   建议 P95 延迟 |
| --------- | ----------: |
| 文本预处理     |    ≤ 300 ms |
| 单句语言标注    |    ≤ 500 ms |
| 1000词文章分析 |       ≤ 2 s |
| 阅读题答案评价   |     ≤ 1.5 s |
| 阅读错因诊断    |       ≤ 2 s |
| 写作快速纠错    |       ≤ 3 s |
| 写作深度分析    |       ≤ 8 s |
| ASR 转写    | 音频结束后 ≤ 2 s |
| 口语综合反馈    |       ≤ 5 s |
| 掌握度更新     |    ≤ 300 ms |
| 每日学习计划    |       ≤ 1 s |

## 15.2 可观测性

每次工具调用记录：

```json
{
  "request_id": "req_001",
  "tool_name": "reading.evaluate_answer",
  "model_version": "v3.2",
  "prompt_version": "reading_eval_17",
  "latency_ms": 842,
  "input_tokens": 1200,
  "output_tokens": 240,
  "confidence": 0.88,
  "fallback_used": false,
  "error_code": null
}
```

## 15.3 隐私要求

* 学生身份与学习内容分库存储；
* 语音和作文设置可配置保存周期；
* 教师只能访问授权班级；
* 模型训练使用学生内容必须取得独立授权；
* 不推断学生人格、心理疾病或家庭状况；
* 阶段报告不得使用侮辱性、标签化表达。

## 15.4 教师覆盖机制

教师可覆盖：

* 题目答案；
* 文章难度；
* 作文评分；
* 目标知识点；
* 复习优先级；
* 学习任务；
* 错误归因。

覆盖记录：

```json
{
  "override_id": "ovr_001",
  "teacher_id": "teacher_001",
  "target_object_id": "q_001",
  "original_value": {},
  "new_value": {},
  "reason": "校内课程要求",
  "created_at": "2026-07-29T12:00:00+08:00"
}
```

---

# 16. 质量评估指标

## 16.1 语言分析指标

* 词汇等级识别准确率；
* 熟词生义识别准确率；
* 长难句主干识别准确率；
* 语法点抽取精确率；
* 文本难度与教师判断一致性；
* 高考题型适配判断准确率。

## 16.2 阅读指标

* 自动题目可回答率；
* 答案唯一性；
* 文本证据定位准确率；
* 干扰项质量；
* 错因诊断与教师一致率；
* 提示后独立重答成功率；
* 同技能变式题迁移率。

## 16.3 写作指标

* 语法错误检测精确率；
* 错误误报率；
* 内容要点遗漏识别率；
* 续写情节一致性识别率；
* 与人工评分一致性；
* 修改后原意保持率；
* 第二稿提升幅度。

## 16.4 听说指标

* 听力证据时间定位准确率；
* 听力干扰项诊断准确率；
* ASR 词错误率；
* 发音分与人工评价相关性；
* 流利度评分稳定性；
* 音频质量异常拦截率。

## 16.5 学习追踪指标

* 掌握度对未来作答的预测准确率；
* 复习到期实际回忆率；
* 错误复发率；
* 分数预测误差；
* 时间管理风险预测准确率；
* 学习计划完成率；
* 阶段能力变化稳定性。

---

# 17. 核心验收标准

系统进入正式教学试点前，必须满足：

1. 所有分数均可追溯到任务证据；
2. 阅读题均附带文本证据；
3. 阅读错误均可映射到干扰项或技能诊断；
4. 七选五正确选项经过回填唯一性校验；
5. 应用文和读后续写使用独立评分逻辑；
6. 作文优化能够阻断原意改变；
7. ASR 低置信内容不直接形成语法扣分；
8. 口语成绩不直接换算为高考书面卷分数；
9. 掌握度更新考虑提示、难度和独立程度；
10. 首次测评输出分项画像和置信区间；
11. 单次练习不得形成稳定高考分数预测；
12. 日常训练结束后自动更新复习队列；
13. 同一知识点可以跨阅读、语法、写作和口语积累证据；
14. 教师能够查看和覆盖 Agent 结论；
15. 所有教师覆盖操作具有审计记录。

---

# 18. MVP 开发规划

## 18.1 第一阶段

实现：

* 新高考全国Ⅰ卷考试配置；
* 英语文本语言分析；
* 课标词汇和熟词生义识别；
* 长难句分析；
* 阅读理解题生成；
* 七选五生成；
* 阅读答案和干扰项诊断；
* 基础词汇、语法掌握度；
* 简单间隔复习。

## 18.2 第二阶段

增加：

* 应用文要求检查；
* 应用文自动评分；
* 读后续写故事解析；
* 续写情节一致性校验；
* 逐句批注；
* 原意保护；
* 双稿制写作工作流；
* 听力题生成和错因诊断。

## 18.3 第三阶段

增加：

* ASR 和口语反馈；
* 自适应首次测评；
* 模拟考试时间管理；
* 分项成绩预测；
* 阶段报告；
* 教师端学情分析；
* 班级共性错因识别；
* 教师覆盖与审计。

## 18.4 第四阶段

增加：

* 多省份考试配置；
* 多教材版本适配；
* 真实试题难度校准；
* 跨场景知识证据融合；
* 个性化长期复习模型；
* 班级分层教学建议；
* 教师自定义知识图谱和评分规则。
