# 阅读与语言学习 Agent 系统开发文档

**文档名称：** Reading & Language Learning Agent Development Specification  
**系统定位：** 智能阅读与语言学习 Agent  
**版本：** V1.0  
**系统类型：** 多模态、自适应、长期学习型教育 Agent  
**目标用户：** 中学生、高中生、大学生及外语学习者  
**推荐技术栈：** Vue + Python + FastAPI + LangChain + LangGraph + MySQL + Redis + Vector DB + LLM + ASR/TTS

---

# 1. 项目背景

阅读与语言学习 Agent 面向以下核心学习场景：

- 阅读理解
- 外语学习
- 词汇学习
- 语法学习
- 口语训练
- 写作训练
- 表达优化
- 学习记录
- 个性化复习
- 学习能力诊断

系统不能仅作为普通问答机器人，而应构建为一个具备：

- 学生长期画像
- 学习状态记忆
- 知识点掌握度跟踪
- 自适应教学
- 多轮训练
- 自动评分
- 错因分析
- 个性化推荐
- 学习数据沉淀

能力的长期智能学习系统。

系统核心目标是：

> 将传统“LLM 回答问题”升级为“观察学生 → 判断水平 → 设计任务 → 学生完成 → 自动评价 → 记录表现 → 更新能力 → 调整下一次教学”的完整学习闭环。

---

# 2. 系统总体目标

系统需要形成以下闭环：

```text
用户进入系统
    ↓
读取学生画像
    ↓
判断学习目标
    ↓
选择学习模式
    ↓
生成学习任务
    ↓
学生完成任务
    ↓
自动评价
    ↓
分析错误
    ↓
给出教学反馈
    ↓
更新学生画像
    ↓
保存学习记录
    ↓
生成下一步学习建议
```

最终实现：

```text
学习

→ 练习

→ 评价

→ 诊断

→ 记录

→ 推荐

→ 再学习
```

---

# 3. 系统设计原则

## 3.1 一个 Agent，多个学习模式

不建议部署四套完全独立系统：

```text
阅读 → 模型 A
外语 → 模型 B
口语 → 模型 C
写作 → 模型 D
```

推荐采用：

```text
Reading & Language Agent
        │
        ↓
    Mode Router
        │
 ┌──────┼──────┬──────┐
 ↓      ↓      ↓      ↓
阅读    学习    口语    写作
模式    模式    模式    模式
```

不同模式对应不同：

- Prompt
- LangGraph SubGraph
- Tool
- 评分规则
- 输出 Schema

但共享：

- 用户系统
- 学生画像
- LLM
- RAG
- 词汇工具
- 语法工具
- 学习记录
- 数据库
- Memory
- 日志
- 权限
- Eval

---

# 4. 系统总体架构

```text
                       Web / Mobile
                            │
                            ▼
                     Vue Frontend
                            │
                            ▼
                       API Gateway
                            │
                            ▼
                       FastAPI
                            │
                            ▼
                 Reading Language Agent
                            │
                     LangGraph Core
                            │
        ┌───────────────────┼────────────────────┐
        │                   │                    │
        ▼                   ▼                    ▼
   Mode Router        Student Profile        Memory
        │
 ┌──────┼─────────┬─────────┐
 │      │         │         │
 ▼      ▼         ▼         ▼
Reading Language Speaking Writing
Graph   Graph     Graph    Graph
 │       │         │        │
 └───────┴─────────┴────────┘
             │
             ▼
       Shared Tools Layer
             │
 ┌───────────┼─────────────┐
 ▼           ▼             ▼
Vocabulary Grammar      Expression
Tool       Tool          Tool
 │           │             │
 ├───────────┼─────────────┤
 ▼           ▼             ▼
RAG       Learning      Evaluation
          Record
             │
             ▼
       Student Profile DB
```

---

# 5. 核心功能模块

系统划分为四个核心业务模块和若干公共能力模块。

---

# 6. 模块一：阅读理解模式

## 6.1 功能目标

训练学生：

