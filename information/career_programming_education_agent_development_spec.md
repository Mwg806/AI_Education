# 职业教育 / 编程教育 Agent 开发设计说明书

> 文档定位：用于职业教育 / 编程教育 Agent 的产品定义、系统设计、研发拆解、接口约束、数据设计、测试验收与后续扩展。
> 目标读者：产品经理、AI Agent 工程师、后端工程师、前端工程师、算法工程师、测试工程师、教研人员。
> 推荐技术栈：LangChain + LangGraph + FastAPI + MySQL + Redis + Docker Sandbox + RAG。
> 首期建议聚焦方向：Python 后端开发工程师。
> 后续可扩展方向：Java 后端、前端开发、全栈开发、数据分析、AI/算法工程师、测试开发、运维/DevOps 等。

---

# 1. 项目背景

传统编程教育产品通常存在以下问题：

1. 以课程内容为中心，而不是以岗位能力为中心；
2. 能告诉学生“学什么”，但不能判断“现在会什么、还不会什么”；
3. 能提供代码答案，但缺少真实代码运行、测试和错误定位；
4. 项目实训往往只给完整代码，缺乏逐阶段任务、检查点和过程评价；
5. 学习、项目、简历、面试之间相互割裂；
6. 缺乏持续更新的学生职业能力画像；
7. LLM 很容易直接给出答案，导致“完成任务”而不是“真正学习”。

因此，本项目不应被定义为一个简单的“编程问答机器人”，而应被定义为：

> **面向职业技能学习、编程训练、项目实训与面试准备的智能教学 Agent。**

该 Agent 通过持续维护用户职业目标、技能掌握度、练习记录、项目过程和面试表现，形成一个完整的职业能力训练闭环。

---

# 2. 产品定位

## 2.1 核心定位

职业教育 / 编程教育 Agent 的核心职责是：

> 围绕用户的目标岗位，自动完成岗位技能拆解、能力诊断、学习路线生成、编码训练、项目实训、代码反馈、能力更新、面试训练和就业准备。

其核心闭环如下：

```text
职业目标
   ↓
岗位技能图谱
   ↓
当前能力诊断
   ↓
技能差距分析
   ↓
个性化学习路线
   ↓
知识学习 / 编码练习 / 项目实训
   ↓
代码执行 / 自动测试 / AI Review
   ↓
错误诊断
   ↓
针对性补练
   ↓
能力画像更新
   ↓
项目能力评价
   ↓
模拟面试
   ↓
岗位胜任度评估
```

---

## 2.2 核心服务对象

首期建议服务以下用户：

- 高职 / 专科学生；
- 本科计算机及相关专业学生；
- 转行进入软件开发行业的学习者；
- 有一定编程基础，希望准备实习或校招的学生；
- 希望通过项目和面试提升岗位竞争力的用户。

---

## 2.3 首期产品边界

第一版不建议同时支持所有职业方向。

推荐首期固定：

```text
目标岗位：Python 后端开发工程师
```

首期覆盖：

- Python 工程基础；
- Git；
- Linux；
- HTTP；
- REST API；
- FastAPI；
- MySQL；
- ORM；
- Redis；
- pytest；
- Docker；
- API 设计；
- 数据库设计；
- 项目开发；
- 常见后端面试题。

待闭环稳定后，再复制能力模型到：

- Java Backend；
- Frontend；
- Full Stack；
- Data Analyst；
- AI Engineer；
- Test Engineer；
- DevOps Engineer。

---

# 3. 项目目标

## 3.1 总体目标

构建一个能够长期跟踪学生职业技能成长的智能 Agent，使系统具备以下核心能力：

1. 理解用户职业目标；
2. 将岗位拆解为结构化技能图谱；
3. 诊断用户当前技能水平；
4. 计算用户与目标岗位之间的能力差距；
5. 自动生成可执行学习计划；
6. 自动生成编程训练任务；
7. 自动运行用户代码和测试用例；
8. 判断代码正确性、质量和工程规范；
9. 根据错误类型提供分级教学反馈；
10. 自动生成和管理项目实训任务；
11. 对项目过程和成果进行评价；
12. 自动更新用户技能掌握度；
13. 根据能力薄弱点动态调整下一步学习内容；
14. 支持真实岗位场景的模拟面试；
15. 输出岗位胜任度报告和学习建议。

---

## 3.2 非目标

第一阶段不建议实现：

- 自动帮用户完成整个大型商业项目；
- 无约束执行任意系统命令；
- 完全依赖 LLM 判断代码正确性；
- 直接把完整项目代码一次性生成给用户；
- 只依赖聊天历史作为学习状态；
- 同时构建几十种岗位完整技能体系；
- 首期接入真实招聘平台并做自动投递；
- 首期做企业级 ATS 招聘匹配系统。

---

# 4. 核心设计原则

## 4.1 岗位能力驱动

所有学习内容最终都应映射到：

```text
岗位
→ 能力域
→ 技能
→ 子技能
→ 知识点
→ 练习
→ 项目任务
→ 面试题
```

而不是简单的：

```text
课程章节
→ 视频
→ 习题
```

---

## 4.2 证据驱动的能力更新

不能仅因为用户说“我会 FastAPI”就认为其掌握。

技能掌握度应依据证据更新，例如：

- 自评；
- 基础测评；
- 编码练习；
- 单元测试；
- 项目提交；
- Code Review；
- 面试回答；
- 历史稳定表现。

建议：

```text
自评证据权重 < 测试证据 < 代码证据 < 项目证据
```

---

## 4.3 教学优先，而不是答案优先

对于编程问题，默认采用分级提示：

```text
Hint 1：指出问题方向
Hint 2：指出相关知识
Hint 3：提供伪代码
Hint 4：提供关键实现片段
Solution：完整参考答案
```

避免用户第一次失败就直接得到完整答案。

---

## 4.4 工具判断事实，LLM 负责解释

例如：

```text
代码是否编译成功      → 编译器
测试是否通过          → pytest / unittest
代码风格              → Ruff / Flake8 / ESLint
类型问题              → mypy / tsc
复杂度                → 静态分析工具
教学反馈              → LLM
下一步练什么          → Agent 决策
```

---

## 4.5 所有能力必须可追踪

系统应能够回答：

- 用户现在会什么；
- 用户不会什么；
- 最近错误集中在哪；
- 哪些能力来源于真实项目；
- 哪些知识只是自评；
- 下一步为什么推荐这个任务。

---

# 5. 核心业务模块

整个 Agent 建议拆分为 8 个核心模块。

---

# 6. 模块一：职业目标与用户画像

## 6.1 功能目标

第一次使用时收集用户职业目标与学习背景。

核心输入：

- 目标岗位；
- 当前身份；
- 学历阶段；
- 编程经历；
- 已掌握语言；
- 已掌握技术栈；
- 每周学习时间；
- 目标时间；
- 是否准备实习 / 校招 / 社招；
- 是否有项目经验；
- 是否有面试经历。

---

## 6.2 示例输出

```json
{
  "user_id": "u_001",
  "target_role": "Python Backend Engineer",
  "target_level": "Intern / Junior",
  "deadline_days": 90,
  "weekly_hours": 14,
  "known_skills": [
    "Python基础",
    "MySQL基础"
  ],
  "weak_skills": [
    "FastAPI",
    "Redis",
    "Docker",
    "Testing"
  ],
  "project_experience": "low",
  "interview_experience": "none"
}
```

---

## 6.3 建议工具

```text
collect_career_goal
collect_learning_background
normalize_target_role
build_initial_user_profile
update_user_profile
```

---

# 7. 模块二：岗位技能图谱 Skill Graph

## 7.1 功能目标

将岗位拆解为机器可读取、可评估、可学习的技能结构。

---

## 7.2 示例：Python 后端技能图谱

```text
Python Backend Engineer
│
├── Python
│   ├── Syntax
│   ├── Data Structure
│   ├── OOP
│   ├── Exception
│   ├── Decorator
│   ├── Generator
│   ├── Type Hint
│   └── AsyncIO
│
├── Web Foundation
│   ├── HTTP
│   ├── REST
│   ├── JSON
│   ├── Cookie
│   ├── Session
│   └── Authentication
│
├── FastAPI
│   ├── Route
│   ├── Pydantic
│   ├── Dependency Injection
│   ├── Middleware
│   ├── Error Handling
│   └── Async API
│
├── Database
│   ├── SQL
│   ├── MySQL
│   ├── Index
│   ├── Transaction
│   ├── SQLAlchemy
│   └── Redis
│
├── Engineering
│   ├── Git
│   ├── Linux
│   ├── Logging
│   ├── Testing
│   ├── Docker
│   └── Deployment
│
└── Project Capability
    ├── Requirement Analysis
    ├── API Design
    ├── Database Design
    ├── Debugging
    ├── Security
    └── Documentation
```

---

## 7.3 Skill Node 数据结构

```json
{
  "skill_id": "PY_FASTAPI_ROUTE",
  "name": "FastAPI Routing",
  "domain": "FastAPI",
  "level": 2,
  "importance": 0.85,
  "prerequisites": [
    "HTTP_BASIC",
    "PY_FUNCTION"
  ],
  "learning_outcomes": [
    "能够定义GET/POST接口",
    "能够处理Path和Query参数",
    "能够返回规范HTTP状态码"
  ],
  "assessment_types": [
    "quiz",
    "coding",
    "project"
  ],
  "related_projects": [
    "todo_api"
  ],
  "related_interview_topics": [
    "rest_api"
  ]
}
```