- 阅读速度
- 主旨理解
- 事实定位
- 推理判断
- 词义猜测
- 长难句理解
- 作者态度判断
- 篇章结构分析

---

# 7. 阅读任务输入

支持：

### 文本输入

用户直接粘贴：

```text
阅读文章
```

### PDF

例如：

```text
教材
试卷
阅读材料
文章
```

### 图片

例如：

```text
阅读理解题截图
试卷照片
```

### 系统生成

根据：

```text
学生水平
+
学习目标
+
薄弱能力
```

自动生成阅读材料。

---

# 8. 阅读理解处理流程

```text
文章输入
    ↓
Text Parser
    ↓
文本清洗
    ↓
文章语言识别
    ↓
难度评估
    ↓
文章结构分析
    ↓
词汇分析
    ↓
长难句分析
    ↓
知识点标注
    ↓
题型生成 / 读取原题
    ↓
学生作答
    ↓
答案评价
    ↓
证据定位
    ↓
错因分析
    ↓
能力更新
```

---

# 9. 阅读分析输出结构

推荐后端强制使用 Structured Output：

```json
{
  "article": {
    "language": "English",
    "level": "B1",
    "topic": "environment",
    "difficulty_score": 62
  },

  "structure": [
    {
      "paragraph": 1,
      "summary": "提出环境污染问题"
    }
  ],

  "vocabulary": [],

  "complex_sentences": [],

  "main_idea": "",

  "questions": []
}
```

---

# 10. 阅读题错误分类

系统必须记录学生错误类型，而不是只记录：

```text
答错
```

推荐分类：

```text
READ_MAIN_IDEA
READ_DETAIL
READ_INFERENCE
READ_WORD_MEANING
READ_AUTHOR_ATTITUDE
READ_STRUCTURE
READ_REFERENCE
READ_LOGIC
```

例如：

```json
{
  "question_id": "Q1023",
  "student_answer": "C",
  "correct_answer": "B",

  "error_type": "READ_DETAIL",

  "reason": "未准确定位第三段关键句",

  "evidence": {
    "paragraph": 3,
    "sentence": 2
  }
}
```

---

# 11. 阅读反馈机制

反馈不要只给正确答案。

推荐四层反馈：

### Level 1

提示定位范围：

```text
答案主要位于第 3 段。
```

### Level 2

提示关键句：

```text
重点关注 although 后面的主句。
```

### Level 3

解释：

```text
作者真正强调的是……
```

### Level 4

给出完整答案。

实现：

```text
Hint → Hint → Explanation → Answer
```

避免学生过度依赖答案。

---

# 12. 模块二：外语学习模式

外语学习模式定义为：

> Adaptive Language Tutor

而不是自由聊天机器人。

---

# 13. 外语学习核心能力

包括：

```text
词汇
语法
句型
听力
阅读
翻译
短语
固定搭配
语言表达
文化背景
练习
复习
```

---

# 14. 学习计划生成

进入学习模式：

```text
Load Student Profile
        ↓
读取历史学习数据
        ↓
判断薄弱知识点
        ↓
读取近期学习记录
        ↓
生成本次学习目标
```

例如：

```text
今日学习计划

01 旧词复习        5 个

02 新词学习        8 个

03 定语从句复习

04 完成 5 道练习

05 阅读一篇短文

06 错题复习
```

---

# 15. 词汇学习系统

每个单词至少保存：

```text
Word
Lemma
Meaning
POS
IPA
Difficulty
Example
Collocation
Synonym
Antonym
Topic
Encounter Count
Correct Count
Wrong Count
Mastery Score
Last Review
Next Review
```

例如：

```json
{
  "word": "significant",
  "meaning": "重要的；显著的",
  "pos": "adjective",
  "ipa": "/sɪɡˈnɪfɪkənt/",

  "difficulty": "B1",

  "collocations": [
    "significant difference",
    "significant impact"
  ],

  "mastery": 0.71
}
```

---

# 16. 单词掌握度

建议：

```text
0.00 - 0.30

陌生


0.30 - 0.50

认识


0.50 - 0.70

基本掌握


0.70 - 0.90

熟练


0.90 - 1.00

完全掌握
```