---

## 7.4 推荐字段

Skill Node 至少包含：

| 字段 | 说明 |
|---|---|
| skill_id | 唯一 ID |
| role_id | 所属岗位 |
| name | 技能名称 |
| domain | 能力域 |
| level | 难度等级 |
| importance | 岗位重要度 |
| prerequisite | 前置能力 |
| learning_outcomes | 学习目标 |
| assessment_rules | 掌握判定规则 |
| resources | 学习资源 |
| tasks | 练习任务 |
| projects | 项目关联 |
| interview_questions | 面试关联 |

---

# 8. 模块三：能力诊断与 Gap Analysis

## 8.1 功能目标

分析：

```text
目标岗位需要什么
-
用户当前掌握什么
=
技能差距
```

---

## 8.2 能力证据来源

建议至少使用：

```text
Self Report
Diagnostic Quiz
Coding Test
Project Evidence
Interview Evidence
Historical Performance
```

---

## 8.3 技能掌握度

建议统一使用：

```text
0.00 ~ 1.00
```

例如：

```json
{
  "python_oop": 0.82,
  "fastapi": 0.55,
  "mysql": 0.70,
  "redis": 0.25,
  "docker": 0.18
}
```

---

## 8.4 简化计算模型

可以首期采用规则型：

```text
mastery =
0.10 × self_report
+ 0.20 × quiz
+ 0.30 × coding
+ 0.30 × project
+ 0.10 × interview
```

后期再加入：

- Bayesian Knowledge Tracing；
- Deep Knowledge Tracing；
- IRT；
- 时间衰减；
- Evidence Confidence。

---

## 8.5 输出

```json
{
  "target_role": "Python Backend Engineer",
  "overall_readiness": 0.48,
  "strong_skills": [
    "Python基础",
    "SQL基础"
  ],
  "priority_gaps": [
    "FastAPI",
    "Redis",
    "Docker",
    "Testing"
  ]
}
```

---

# 9. 模块四：个性化学习路线

## 9.1 功能目标

根据：

```text
岗位要求
+
当前能力
+
可用时间
+
目标截止日期
=
学习路线
```

---

## 9.2 学习路线结构

不要只输出：

```text
第一周学 Python
第二周学 FastAPI
```

每个阶段都应该包含：

```text
学习目标
知识任务
代码练习
项目任务
验收标准
时间预算
依赖关系
```

---

## 9.3 示例

```json
{
  "week": 4,
  "topic": "FastAPI 基础",
  "learning_objectives": [
    "掌握Route",
    "掌握Pydantic",
    "理解HTTP状态码"
  ],
  "coding_tasks": [
    "实现用户CRUD"
  ],
  "project_tasks": [
    "完成学生管理系统用户模块"
  ],
  "acceptance": [
    "所有API测试通过",
    "错误状态码符合REST规范"
  ],
  "estimated_hours": 12
}
```

---

# 10. 模块五：编程训练 Coding Tutor

这是本 Agent 的核心模块之一。

## 10.1 流程

```text
Skill Node
   ↓
Task Generator
   ↓
User Coding
   ↓
Code Execution
   ↓
Test Cases
   ↓
Static Analysis
   ↓
Error Diagnosis
   ↓
Teaching Feedback
   ↓
Retry
   ↓
Mastery Update
```

---

## 10.2 编程任务类型

建议支持：

1. 基础语法题；
2. Bug Fix；
3. Function Implementation；
4. API 编程；
5. 数据处理；
6. SQL；
7. 算法题；
8. 重构题；
9. 工程配置题；
10. Debug 题。

---

## 10.3 Task 数据结构

```json
{
  "task_id": "task_001",
  "skill_id": "PY_DICT",
  "difficulty": 2,
  "type": "coding",
  "description": "实现单词频次统计函数",
  "starter_code": "def count_words(words):\n    pass",
  "test_cases": [],
  "hints": [],
  "rubric": {}
}
```

---

# 11. 模块六：代码执行与自动测试

## 11.1 核心原则

绝不建议直接在主后端环境执行用户代码。

必须使用：

```text
Sandbox
```

推荐：

```text
FastAPI Backend
      ↓
Code Runner Service
      ↓
Docker Sandbox
      ↓
Language Runtime
      ↓
Test Runner
```

---

## 11.2 Sandbox 限制

每次执行至少限制：

```text
CPU
Memory
Execution Time
Network
Filesystem
Process Count
```

例如：