系统根据：

```text
遇到次数

+
正确次数

+
间隔复习表现

+
主动使用情况

+
近期表现
```

动态调整 Mastery Score。

---

# 17. 自适应复习

不要每次直接重复解释。

第一次：

```text
significant

重要的；显著的
```

第二次：

```text
你之前学习过 significant。

你还记得它是什么意思吗？
```

第三次：

```text
请选择 significant 的正确含义。
```

后期：

```text
请使用 significant 写一个句子。
```

最终从：

```text
识别
```

升级到：

```text
理解
```

再升级到：

```text
主动使用
```

---

# 18. 模块三：口语训练

口语训练属于多模态模块。

不能只有 LLM。

系统需要：

```text
ASR
+
Audio Feature Analysis
+
LLM
```

---

# 19. 口语处理链路

```text
用户录音
    ↓
Audio Upload
    ↓
ASR
    ↓
Transcript
    │
    ├───────────────┐
    ▼               ▼
语言分析        声学分析
    │               │
    ▼               ▼
Grammar        Pronunciation
Vocabulary     Fluency
Content        Pause
Coherence      Speed
    │               │
    └───────┬───────┘
            ▼
        LLM Evaluator
            ↓
       Speaking Report
```

---

# 20. 口语评分维度

建议：

```text
Pronunciation

Fluency

Grammar

Vocabulary

Content

Coherence

Naturalness
```

例如：

```json
{
  "total": 82,

  "dimensions": {
    "pronunciation": 78,
    "fluency": 85,
    "grammar": 80,
    "vocabulary": 76,
    "content": 90,
    "naturalness": 81
  }
}
```

---

# 21. 发音反馈

推荐：

```text
错误单词

↓

错误音素

↓

正确发音

↓

示范

↓

学生重新朗读

↓

重新评分
```

例如：

```text
environment

问题：
/r/ 发音不充分

建议：
……

重新录制
```

---

# 22. 情景口语训练

系统支持：

```text
Airport

Restaurant

Interview

Travel

School

Business

IELTS

TOEFL

Daily conversation
```

模型角色例如：

```text
You are a hotel receptionist.
```

学生：

```text
I want book a room.
```

系统记录：

```text
语法：
want to book

表达：
I'd like to book a room.

自然度：
提升
```

---

# 23. 模块四：写作训练

核心原则：

> 写作 Agent 是“教学系统”，不是“作文自动重写器”。

---

# 24. 写作流程

```text
写作任务
    ↓
学生作文
    ↓
任务理解检查
    ↓
文章结构分析
    ↓
Grammar Analysis
    ↓
Vocabulary Analysis
    ↓
Coherence Analysis
    ↓
Content Analysis
    ↓
Score
    ↓
错误标记
    ↓
学生自行修改
    ↓
再次提交
    ↓
重新评价
    ↓
最终参考版本
```

---

# 25. 写作评价维度

例如：

```text
Content        25%

Structure      20%

Grammar        20%

Vocabulary     15%

Coherence      10%

Expression     10%
```

不同考试可加载不同 Rubric。

例如：

```text
高考英语

IELTS

TOEFL

四六级

校内作文
```

评分模板禁止混用。

---

# 26. 写作错误分类

```text
GRAMMAR_TENSE

GRAMMAR_AGREEMENT

GRAMMAR_ARTICLE

GRAMMAR_PREPOSITION

GRAMMAR_CLAUSE

VOCAB_USAGE

VOCAB_COLLOCATION

SPELLING

COHERENCE

LOGIC

STRUCTURE

STYLE

REDUNDANCY
```

---

# 27. 写作修改反馈

例如：

学生：

```text
My friend have many hobby.
```

系统：

```text
问题 1：

My friend 属于第三人称单数。

请检查 have 的形式。


问题 2：

many 后面的可数名词一般使用什么形式？
```

让学生自行：

```text
My friend has many hobbies.
```

系统：

```text
Correct.
```

随后记录：

```text
Subject Verb Agreement +1

Plural Noun +1
```

---

# 28. 公共能力层

四种学习模式共享：

```text
VocabularyService

GrammarService

ExpressionService

TranslationService

DifficultyService

KnowledgeService

StudentProfileService

LearningRecordService

EvaluationService

RecommendationService
```

---

# 29. Agent State 设计

推荐 LangGraph 使用统一 State：

```python
class LanguageAgentState(TypedDict):

    user_id: str

    session_id: str

    mode: str

    messages: list

    user_profile: dict

    learning_goal: dict

    current_task: dict

    input_content: dict

    retrieved_context: list

    analysis_result: dict

    evaluation_result: dict

    learning_events: list

    profile_updates: list

    next_action: str

    confidence: float

    errors: list
```

---

# 30. Mode 类型

```python
class LearningMode(str, Enum):

    READING = "reading"

    LANGUAGE = "language_learning"

    SPEAKING = "speaking"

    WRITING = "writing"
```

---

# 31. LangGraph 总工作流

```text
START
  │
  ▼
LoadUser
  │
  ▼
LoadStudentProfile
  │
  ▼
IntentRouter
  │
  ├───────────────┐
  │               │
  ▼               ▼
Reading         Language
  │               │
  ├───────────────┤
  │               │
  ▼               ▼
Speaking        Writing
  │               │
  └───────┬───────┘
          ▼
      Evaluator
          │
          ▼
    LearningAnalyzer
          │
          ▼
    UpdateProfile
          │
          ▼
   SaveLearningRecord
          │
          ▼
 RecommendationNode
          │
          ▼
         END
```

---

# 32. Reading SubGraph

```text
ReadingInput
       ↓
ParseReading
       ↓
AnalyzeDifficulty
       ↓
AnalyzeStructure
       ↓
AnalyzeVocabulary
       ↓
AnalyzeSentences
       ↓
QuestionHandler
       ↓
StudentAnswer
       ↓
EvaluateAnswer
       ↓
EvidenceLocator
       ↓
ErrorAnalyzer
       ↓
ReadingFeedback
```

---

# 33. Speaking SubGraph

```text
AudioInput
    ↓
ASR
    ↓
AudioAnalyzer
    ↓
TranscriptAnalyzer
    ↓
SpeakingEvaluator
    ↓
FeedbackGenerator
    ↓
Retry
    ↓
ReEvaluation
```

---

# 34. Writing SubGraph

```text
WritingTask
    ↓
EssayInput
    ↓
RequirementAnalyzer
    ↓
GrammarAnalyzer
    ↓
VocabularyAnalyzer
    ↓
StructureAnalyzer
    ↓
ContentAnalyzer
    ↓
EssayEvaluator
    ↓
GuidedFeedback
    ↓
StudentRevision
    ↓
ReEvaluation
```

---

# 35. Tool 设计

Agent 不应该所有能力全部交给 LLM。

推荐 Tools：

```text
get_student_profile

update_student_profile

get_learning_history

save_learning_event

search_language_knowledge

explain_vocabulary

check_grammar

evaluate_reading_answer

evaluate_writing

generate_exercise

schedule_review

speech_to_text

analyze_pronunciation
```

---

# 36. Tool Example

```python
@tool
def get_student_profile(user_id: str):
    """
    Get current language learning profile.
    """
```

返回：

```json
{
  "english_level": "B1",

  "reading": 0.72,

  "writing": 0.61,

  "speaking": 0.58,

  "vocabulary": 0.67,

  "grammar": 0.63
}
```

---

# 37. Structured Output 原则

核心模块禁止完全使用自由文本。

例如阅读评分：

```python
class ReadingEvaluation(BaseModel):

    correct: bool

    score: float

    error_type: Optional[str]

    evidence: Optional[str]

    explanation: str

    mastery_change: float
```

模型输出必须通过 Schema 验证。

---

# 38. 学生画像系统

Student Profile 是整个系统的数据中心。

推荐结构：