```text
CPU: 1 Core
Memory: 256MB
Timeout: 5s
Network: Disabled
Read-only Base FS
Maximum Processes: 20
```

---

## 11.3 Python 工具链

可以使用：

```text
pytest
ruff
mypy
bandit
radon
```

---

## 11.4 返回结构

```json
{
  "execution_status": "finished",
  "compile_success": true,
  "tests_passed": 8,
  "tests_failed": 2,
  "runtime_ms": 82,
  "memory_mb": 18,
  "static_analysis": {
    "style_issues": 2,
    "complexity": 4
  }
}
```

---

# 12. 模块七：错误诊断与教学反馈

## 12.1 Error Taxonomy

建议统一错误分类：

```text
Programming Error
│
├── Syntax Error
├── Runtime Error
│   ├── TypeError
│   ├── IndexError
│   ├── KeyError
│   └── Null Error
├── Logic Error
├── Algorithm Error
├── API Misuse
├── Knowledge Gap
├── Performance Problem
└── Engineering Issue
    ├── Code Style
    ├── Architecture
    ├── Testing
    ├── Security
    └── Maintainability
```

---

## 12.2 反馈原则

第一轮失败：

```text
指出方向
```

第二轮：

```text
指出知识点
```

第三轮：

```text
提供伪代码
```

第四轮：

```text
关键代码
```

用户主动要求完整答案：

```text
完整解释 + 参考代码
```

---

## 12.3 示例

用户错误：

```python
for i in nums:
    for j in nums:
        if i + j == target:
            return [i, j]
```

Agent 应反馈：

```text
测试没有通过。

你当前返回的是数组中的“元素值”，但题目要求的是“元素下标”。

建议思考：
Python 中是否有一种方式，可以在遍历元素时同时获得 index 和 value？

知识点：
enumerate
```

而不是立即重写全部答案。

---

# 13. 模块八：项目实训 Project Mentor

项目实训应是 Agent 的另一核心能力。

---

## 13.1 项目流程

```text
Project Selection
      ↓
Requirement
      ↓
Milestones
      ↓
Task Breakdown
      ↓
Student Implementation
      ↓
Submission
      ↓
Auto Test
      ↓
Code Review
      ↓
Feedback
      ↓
Revision
      ↓
Project Evaluation
```

---

## 13.2 首期推荐项目

Python 后端方向可以准备：

### Project 1

```text
Todo REST API
```

目标：

- FastAPI；
- CRUD；
- Pydantic；
- 基础测试。

### Project 2

```text
Blog Backend
```

增加：

- MySQL；
- SQLAlchemy；
- User / Post；
- JWT。

### Project 3

```text
Student Management System
```

增加：

- RBAC；
- Pagination；
- Logging；
- Redis。

### Project 4

```text
Mini E-commerce Backend
```

增加：

- Order；
- Cache；
- Transaction；
- Docker；
- Deployment。

---

## 13.3 Project Task 数据结构

```json
{
  "project_id": "student_manage",
  "milestone": 2,
  "task_id": "student_model",
  "objective": "设计Student数据模型",
  "requirements": [
    "id",
    "name",
    "student_number",
    "class_name",
    "created_at"
  ],
  "acceptance": [
    "student_number唯一",
    "字段类型合理",
    "可创建数据库表"
  ]
}
```

---

# 14. 项目评价体系

建议使用 Rubric。

| 评价维度 | 权重 |
|---|---:|
| 功能正确性 | 30% |
| 代码质量 | 15% |
| 系统设计 | 15% |
| 数据库 / API 设计 | 15% |
| 测试 | 10% |
| 文档与部署 | 15% |

---

## 14.1 示例

```json
{
  "project_score": 78,
  "dimensions": {
    "functionality": 92,
    "code_quality": 85,
    "system_design": 72,
    "testing": 45,
    "deployment": 80
  }
}
```

评价结果应反向更新用户技能画像。

---

# 15. 模块九：模拟面试 Interview Coach

## 15.1 功能目标

围绕目标岗位进行：

- 基础面试；
- 技术面试；
- 项目面试；
- 场景题；
- 系统设计；
- HR 行为问题。

---

## 15.2 面试 Workflow

```text
Select Role
    ↓
Select Difficulty
    ↓
Generate Question
    ↓
User Answer
    ↓
Evaluate
    ↓
Follow-up
    ↓
Final Report
```

---

## 15.3 回答评价维度

```text
Correctness
Completeness
Clarity
Depth
Practicality
Role Match
```

---

## 15.4 示例输出

```json
{
  "question": "Redis为什么快？",
  "score": 68,
  "dimensions": {
    "correctness": 75,
    "completeness": 55,
    "clarity": 70
  },
  "missing_points": [
    "IO多路复用",
    "高效数据结构"
  ],
  "followup": "Redis为什么以前主要采用单线程处理命令？"
}
```