```text
Student

├── Basic Profile

├── Language Level

├── Vocabulary Mastery

├── Grammar Mastery

├── Reading Ability

├── Writing Ability

├── Speaking Ability

├── Error Distribution

├── Learning History

├── Review Queue

└── Learning Preference
```

---

# 39. 能力画像

例如：

```json
{
  "reading": {
    "main_idea": 0.82,

    "detail": 0.63,

    "inference": 0.52,

    "word_guess": 0.71
  },

  "grammar": {
    "tense": 0.81,

    "clause": 0.55,

    "non_finite": 0.43,

    "agreement": 0.87
  }
}
```

---

# 40. 数据库设计

推荐核心表：

```text
users

student_profiles

language_abilities

vocabulary_mastery

grammar_mastery

reading_records

reading_question_records

speaking_records

writing_records

learning_sessions

learning_events

error_records

review_queue

agent_sessions
```

---

# 41. users

```sql
users

id
username
phone
email
created_at
updated_at
```

---

# 42. student_profiles

```sql
student_profiles

id
user_id

native_language

target_language

current_level

target_level

learning_goal

daily_minutes

created_at

updated_at
```

---

# 43. vocabulary_mastery

```sql
vocabulary_mastery

id

user_id

word

language

mastery_score

encounter_count

correct_count

wrong_count

last_seen_at

next_review_at
```

---

# 44. grammar_mastery

```sql
grammar_mastery

id

user_id

grammar_code

mastery_score

practice_count

correct_count

wrong_count

last_practice_at
```

---

# 45. learning_events

推荐采用事件流思想：

```sql
learning_events

id

user_id

session_id

event_type

knowledge_type

knowledge_id

result

score

metadata

created_at
```

例如：

```text
VOCAB_CORRECT

VOCAB_WRONG

READING_DETAIL_WRONG

GRAMMAR_TENSE_WRONG

WRITING_REVISION_SUCCESS

SPEAKING_PRONUNCIATION_ERROR
```

---

# 46. 为什么使用 Learning Event

不要只保存最终总分。

必须能够恢复：

> 学生到底在哪一次任务、哪个知识点、犯了什么错误。

例如：

```json
{
  "event": "GRAMMAR_TENSE_WRONG",

  "knowledge": "past_simple",

  "context": "writing",

  "sentence": "I go to Beijing yesterday.",

  "timestamp": "..."
}
```

长期积累之后才能做真正的学情诊断。

---

# 47. 能力分更新

推荐采用渐进更新：

```text
new_mastery

=

old_mastery × (1 - α)

+

current_performance × α
```

α 可以根据：

```text
近期程度

题目难度

学习次数

置信度
```

动态调整。

禁止：

```text
答对一次

↓

直接 mastery = 1
```

---

# 48. RAG 知识库设计

语言学习 Agent 建议建设：

```text
教材知识库

考试标准

语法知识

词汇知识

阅读材料

范文

评分标准

题库

教学策略

语言学习资源
```

---

# 49. RAG Metadata

每个知识块至少保存：

```json
{
  "language": "English",

  "level": "B1",

  "grade": "HighSchool",

  "subject": "English",

  "knowledge_type": "Grammar",

  "knowledge_point": "Relative Clause",

  "source": "Textbook",

  "chapter": "Unit 3"
}
```

---

# 50. 检索流程

禁止简单：

```text
Query

↓

Vector Search

↓

Top 5
```

推荐：

```text
User Query
     ↓
Query Rewrite
     ↓
Intent Classification
     ↓
Metadata Filter
     ↓
Hybrid Search
     ↓
Vector + Keyword
     ↓
Reranker
     ↓
Context Filter
     ↓
LLM
```

---

# 51. Memory 设计

Memory 分三层。

## Session Memory

当前对话。

例如：

```text
今天正在做第 3 篇阅读。
```

## Learning Memory

近期学习。

例如：

```text
最近连续三次定语从句错误。
```

## Student Profile

长期画像。

例如：

```text
阅读推理能力偏弱。
```

禁止将所有聊天消息永久发送给模型。

---

# 52. 教学策略 Engine

增加 Teaching Strategy Engine。

输入：

```text
Student Profile

Current Task

Recent Errors

Difficulty

Learning Goal
```

输出：

```text
direct_answer

hint

guided_question

example

practice

review

explanation
```

Agent 根据学生状态决定应该：

```text
直接解释

还是

先提示

还是

让学生自己思考
```

---

# 53. 难度自适应

题目难度范围：

```text
0 - 100
```

规则示例：

学生连续正确：

```text
Difficulty + 5
```

连续错误：

```text
Difficulty - 5
```

但需要限制变化速度。

---

# 54. Recommendation Engine

每次 Session 结束生成：

```json
{
  "review": [
    "relative clauses",
    "significant"
  ],

  "next_learning": [
    "reading inference"
  ],

  "suggested_task": {
    "type": "reading",
    "difficulty": 65
  }
}
```

---

# 55. 前端主要页面

推荐：

```text
登录

首页 Dashboard

阅读训练

语言学习

词汇本

语法训练

口语训练

写作训练

错题本

学习记录

学习报告

个人画像
```

---

# 56. Dashboard

显示：

```text
今日学习时间

今日任务

连续学习天数

词汇掌握数

语法掌握度

阅读能力

写作能力

口语能力

最近错误

今日复习
```

---

# 57. 阅读页面

推荐布局：

```text
┌──────────────────┬───────────────┐
│                  │               │
│    Reading       │   Question    │
│                  │               │
│                  │               │
├──────────────────┴───────────────┤
│ Vocabulary / Grammar / Explanation│
└──────────────────────────────────┘
```

支持点击单词：

```text
word

↓

popover

↓

meaning

pronunciation

example

add to vocabulary
```

---

# 58. 写作页面

推荐：

```text
左：

作文编辑器


右：

评分

Grammar

Vocabulary

Structure

Suggestions
```

错误使用位置高亮：

```text
红色

Grammar


橙色

Vocabulary


蓝色

Expression
```

---

# 59. 口语页面

提供：

```text
录音

实时波形

ASR

计时

重新录制

评分

发音错误

推荐表达
```

---

# 60. API 设计

推荐：

```text
POST /api/language/session

POST /api/language/chat

POST /api/reading/analyze

POST /api/reading/submit

POST /api/writing/evaluate

POST /api/writing/revise

POST /api/speaking/upload

POST /api/speaking/evaluate

GET /api/profile

GET /api/learning/history

GET /api/review/today
```

---

# 61. Agent Chat API

请求：

```json
{
  "session_id": "...",

  "mode": "reading",

  "message": "...",

  "attachments": []
}
```

响应：

```json
{
  "message": "",

  "mode": "reading",

  "structured_data": {},

  "suggested_actions": [],

  "learning_events": []
}
```

---

# 62. 模型路由

V1 不需要四个独立模型。

推荐：

```text
Model Router

├── Cheap Model

│     词汇
│     简单语法
│     分类
│
├── Strong Model

│     阅读推理
│     写作评价
│     教学规划
│
└── Speech Model

      ASR
      Pronunciation
```

优势：

```text
降低成本

减少延迟

便于切换模型

便于 Eval
```

---

# 63. Model Adapter

禁止业务代码直接调用某个厂商 API。

统一封装：

```python
class LLMService:

    def invoke(...):
        ...

    def structured_output(...):
        ...

    def stream(...):
        ...
```

以后：

```text
OpenAI

DeepSeek

Qwen

Claude

Local Model
```

可以自由切换。

---

# 64. Prompt 管理

Prompt 禁止散落在代码中。

推荐：

```text
prompts/

├── common/

├── reading/

├── speaking/

├── writing/

├── vocabulary/

└── evaluator/
```

每个 Prompt：

```text
version

role

task

constraints

output_schema

examples
```

---

# 65. Prompt Version

数据库或配置记录：

```text
reading_evaluation_v1

reading_evaluation_v2

writing_feedback_v3
```

方便：

```text
A/B Test

Rollback

Eval
```

---

# 66. Verifier