---

# 16. 模块十：简历与项目经历沉淀

此模块建议在 V2 / V3 实现。

Agent 只能基于用户真实完成的内容生成项目经历。

数据来源：

```text
Project Tasks
Git Commit
Submission History
Test Result
Project Evaluation
```

禁止无依据虚构：

```text
“独立负责千万级高并发系统”
```

如果用户实际上没有做过。

---

# 17. LangGraph 总体架构

建议将 Agent 设计为状态驱动 Workflow。

```text
START
  │
  ▼
Intent Router
  │
  ├───────────── Career Goal
  │
  ├───────────── Skill Diagnosis
  │
  ├───────────── Learning Planning
  │
  ├───────────── Coding Tutor
  │
  ├───────────── Project Mentor
  │
  └───────────── Interview Coach
  │
  ▼
Student Model Update
  │
  ▼
Persistence
  │
  ▼
END
```

---

# 18. 推荐 LangGraph 节点

```text
intent_router
career_goal_parser
profile_loader
skill_graph_loader
skill_gap_analyzer
learning_plan_generator
task_selector
coding_task_generator
code_result_analyzer
feedback_generator
project_task_manager
project_evaluator
interview_question_generator
interview_evaluator
skill_mastery_updater
memory_writer
```

---

# 19. Agent State 设计

推荐：

```python
from typing_extensions import TypedDict

class CareerEducationState(TypedDict):
    user_id: str

    messages: list

    intent: str

    career_goal: dict
    user_profile: dict

    skill_profile: dict
    skill_gap: dict

    learning_plan: dict

    current_skill_id: str
    current_task: dict

    submitted_code: str
    execution_result: dict
    test_result: dict
    static_analysis_result: dict

    diagnosis: dict
    feedback: dict

    current_project: dict
    project_task: dict
    project_evaluation: dict

    interview_session: dict
    interview_question: dict
    interview_evaluation: dict

    next_action: str
```

---

# 20. Intent Router

建议至少识别：

```text
CAREER_QUERY
SKILL_DIAGNOSIS
LEARNING_PLAN
KNOWLEDGE_QUESTION
CODING_PRACTICE
CODE_DEBUG
PROJECT_GUIDANCE
PROJECT_REVIEW
INTERVIEW_PRACTICE
PROGRESS_QUERY
```

例如：

```json
{
  "intent": "CODE_DEBUG",
  "confidence": 0.94
}
```

---

# 21. Tool Layer 设计

建议工具按业务域划分。

---

## 21.1 Career Tools

```text
get_role_definition
get_role_skill_graph
calculate_skill_gap
generate_role_readiness
```

---

## 21.2 Learning Tools

```text
generate_learning_plan
get_next_skill
get_learning_resource
update_learning_progress
```

---

## 21.3 Coding Tools

```text
generate_coding_task
submit_code
run_code
run_test_cases
run_static_analysis
analyze_failure
generate_hint
```

---

## 21.4 Project Tools

```text
create_project
decompose_project
get_next_project_task
submit_project_task
evaluate_project_task
evaluate_project
```

---

## 21.5 Interview Tools

```text
create_interview_session
generate_interview_question
evaluate_interview_answer
generate_followup_question
generate_interview_report
```

---

## 21.6 Profile Tools

```text
get_user_profile
get_skill_mastery
update_skill_mastery
get_error_history
get_learning_history
```

---

# 22. 数据库设计

建议使用 MySQL 存结构化长期数据。

---

## 22.1 核心表

```text
users
career_goals
roles
skill_nodes
skill_edges

user_skill_mastery
skill_evidence

learning_plans
learning_plan_items

coding_tasks
coding_submissions
test_results
error_records

projects
project_milestones
project_tasks
project_submissions
project_evaluations

interview_sessions
interview_questions
interview_answers
interview_evaluations
```

---

# 23. user_skill_mastery 表

这是最重要的表之一。

建议字段：

```sql
id
user_id
skill_id
mastery
confidence
last_assessed_at
practice_count
success_count
source
created_at
updated_at
```

---

# 24. skill_evidence 表

记录能力更新依据：

```sql
id
user_id
skill_id
evidence_type
evidence_id
score
weight
created_at
```

evidence_type：

```text
self_report
quiz
coding
project
interview
```

---

# 25. Redis 使用建议

Redis 可以保存：

- Agent 短期状态；
- LangGraph checkpoint；
- 当前项目 session；
- 当前练习 session；
- 面试 session；
- 临时执行任务状态；
- Rate Limit；
- Code Runner Queue。

长期学习记录不要只存在 Redis。

---

# 26. RAG 知识库设计