关键任务后增加验证节点。

例如：

```text
LLM Answer
   ↓
Verifier
   ↓
Pass?
 ┌─────┴─────┐
 No          Yes
 ↓            ↓
Rewrite      Output
```

Verifier 检查：

```text
是否回答用户问题

是否有事实错误

是否符合学生水平

是否泄露答案过早

评分是否合理

格式是否正确

是否包含依据
```

---

# 67. Guardrail

教育系统需要限制：

```text
禁止伪造教材内容

禁止伪造考试标准

禁止无依据评分

禁止把模型猜测说成事实

禁止低置信度时强行给结论
```

---

# 68. Confidence

核心分析输出：

```json
{
  "confidence": 0.82
}
```

例如：

```text
> 0.85

直接输出


0.60 - 0.85

增加验证


< 0.60

请求补充信息或降低结论强度
```

---

# 69. 日志系统

每次 Agent 调用记录：

```text
request_id

user_id

session_id

mode

node

model

prompt_version

input_tokens

output_tokens

latency

tool_calls

status

error
```

---

# 70. Trace

使用：

```text
LangSmith

OpenTelemetry

或自建 Trace
```

至少能够看到：

```text
Router
 ↓
RAG
 ↓
LLM
 ↓
Tool
 ↓
Evaluator
 ↓
Database
```

每一步耗时。

---

# 71. 成本监控

统计：

```text
每日 Token

用户平均 Token

每种模式 Token

模型成本

RAG 成本

ASR 成本
```

---

# 72. 缓存

Redis 缓存：

```text
用户画像

常用词汇解释

语法知识

热门 RAG Query

Session State
```

避免重复调用 LLM。

---

# 73. 错误处理

例如 LLM 超时：

```text
Retry
 ↓
Fallback Model
 ↓
Graceful Response
```

RAG 失败：

```text
禁止编造知识

↓

告诉 Agent 缺少可靠资料
```

ASR 失败：

```text
提示重新录音
```

---

# 74. Backend 目录结构

推荐：

```text
backend/

├── app/

│   ├── api/

│   │   ├── reading.py
│   │   ├── writing.py
│   │   ├── speaking.py
│   │   └── language.py
│
│   ├── agents/

│   │   └── language_agent/
│   │
│   │       ├── graph.py
│   │       ├── state.py
│   │       ├── router.py
│   │
│   │       ├── reading/
│   │       ├── speaking/
│   │       ├── writing/
│   │       └── language/
│
│   ├── tools/

│   ├── services/

│   ├── models/

│   ├── schemas/

│   ├── repositories/

│   ├── prompts/

│   ├── rag/

│   ├── llm/

│   └── core/

├── tests/

└── main.py
```

---

# 75. Frontend 目录建议

```text
frontend/src/

├── api/

├── components/

│   ├── reading/

│   ├── speaking/

│   ├── writing/

│   └── common/

├── views/

│   ├── Dashboard

│   ├── Reading

│   ├── Speaking

│   ├── Writing

│   └── Vocabulary

├── stores/

├── router/

└── utils/
```

---

# 76. Eval 系统

Agent 上线必须建立 Eval Dataset。

建议至少：

```text
Reading      200

Vocabulary   100

Grammar      200

Writing      100

Speaking     100
```

逐渐扩充至：

```text
1000+
```

---

# 77. Eval 指标

## 阅读

```text
答案正确率

证据定位准确率

错因分类准确率

难度预测一致性
```

## 语法

```text
Grammar Error Precision

Grammar Error Recall
```

## 写作

```text
评分一致性

人工评分相关性

错误检测准确率

误报率
```

## Agent

```text
Task Completion Rate

Tool Success Rate

Hallucination Rate

Structured Output Success

Latency

Cost
```

---

# 78. 人工评价

邀请教师进行：

```text
模型评分

vs

教师评分
```

计算：

```text
Pearson

Spearman

MAE

一致性
```

---

# 79. 测试体系

必须包含：

```text
Unit Test

API Test

Tool Test

Graph Test

Prompt Eval

RAG Eval

Integration Test

Load Test

Frontend E2E
```