职业教育 Agent 可以建设 4 类知识库。

## 26.1 Skill Knowledge Base

```text
Python
FastAPI
MySQL
Redis
Docker
Linux
Git
```

用于知识讲解。

---

## 26.2 Job Skill Base

来源：

- 岗位能力标准；
- 职业技能标准；
- 企业岗位描述；
- 技术路线。

---

## 26.3 Project Knowledge Base

包含：

- 项目需求；
- 项目规范；
- API 规范；
- 工程模板；
- 评分标准。

---

## 26.4 Interview Knowledge Base

包含：

- Python；
- Database；
- Redis；
- Network；
- OS；
- Project；
- System Design。

---

# 27. 编程 Sandbox 架构

推荐独立服务：

```text
Agent Backend
      ↓
Code Runner API
      ↓
Task Queue
      ↓
Docker Sandbox
      ↓
Result Collector
```

---

# 28. 安全要求

Code Sandbox 必须：

1. 禁止访问宿主机文件；
2. 默认禁用外网；
3. CPU 限制；
4. 内存限制；
5. 运行时限制；
6. 文件大小限制；
7. 进程数限制；
8. 禁止 Docker Socket；
9. 禁止 privileged；
10. 执行结束立即销毁容器。

---

# 29. API 示例

## 29.1 创建编程任务

```http
POST /api/coding/task
```

Request：

```json
{
  "user_id": "u001",
  "skill_id": "PY_DICT",
  "difficulty": 2
}
```

---

## 29.2 提交代码

```http
POST /api/coding/submit
```

```json
{
  "user_id": "u001",
  "task_id": "task001",
  "language": "python",
  "code": "..."
}
```

---

## 29.3 获取反馈

```http
GET /api/coding/submission/{submission_id}
```

---

# 30. 前端页面建议

至少需要：

## 30.1 Dashboard

展示：

```text
职业目标
岗位准备度
技能雷达
当前计划
最近训练
薄弱技能
项目进度
面试准备度
```

---

## 30.2 Skill Map

技能图谱可视化。

---

## 30.3 Coding Workspace

建议布局：

```text
左侧：
任务说明

中间：
代码编辑器

右侧：
Hint / Feedback

底部：
Test Result
Console
```

推荐 Monaco Editor。

---

## 30.4 Project Workspace

展示：

```text
Project
Milestones
Current Task
Submission
Review
Score
```

---

## 30.5 Interview Workspace

聊天或语音面试界面。

---

# 31. 教学策略设计

Agent 不应该每次立即给最终答案。

建议定义：

```text
Teaching Policy
```

---

## 31.1 Beginner

```text
解释多
提示多
任务小
反馈详细
```

---

## 31.2 Intermediate

```text
解释减少
先提问
强调Debug
```

---

## 31.3 Advanced

```text
更强调架构
性能
测试
工程权衡
```

---

# 32. 动态难度调整

根据最近表现调整 difficulty。

例如：

```text
连续3次首次通过
→ difficulty + 1

连续2次失败
→ difficulty - 1

同一错误出现3次
→ 插入 remedial task
```

---

# 33. 学习闭环

完整闭环必须做到：

```text
Learn
 ↓
Practice
 ↓
Execute
 ↓
Evaluate
 ↓
Diagnose
 ↓
Remediate
 ↓
Re-test
 ↓
Update Mastery
 ↓
Select Next Skill
```

只有做到这一点，才算真正的智能教学系统。

---

# 34. 与其他教育 Agent 的协作建议

如果系统中已经存在其他教育 Agent，不建议在职业教育 Agent 内重新实现一整套通用能力。

可复用：

```text
个性化学习规划 Agent
→ 通用计划能力

学情诊断 Agent
→ 通用能力分析

作业辅导 Agent
→ 通用教学反馈
```

职业教育 Agent 聚焦：

```text
岗位技能图谱
代码训练
代码沙箱
项目实训
工程能力评价
面试
职业准备
```

建议共享统一：

```text
User Profile
Learning Profile
Skill Evidence
Memory Schema
Agent Protocol
```

---

# 35. MVP 开发范围

## Phase 1：核心训练闭环

目标：

```text
Python Backend
```

实现：

1. 用户职业目标采集；
2. Python Backend Skill Graph；
3. 基础能力诊断；
4. Skill Gap；
5. 学习路线；
6. 编程任务；
7. Docker Sandbox；
8. pytest；
9. AI Feedback；
10. Skill Mastery 更新。

核心流程：

```text
Goal
 ↓
Diagnosis
 ↓
Plan
 ↓
Task
 ↓
Code
 ↓
Test
 ↓
Feedback
 ↓
Mastery Update
```

---

# 36. Phase 2：项目实训