---

# 80. 安全要求

学生数据属于敏感数据。

必须：

```text
密码 Hash

HTTPS

权限校验

数据隔离

日志脱敏

上传文件检查

数据库权限控制

备份

删除机制
```

---

# 81. 学生隐私

禁止将：

```text
姓名

手机号

学校

学生个人信息
```

直接拼接到非必要 LLM Prompt。

采用：

```text
user_id
```

替代。

---

# 82. 与其他教育 Agent 的关系

建议统一 Student Profile。

```text
             Student Profile
                    │
        ┌───────────┼───────────┐
        ↓           ↓           ↓
   学习规划      作业辅导      学情诊断
        ↑           ↑           ↑
        └───────────┼───────────┘
                    │
             阅读语言学习
```

---

# 83. 数据共享

阅读语言 Agent 写入：

```text
词汇水平

语法水平

阅读能力

写作能力

口语能力

错误历史
```

学情诊断 Agent 读取：

```text
能力趋势

薄弱点

错误分布
```

学习规划 Agent 读取：

```text
薄弱点
```

生成：

```text
未来学习计划
```

这样多个 Agent 才是真正协同。

---

# 84. V1 开发阶段

第一阶段只实现：

```text
阅读理解

词汇解释

语法反馈

写作评价

学生画像

学习记录
```

优先实现文字链路。

---

# 85. V2

增加：

```text
口语

ASR

TTS

发音评分

自适应复习

错题本
```

---

# 86. V3

增加：

```text
完整 Learning Planner

能力预测

智能复习算法

多 Agent 数据共享

教师端

班级分析
```

---

# 87. 推荐开发顺序

```text
01 用户系统

↓

02 Student Profile

↓

03 Learning Event

↓

04 LangGraph Core

↓

05 Reading

↓

06 Vocabulary

↓

07 Grammar

↓

08 Writing

↓

09 RAG

↓

10 Evaluation

↓

11 Speaking

↓

12 Adaptive Learning

↓

13 Recommendation

↓

14 Multi-Agent Integration
```

---

# 88. MVP 验收标准

用户能够：

```text
登录

↓

进入阅读模式

↓

上传或输入文章

↓

查看文章分析

↓

完成阅读题

↓

获得错因反馈

↓

查看词汇解释

↓

完成语法练习

↓

提交作文

↓

获得写作反馈

↓

查看自己的学习记录
```

---

# 89. 成熟版验收标准

成熟系统至少满足：

### 功能

四种学习模式完整运行。

### 数据

所有学习行为均可记录。

### 个性化

学习内容根据 Student Profile 调整。

### 自适应

难度根据学生表现改变。

### 教学

优先引导而不是直接给答案。

### RAG

重要知识有来源支撑。

### 稳定性

模型失败有 Retry 与 Fallback。

### Eval

核心能力有标准测试集。

### 可观测性

每个 Agent Node 可追踪。

### 可扩展

可以添加新的语言与考试体系。

---

# 90. 最终系统定位

最终系统不应该是：

```text
用户

↓

LLM

↓

答案
```

而应该是：

```text
                Student
                   │
                   ▼
            Language Agent
                   │
                   ▼
              Mode Router
                   │
     ┌─────────────┼─────────────┐
     ▼             ▼             ▼
  Reading       Speaking       Writing
     │             │             │
     └─────────────┼─────────────┘
                   ▼
             Teaching Engine
                   │
                   ▼
              Tools / RAG
                   │
                   ▼
               Evaluator
                   │
                   ▼
             Learning Event
                   │
                   ▼
             Student Profile
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
Learning Recommendation    Diagnosis
        │
        ▼
   Next Learning Task
```

系统形成完整闭环：

```text
Learn
  ↓
Practice
  ↓
Evaluate
  ↓
Diagnose
  ↓
Remember
  ↓
Adapt
  ↓
Learn Again
```

这也是阅读与语言学习 Agent 从普通“大模型问答系统”升级为成熟“自适应语言学习系统”的核心。