新增：

1. Project Library；
2. 项目拆解；
3. Milestone；
4. Task；
5. Code Review；
6. Project Rubric；
7. Project Skill Evidence。

---

# 37. Phase 3：就业闭环

新增：

1. 模拟面试；
2. 项目经历生成；
3. 简历建议；
4. 岗位胜任度；
5. JD Gap；
6. 个性化冲刺计划。

最终形成：

```text
岗位
↓
学习
↓
练习
↓
项目
↓
简历
↓
面试
↓
就业准备
```

---

# 38. 开发优先级

## P0

必须优先：

```text
Skill Graph
Student Skill Profile
Skill Gap
Code Sandbox
Test Cases
Coding Feedback
Skill Mastery Update
```

---

## P1

第二阶段：

```text
Project Mentor
Project Rubric
Error Diagnosis
Adaptive Difficulty
Interview Practice
```

---

## P2

后续：

```text
Resume
JD Matching
Job Recommendation
Voice Interview
Enterprise Skill Standard
```

---

# 39. 推荐项目目录

```text
career_education_agent/
│
├── app/
│   ├── agents/
│   │   ├── career_agent.py
│   │   ├── coding_agent.py
│   │   ├── project_agent.py
│   │   └── interview_agent.py
│   │
│   ├── graph/
│   │   ├── state.py
│   │   ├── nodes.py
│   │   ├── router.py
│   │   └── workflow.py
│   │
│   ├── tools/
│   │   ├── career_tools.py
│   │   ├── skill_tools.py
│   │   ├── coding_tools.py
│   │   ├── sandbox_tools.py
│   │   ├── project_tools.py
│   │   └── interview_tools.py
│   │
│   ├── services/
│   │   ├── skill_service.py
│   │   ├── learning_service.py
│   │   ├── code_runner_service.py
│   │   ├── evaluation_service.py
│   │   └── rag_service.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── skill.py
│   │   ├── task.py
│   │   ├── project.py
│   │   └── interview.py
│   │
│   ├── api/
│   │   ├── career.py
│   │   ├── coding.py
│   │   ├── project.py
│   │   └── interview.py
│   │
│   └── prompts/
│
├── skill_graph/
├── project_library/
├── interview_bank/
├── sandbox/
├── tests/
└── README.md
```

---

# 40. Prompt 设计原则

不建议用一个超长 System Prompt 完成全部任务。

推荐：

```text
Global System Prompt
+
Role-specific Prompt
+
Node Prompt
+
Structured Context
+
Tool Result
```

例如：

```text
coding_feedback_prompt
project_review_prompt
interview_evaluation_prompt
skill_gap_prompt
learning_plan_prompt
```

---

# 41. 结构化输出

Agent 关键节点必须使用结构化数据。

例如：

```python
class CodingDiagnosis(BaseModel):
    error_type: str
    root_cause: str
    related_skill_id: str
    severity: int
    recommended_hint_level: int
    mastery_adjustment: float
```

避免让下游系统解析自然语言。

---

# 42. 评测体系

Agent 上线前至少需要四层评测。

---

## 42.1 Tool Test

测试：

```text
Sandbox
Test Runner
Static Analysis
Database
RAG
```

---

## 42.2 Node Test

测试：

```text
Intent Router
Skill Gap
Task Generation
Diagnosis
Feedback
Interview Evaluation
```

---

## 42.3 Workflow Test

测试完整流程：

```text
Beginner
Intermediate
Advanced
```

---

## 42.4 Educational Evaluation

重点检查：

```text
是否过早泄露答案
反馈是否准确
推荐难度是否合理
错误定位是否正确
学习路径是否匹配技能Gap
```

---

# 43. 核心指标

建议至少监控：

## 学习指标

```text
Skill Mastery Growth
First-pass Rate
Retry Count
Hint Usage
Task Completion Rate
```

## 项目指标

```text
Milestone Completion
Project Score
Code Quality Score
Test Coverage
```

## Agent 指标

```text
Intent Accuracy
Tool Success Rate
Sandbox Failure Rate
Structured Output Failure
Latency
Token Cost
```

---

# 44. 验收标准

MVP 建议至少满足：

### 职业诊断

- 能正确识别 Python Backend 职业目标；
- 能生成完整 Skill Gap；
- 能给出解释原因。

### 学习计划

- 每个计划包含：
  - skill；
  - objective；
  - task；
  - acceptance；
  - estimated time。

### 编程训练

- 能创建代码任务；
- 能提交代码；
- 能安全运行；
- 能执行测试；
- 能准确反馈失败用例；
- 能提供分级 Hint。

### 能力更新

- 成功 / 失败能影响 mastery；
- 能记录 evidence；
- 能根据 mastery 推荐下一任务。

### 项目

Phase 2 要求：

- 能拆 Milestone；
- 能创建任务；
- 能 Review；
- 能评分；
- 能更新 Skill Profile。

---

# 45. 风险分析

## 风险 1：LLM 反馈错误

解决：

```text
工具结果优先
LLM只负责解释
```

---

## 风险 2：用户代码安全

解决：

```text
Sandbox Isolation
Resource Limit
Network Disable
```

---

## 风险 3：Skill Graph 质量不足

解决：

```text
先人工教研
后自动扩展
```

不要首期完全依赖 LLM 自动生成岗位技能体系。

---

## 风险 4：任务难度不稳定

解决：

```text
Difficulty Metadata
Historical Pass Rate
Adaptive Rules
```

---

## 风险 5：Agent 过度帮助

解决：

```text
Hint Policy
Solution Unlock Rule
Attempt Count
```

---

# 46. 最终产品形态

最终目标不是：

> “AI 回答编程问题。”

而是：

> **AI 职业技能导师。**

它应该长期知道：

```text
你想做什么岗位
你现在会什么
你不会什么
你曾经哪里出错
你做过什么项目
你的代码水平怎么样
你的项目能力怎么样
你的面试能力怎么样
你离岗位要求还有多远
你下一步最应该做什么
```

---

# 47. 推荐最终业务架构

```text
                        Career Education Agent
                                 │
             ┌───────────────────┼───────────────────┐
             │                   │                   │
             ▼                   ▼                   ▼
        Career Goal          Skill Model        Learning Plan
             │                   │                   │
             └───────────────────┼───────────────────┘
                                 │
                       ┌─────────┴─────────┐
                       ▼                   ▼
                  Coding Tutor        Project Mentor
                       │                   │
                       ▼                   ▼
                  Code Sandbox        Project Review
                       │                   │
                       └─────────┬─────────┘
                                 ▼
                          Skill Evidence
                                 │
                                 ▼
                          Mastery Update
                                 │
                                 ▼
                         Interview Coach
                                 │
                                 ▼
                       Career Readiness Report
```

---

# 48. 建议的首期开发顺序

推荐严格按照下面顺序：

```text
01 定义 Python Backend Skill Graph

02 设计 users / skill_nodes / user_skill_mastery

03 完成首次用户职业目标采集

04 完成基础 Skill Diagnosis

05 完成 Skill Gap

06 完成 Learning Plan

07 完成 Coding Task 数据结构

08 开发 Docker Sandbox

09 接入 pytest

10 完成 Coding Feedback

11 完成 Error Taxonomy

12 完成 Skill Mastery Update

13 完成 Next Task Recommendation

14 接入 Project Mentor

15 接入 Interview Coach
```

---

# 49. 第一版最小 Demo 流程

建议 Demo 严格控制在：

```text
用户：
我想成为 Python 后端开发工程师
        ↓
Agent：
完成能力诊断
        ↓
Agent：
发现 FastAPI 薄弱
        ↓
Agent：
生成 FastAPI 学习任务
        ↓
Agent：
生成一个 CRUD 编程任务
        ↓
用户：
提交代码
        ↓
Sandbox：
运行 pytest
        ↓
Agent：
定位问题并给 Hint
        ↓
用户：
修改代码
        ↓
测试通过
        ↓
Mastery：
FastAPI 0.42 → 0.55
        ↓
Agent：
推荐下一任务
```

如果第一版可以稳定跑通这条链路，说明系统核心设计成立。

---

# 50. 结论

职业教育 / 编程教育 Agent 的真正核心不在于“会不会生成代码”，而在于建立以下五个长期能力：

```text
1. 岗位技能图谱
2. 用户技能画像
3. 真实代码自动评测
4. 项目过程评价
5. 基于证据的动态学习决策
```

这五个能力共同组成产品壁垒。

因此，本项目的核心技术路线应确定为：

```text
LangGraph Workflow
        +
Skill Graph
        +
Student Skill Model
        +
Code Sandbox
        +
Project Evaluation
        +
RAG
        +
Persistent Learning Memory
```

最终实现：

> **从“职业目标”出发，以“真实技能证据”为依据，通过“学习—编码—项目—评价—面试”的连续闭环，持续提升用户岗位胜任能力。**

---

# 51. 推荐下一步开发任务

建议下一步直接进入工程实施，优先完成以下 6 个产物：

1. `python_backend_skill_graph.json`
2. `CareerEducationState` 完整 TypedDict
3. LangGraph 节点与状态流转图
4. MySQL 数据库表结构 SQL
5. Tool 接口定义
6. MVP API 接口文档

完成以上 6 项后，即可正式进入后端编码阶段。
