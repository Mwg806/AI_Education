# 面向新高考全国Ⅰ卷高中生的个性化学习规划 Agent 需求规格说明书

> 文档版本：V1.0  
> 适用对象：普通高中高一、高二、高三学生，目标考试体系为新高考全国Ⅰ卷  
> 核心场景：个性化学习、校内同步提升、学业水平巩固、选科发展、高考备考与教师辅助  
> 文档用途：产品立项、需求评审、系统架构、Agent 编排、工具开发、接口联调和测试验收

---

## 1. 文档说明

### 1.1 建设目标

本系统建设一个面向高中生的“个性化学习规划 Agent”，根据学生的：

1. 学习目标；
2. 知识基础；
3. 练习表现；
4. 可用学习时间；

自动生成精准适配、可执行、可解释、可动态迭代的阶段性学习计划。

系统不是一次性输出一段学习建议，而是持续运行的规划系统，形成如下闭环：

```text
目标结构化
→ 学情诊断
→ 知识画像
→ 时间容量建模
→ 学习路径规划
→ 阶段与任务排期
→ 学习执行
→ 练习证据回流
→ 掌握度更新
→ 动态调整
```

### 1.2 目标用户限定

本规格书中的默认用户群体为：

- 中国普通高中高一、高二、高三学生；
- 参加普通高等学校招生全国统一考试；
- 统一考试部分采用新高考全国Ⅰ卷；
- 学习目标通常与校内教学、阶段考试、联考、模拟考试和高考相关；
- 需要兼容不同省份的选科、赋分、教材、校历和考试安排。

### 1.3 考试体系建模原则

系统将“全国一卷”标准化为考试配置 `NEW_GAOKAO_NATIONAL_I`，不得仅使用自然语言字符串进行判断。

在常见“3+1+2”模式下：

- 语文、数学、外语属于全国统一高考科目；
- 物理、历史中选择一门作为首选科目；
- 思想政治、地理、化学、生物学中选择两门作为再选科目；
- 选择性考试的命题、原始分或等级赋分规则，需要通过省级配置管理；
- 系统不得把省份名单、考试日期、赋分公式或教材版本写死在 Agent Prompt 中。

系统应通过 `ExamPolicyService` 按省份、入学年份和考试年份读取当前有效政策。

### 1.4 设计原则

#### 1.4.1 最小必要信息原则

首次使用只收集生成首版计划必需的信息，其他信息通过后续行为逐步补全。

#### 1.4.2 证据驱动原则

每一个知识判断、任务安排和计划调整，都必须能够追溯到目标、测评、练习、知识图谱、时间容量或教师约束。

#### 1.4.3 LLM 与确定性工具分工

LLM 负责：

- 理解自然语言目标；
- 识别模糊表达；
- 生成追问；
- 生成面向学生和教师的解释；
- 组织工具调用。

确定性工具负责：

- 考试政策查询；
- 知识图谱检索；
- 掌握度计算；
- 测评选题与评分；
- 时间容量计算；
- 任务工时估算；
- 排期优化；
- 规则校验；
- 计划版本管理。

#### 1.4.4 高考目标与日常学习统一原则

系统同时维护：

- 长期目标：高考总分、单科目标、目标院校或专业要求；
- 中期目标：学期目标、联考目标、模考目标、阶段知识覆盖；
- 短期目标：周计划、日任务、知识点修复和错题复习。

短期计划必须服务于中长期目标，不能只根据最近一次练习机械推荐题目。

---

## 2. Agent 总体定义

### 2.1 Agent 名称

```text
PersonalizedLearningPlannerAgent
```

### 2.2 核心职责

Agent 负责：

- 首次用户信息采集；
- 高考考试配置识别；
- 目标结构化与可行性评估；
- 学情诊断测评编排；
- 知识画像构建与更新；
- 练习表现量化；
- 学习时间和效率建模；
- 知识路径规划；
- 阶段、周、日计划生成；
- 计划执行监控；
- 动态调整；
- 学生版和教师版解释；
- 风险预警与人工协同。

### 2.3 非职责范围

以下能力由其他 Agent 或服务负责：

| 能力 | 负责组件 |
|---|---|
| 知识讲解 | 教学讲解 Agent |
| 题目生成 | 题目生成 Agent |
| 主观题批改 | 评价与批改 Agent |
| 作文精批 | 作文批改 Agent |
| 学习情绪陪伴 | 学习陪伴 Agent |
| 志愿与专业推荐 | 生涯规划 Agent |
| 教师班级管理 | 教师辅助 Agent |
| 内容安全审核 | 教学内容审核服务 |

规划 Agent 可以调用上述组件，但不得伪造其专业结果。

### 2.4 Agent 状态机

```text
NEW
  ↓
ONBOARDING
  ↓
GOAL_COLLECTING
  ↓
GOAL_READY
  ↓
ASSESSMENT_PENDING
  ↓
KNOWLEDGE_PROFILE_READY
  ↓
TIME_PROFILE_READY
  ↓
PLAN_GENERATING
  ↓
PLAN_DRAFT
  ↓
WAITING_FOR_CONFIRMATION
  ↓
PLAN_ACTIVE
  ↓
PLAN_ADJUST_PENDING
  ↓
PLAN_ACTIVE
  ↓
STAGE_COMPLETED
  ↓
PLAN_COMPLETED
```

补充状态：

- `PAUSED`：学生暂停学习；
- `WAITING_FOR_DATA`：缺少必要信息；
- `DATA_CONFLICT_PENDING`：数据冲突待处理；
- `MANUAL_REVIEW_REQUIRED`：需要教师或运营人员干预；
- `FAILED`：关键工具失败且无可用降级路径。

---

## 3. 总体系统架构

### 3.1 逻辑架构

```text
学生端 / 教师端 / 家长授权端 / 教务系统
                    │
                    ▼
       PersonalizedLearningPlannerAgent
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
目标与政策工具   学情画像工具    时间建模工具
      │             │             │
      └─────────────┼─────────────┘
                    ▼
             学习计划生成引擎
                    │
   ┌────────────────┼────────────────┐
   ▼                ▼                ▼
知识图谱服务    内容资源服务      排期优化服务
   │                │                │
   └────────────────┼────────────────┘
                    ▼
       计划仓库 / 学习事件总线 / 审计服务
                    │
                    ▼
练习系统 / 测评系统 / 批改 Agent / 教师 Agent / 通知服务
```

### 3.2 核心依赖服务

| 服务 | 职责 |
|---|---|
| IdentityService | 用户身份、学校、年级和角色识别 |
| ConsentService | 未成年人数据授权和数据范围管理 |
| ExamPolicyService | 高考模式、省份政策、科目、赋分和考试节点配置 |
| StudentProfileService | 学生基础信息、选科、偏好和约束 |
| GoalService | 学习目标和目标版本管理 |
| KnowledgeGraphService | 课程知识点、前置依赖、题型和能力关系 |
| KnowledgeTracingService | 学生知识掌握度和遗忘风险更新 |
| AssessmentService | 测评蓝图、选题、会话和评分 |
| PracticeEventService | 练习行为事件接收和标准化 |
| ContentResourceService | 视频、讲义、例题、习题、试卷和错题资源 |
| CalendarService | 校历、课程表、考试和个人学习时间 |
| SchedulingSolver | 约束排期和增量重排 |
| PlanRepository | 计划、阶段、任务和版本存储 |
| NotificationService | 学习提醒、风险提示和调整通知 |
| AuditService | Agent 决策、工具调用和版本差异审计 |

---

## 4. 新高考全国Ⅰ卷考试配置

### 4.1 考试配置模型

```json
{
  "exam_profile_id": "NEW_GAOKAO_NATIONAL_I_2027_HUNAN",
  "exam_system": "new_gaokao",
  "national_paper_type": "national_paper_i",
  "province_code": "43",
  "cohort_entry_year": 2024,
  "exam_year": 2027,
  "subject_model": "3_plus_1_plus_2",
  "compulsory_subjects": [
    "chinese",
    "mathematics",
    "foreign_language"
  ],
  "first_choice_subjects": [
    "physics",
    "history"
  ],
  "second_choice_subjects": [
    "ideology_politics",
    "geography",
    "chemistry",
    "biology"
  ],
  "selected_subjects": [
    "physics",
    "chemistry",
    "biology"
  ],
  "score_rules": {
    "chinese": "raw_score",
    "mathematics": "raw_score",
    "foreign_language": "raw_score",
    "physics": "province_configured",
    "chemistry": "province_configured",
    "biology": "province_configured"
  },
  "policy_version": "policy_2026_07",
  "effective_date": "2026-07-01"
}
```

### 4.2 必须支持的科目

```text
chinese             语文
mathematics         数学
foreign_language    外语
physics             物理
history             历史
ideology_politics   思想政治
geography           地理
chemistry           化学
biology             生物学
```

外语语种、听力考试组织方式和考试次数必须由省级配置决定。

### 4.3 省级差异配置

以下数据不得写死：

- 适用省份；
- 选科模式；
- 选择性考试命题方；
- 等级赋分方式；
- 外语听力考试安排；
- 高考具体日期；
- 模拟考试安排；
- 教材版本；
- 学业水平合格性考试要求；
- 高校专业选考科目要求。

### 4.4 政策工具

#### `exam_policy_resolve`

**定位：** 根据学生省份、入学年份、考试年份识别适用考试政策。

**输入：**

```json
{
  "province_code": "43",
  "school_entry_year": 2024,
  "expected_gaokao_year": 2027
}
```

**输出：**

```json
{
  "exam_profile_id": "NEW_GAOKAO_NATIONAL_I_2027_HUNAN",
  "national_paper_type": "national_paper_i",
  "subject_model": "3_plus_1_plus_2",
  "available_subject_combinations": [],
  "score_rules": {},
  "official_exam_milestones": [],
  "policy_version": "policy_2026_07",
  "status": "active"
}
```

#### `exam_policy_validate`

**定位：** 在生成计划前检查考试配置是否过期或存在冲突。

当政策版本过期、学生省份缺失、选科组合非法时，不得发布正式高考计划。

---

## 5. 核心领域数据模型

### 5.1 学生基础画像 `StudentAcademicProfile`

```json
{
  "student_id": "student_10001",
  "grade": "grade_11",
  "school_term": "grade_11_term_1",
  "province_code": "43",
  "school_type": "public_high_school",
  "curriculum_versions": {
    "mathematics": "people_education_a",
    "physics": "people_education"
  },
  "exam_profile_id": "NEW_GAOKAO_NATIONAL_I_2027_HUNAN",
  "selected_subjects": [
    "physics",
    "chemistry",
    "biology"
  ],
  "class_progress": {},
  "target_exam_year": 2027,
  "profile_version": 6
}
```

### 5.2 学习目标 `LearningGoal`

```json
{
  "goal_id": "goal_001",
  "student_id": "student_10001",
  "goal_type": "gaokao_subject_score",
  "subject": "mathematics",
  "target": {
    "metric": "mock_exam_score",
    "current_value": 92,
    "target_value": 120,
    "unit": "score"
  },
  "deadline": "2027-05-20",
  "priority": 1,
  "exam_context": {
    "exam_profile_id": "NEW_GAOKAO_NATIONAL_I_2027_HUNAN",
    "exam_type": "third_mock_exam"
  },
  "scope": {
    "included_domains": [
      "functions",
      "analytic_geometry",
      "probability_statistics"
    ]
  },
  "status": "active",
  "confidence": 0.94,
  "version": 3
}
```

### 5.3 知识状态 `KnowledgeState`

```json
{
  "student_id": "student_10001",
  "subject": "mathematics",
  "knowledge_id": "math_function_derivative_application",
  "mastery_probability": 0.64,
  "mastery_level": "developing",
  "confidence": 0.82,
  "evidence_count": 18,
  "last_practiced_at": "2026-07-28T20:10:00+08:00",
  "forgetting_risk": 0.31,
  "prerequisite_status": "partial_gap",
  "error_tags": [
    "monotonicity_interval_error"
  ],
  "model_version": "bkt_v3.2"
}
```

### 5.4 学习任务 `PlanTask`

```json
{
  "task_id": "task_001",
  "plan_id": "plan_001",
  "stage_id": "stage_001",
  "subject": "mathematics",
  "task_type": "targeted_practice",
  "knowledge_ids": [
    "math_function_derivative_application"
  ],
  "content_ids": [
    "content_example_322",
    "item_set_501"
  ],
  "planned_start": "2026-07-30T19:00:00+08:00",
  "planned_duration_minutes": 40,
  "difficulty": 0.62,
  "exam_relevance": 0.86,
  "completion_rule": {
    "minimum_item_count": 8,
    "minimum_accuracy": 0.75,
    "maximum_hint_dependency": 0.25
  },
  "flexibility": "movable_within_week",
  "status": "scheduled"
}
```

### 5.5 学习计划 `LearningPlan`

```json
{
  "plan_id": "plan_001",
  "student_id": "student_10001",
  "goal_ids": [
    "goal_001"
  ],
  "version": 3,
  "status": "active",
  "plan_start": "2026-07-30",
  "plan_end": "2027-05-20",
  "exam_profile_id": "NEW_GAOKAO_NATIONAL_I_2027_HUNAN",
  "stages": [],
  "weekly_capacity_minutes": 960,
  "scheduled_minutes": 780,
  "buffer_minutes": 180,
  "generation_basis": {
    "knowledge_profile_version": "kp_18",
    "time_profile_version": "tp_6",
    "goal_version": "gv_3",
    "policy_version": "policy_2026_07",
    "algorithm_version": "planner_v2.1"
  }
}
```

---

## 6. 统一工具调用协议

### 6.1 请求结构

```json
{
  "request_id": "req_20260729_000001",
  "trace_id": "trace_student_10001_init_01",
  "student_id": "student_10001",
  "scenario": "initialization",
  "operator": {
    "type": "agent",
    "id": "personalized_learning_planner_agent"
  },
  "data_version": "v12",
  "idempotency_key": "student_10001_goal_parse_v3",
  "requested_at": "2026-07-29T12:00:00+08:00",
  "payload": {}
}
```

### 6.2 响应结构

```json
{
  "request_id": "req_20260729_000001",
  "status": "success",
  "result": {},
  "warnings": [],
  "errors": [],
  "evidence": [],
  "data_version": "v13",
  "completed_at": "2026-07-29T12:00:01+08:00"
}
```

### 6.3 标准状态

- `success`
- `partial_success`
- `need_more_information`
- `conflict`
- `failed`
- `manual_review_required`

### 6.4 工具调用约束

1. 所有输入通过 JSON Schema 校验；
2. 写操作必须携带幂等键；
3. 输出必须包含证据和数据版本；
4. Agent 不得将推测值作为用户事实写入；
5. 关键数据冲突必须显式返回；
6. 计划更新必须创建新版本；
7. 发布前必须通过政策、知识依赖、时间容量和内容可用性校验。

---

# 7. 模块一：学生目标采集模块

## 7.1 模块定位

负责将高中生、教师或家长提出的模糊目标，转换为可量化、可校验、可追踪的结构化目标。

高中场景中的典型目标包括：

- 提高校内月考、期中、期末或联考成绩；
- 提高高考单科成绩；
- 提高高考总分；
- 完成一轮、二轮或冲刺复习；
- 修复某个知识模块；
- 改善某类题型；
- 提升答题速度、规范性或稳定性；
- 达到目标院校或专业的选科与成绩要求。

## 7.2 子任务拆解

| 编号 | 子任务 | 处理逻辑 | 工具类型 |
|---|---|---|---|
| G1 | 目标来源识别 | 区分学生、教师、家长和教务来源 | 身份权限工具 |
| G2 | 考试上下文识别 | 识别月考、联考、模考、高考和考试年份 | 政策与考试日历工具 |
| G3 | 原始目标采集 | 接收自然语言、表单或教师配置 | 对话表单工具 |
| G4 | 目标语义解析 | 提取科目、指标、当前值、目标值、期限 | LLM 结构化抽取工具 |
| G5 | 模糊项检测 | 检测“提高数学”“冲重点”等不可计算表达 | 规则校验工具 |
| G6 | 智能追问 | 询问最影响规划的缺失字段 | LLM 追问工具 |
| G7 | 目标拆解 | 拆分长期、中期、短期和过程目标 | 目标分解工具 |
| G8 | 科目目标一致性校验 | 检查目标与选科、年级和课程进度一致性 | 政策规则工具 |
| G9 | 目标可行性评估 | 根据基础、时间、历史提升速度进行评估 | 预测与规则工具 |
| G10 | 多目标冲突检测 | 检查总分、单科和时间资源冲突 | 约束检测工具 |
| G11 | 目标确认与版本化 | 展示系统理解结果并持久化 | 目标存储工具 |

## 7.3 工具设计

### 7.3.1 `goal_source_resolve`

**输入：**

```json
{
  "student_id": "student_10001",
  "submitted_by": {
    "actor_type": "teacher",
    "actor_id": "teacher_302"
  },
  "raw_goal": "高三一模数学达到120分"
}
```

**输出：**

```json
{
  "source_type": "teacher",
  "source_priority": 0.9,
  "write_permission": true,
  "student_confirmation_required": true
}
```

### 7.3.2 `goal_parse`

**处理逻辑：**

1. 识别考试类型；
2. 识别考试年份和节点；
3. 识别科目和选科上下文；
4. 提取当前分、目标分、截止日期；
5. 识别题型、知识域和能力目标；
6. 输出字段级置信度；
7. 不确定内容放入 `missing_fields`。

**输入：**

```json
{
  "text": "我现在高二，数学月考大约90分，希望高三一模达到120分，每天最多学一个半小时。",
  "context": {
    "current_date": "2026-07-29",
    "grade": "grade_11",
    "exam_profile_id": "NEW_GAOKAO_NATIONAL_I_2027_HUNAN"
  }
}
```

**输出：**

```json
{
  "goal_type": "mock_exam_subject_score",
  "subject": "mathematics",
  "current_value": 90,
  "target_value": 120,
  "deadline_event": "grade_12_first_mock",
  "daily_time_limit_minutes": 90,
  "missing_fields": [
    "mock_exam_date",
    "current_score_total"
  ],
  "field_confidence": {
    "subject": 0.99,
    "target_value": 0.99,
    "deadline_event": 0.91
  }
}
```

### 7.3.3 `goal_clarification_generate`

规则：

- 每轮最多询问两个问题；
- 优先询问目标值、截止节点、当前值和科目；
- 不重复询问已知字段；
- 能从考试日历读取的字段不让学生重复填写；
- 提供单选、多选或数字输入以降低负担。

### 7.3.4 `goal_decompose`

将高考目标拆解为：

```text
高考或模考结果目标
├── 单科分数目标
│   ├── 知识模块掌握目标
│   ├── 题型得分目标
│   ├── 速度目标
│   └── 规范性目标
└── 过程目标
    ├── 周有效学习时长
    ├── 计划完成率
    ├── 错题回收率
    └── 阶段测评要求
```

**输出示例：**

```json
{
  "result_goal": {
    "metric": "mock_exam_math_score",
    "target": 120
  },
  "competency_goals": [
    {
      "competency": "function_and_derivative",
      "target_mastery": 0.82
    },
    {
      "competency": "analytic_geometry",
      "target_mastery": 0.78
    }
  ],
  "exam_skill_goals": [
    {
      "metric": "multiple_choice_time_minutes",
      "target": 35
    }
  ],
  "process_goals": [
    {
      "metric": "weekly_effective_learning_minutes",
      "target": 420
    },
    {
      "metric": "weekly_plan_completion_rate",
      "target": 0.9
    }
  ]
}
```

### 7.3.5 `goal_feasibility_evaluate`

```text
FeasibilityScore
= 0.25 × 时间充分度
+ 0.25 × 当前基础匹配度
+ 0.20 × 历史提升效率
+ 0.15 × 目标增幅合理性
+ 0.10 × 计划执行稳定性
+ 0.05 × 内容资源可获得性
```

输出等级：

- `feasible`：≥ 0.75；
- `challenging_but_possible`：0.50—0.74；
- `high_risk`：< 0.50。

目标高风险时，Agent 应提供：

- 可实现的目标区间；
- 需要增加的周学习时间；
- 建议延长的期限；
- 应优先提升的科目或模块；
- 保持原目标的风险。

### 7.3.6 `goal_conflict_detect`

检测：

- 高考总分目标与单科目标不一致；
- 多科目标所需时间超过容量；
- 学校教学进度与学生超前计划冲突；
- 目标专业选科要求与当前选科不一致；
- 教师目标与学生目标冲突；
- 目标日期早于当前日期或考试节点不存在。

## 7.4 模块输入输出规范

**输入：**

```json
{
  "student_id": "student_10001",
  "goal_text": "高三一模数学考到120分",
  "source": "student",
  "exam_profile_id": "NEW_GAOKAO_NATIONAL_I_2027_HUNAN"
}
```

**输出：**

```json
{
  "goal_status": "confirmed",
  "goal": {},
  "sub_goals": [],
  "feasibility": {},
  "conflicts": [],
  "next_action": "start_baseline_assessment"
}
```

---

# 8. 模块二：知识基础测评模块

## 8.1 模块定位

评估学生当前知识、能力和高考题型表现，定位：

- 已掌握知识；
- 薄弱知识；
- 前置知识漏洞；
- 易错题型；
- 审题、计算、表达和时间分配问题；
- 学校当前进度与个人实际掌握之间的差异。

输出不能只有总分，必须形成知识点、题型和能力三级画像。

## 8.2 高中知识画像层级

```text
学科
├── 主题域
│   ├── 单元
│   │   ├── 知识点
│   │   ├── 方法
│   │   └──易错点
├── 高考题型
├── 核心能力
└── 考试表现
```

示例：

```text
数学
├── 函数
│   ├── 函数性质
│   ├── 导数
│   └── 函数零点
├── 选择题
├── 数学运算能力
└── 时间分配稳定性
```

## 8.3 子任务拆解

| 编号 | 子任务 | 处理逻辑 | 工具类型 |
|---|---|---|---|
| K1 | 历史数据读取 | 读取校内考试、联考、作业和练习 | 学习记录查询工具 |
| K2 | 试卷结构化 | 将历史试卷映射到知识点、题型、难度 | 试卷解析工具 |
| K3 | 目标知识域抽取 | 根据目标和考试大纲确定诊断范围 | 知识图谱工具 |
| K4 | 证据充分度评估 | 判断是否需要快速、标准或完整诊断 | 证据质量工具 |
| K5 | 测评蓝图生成 | 按知识、题型、难度和时间生成蓝图 | 测评规划工具 |
| K6 | 自适应选题 | 最大化信息增益并保证覆盖 | CAT/IRT 工具 |
| K7 | 答题评分 | 客观题自动评分，主观题调用批改 Agent | 评分工具 |
| K8 | 掌握度推断 | 融合历史成绩和本次测评 | 知识追踪工具 |
| K9 | 错因识别 | 区分知识、方法、审题、计算、表达错误 | 错因分类工具 |
| K10 | 前置漏洞检测 | 沿知识图谱回溯依赖漏洞 | 图谱诊断工具 |
| K11 | 题型能力画像 | 统计各题型得分率、耗时和稳定性 | 学习分析工具 |
| K12 | 标准化画像构建 | 输出知识、题型、能力三级画像 | 画像工具 |
| K13 | 画像质量校验 | 检测覆盖不足、证据冲突和低置信度 | 校验工具 |

## 8.4 工具设计

### 8.4.1 `learning_history_query`

查询范围：

- 月考、期中、期末；
- 市统考、联考；
- 一模、二模、三模；
- 校内作业；
- 平台练习；
- 错题本；
- 教师评价；
- 历史学习计划执行数据。

### 8.4.2 `exam_paper_evidence_extract`

**输入：**

```json
{
  "paper_id": "paper_2026_city_joint_math_01",
  "student_answers": [],
  "scoring_results": []
}
```

**输出：**

```json
{
  "subject": "mathematics",
  "total_score": 94,
  "knowledge_evidence": [],
  "question_type_evidence": [],
  "time_evidence": [],
  "mapping_confidence": 0.91
}
```

### 8.4.3 `knowledge_scope_resolve`

根据：

- 高考考试配置；
- 当前年级；
- 学校教学进度；
- 学生目标；
- 教材版本；
- 目标考试范围；

生成待诊断知识子图。

### 8.4.4 `assessment_evidence_sufficiency_check`

一个知识点可以跳过完整诊断的参考条件：

- 最近 30 天存在有效证据；
- 有效作答不少于 8 次；
- 难度覆盖不少于两个等级；
- 至少包含一次独立测评；
- 掌握度置信度不低于 0.80；
- 无明显退步和高遗忘风险。

### 8.4.5 `assessment_mode_select`

| 模式 | 场景 | 时长 |
|---|---|---:|
| `quick` | 历史数据完整，仅验证关键模块 | 5—10 分钟 |
| `standard` | 有部分历史证据 | 15—25 分钟 |
| `full` | 无历史数据或跨模块目标 | 25—45 分钟 |
| `paper_based` | 使用一套完整模拟卷评估 | 按学科考试时长 |

### 8.4.6 `assessment_blueprint_generate`

蓝图必须约束：

- 目标知识覆盖；
- 前置知识覆盖；
- 高考常见题型覆盖；
- 难度梯度；
- 主客观题比例；
- 最大测评时长；
- 学生当前学习进度。

### 8.4.7 `adaptive_item_select`

```text
ItemPriority
= 信息增益
× 知识覆盖缺口
× 难度匹配度
× 高考相关度
× 题目质量
× 内容新鲜度
```

### 8.4.8 `mastery_infer`

推荐策略：

- 冷启动：IRT + 规则先验；
- 日常更新：BKT、DKT 或 AKT；
- 数据不足：贝叶斯平滑；
- 模型不可用：基于加权证据的规则降级。

### 8.4.9 `prerequisite_gap_detect`

```text
GapRisk
= 前置关系强度
× 当前知识缺口
× 下游影响节点数
× 高考目标相关度
```

输出必须给出：

- 漏洞知识点；
- 直接或间接前置关系；
- 当前掌握度；
- 影响的下游知识点；
- 建议修复顺序。

### 8.4.10 `exam_skill_profile_build`

除知识掌握度外，还要建立：

- 选择题得分率；
- 多选题漏选和错选模式；
- 主观题步骤完整性；
- 语文阅读和作文分项；
- 外语听力、阅读、写作分项；
- 理科实验与计算能力；
- 文科材料分析与表达能力；
- 整卷时间分配；
- 非智力失分率。

## 8.5 模块输入输出规范

**输入：**

```json
{
  "student_id": "student_10001",
  "goal_ids": [
    "goal_001"
  ],
  "exam_profile_id": "NEW_GAOKAO_NATIONAL_I_2027_HUNAN",
  "historical_data_window_days": 180,
  "max_assessment_minutes": 30
}
```

**输出：**

```json
{
  "profile_id": "kp_001",
  "profile_version": 18,
  "knowledge_states": [],
  "question_type_states": [],
  "exam_skill_states": [],
  "priority_gaps": [],
  "prerequisite_gaps": [],
  "assessment_quality": {
    "coverage": 0.91,
    "confidence": 0.84
  },
  "next_action": "build_time_profile"
}
```

---

# 9. 模块三：练习表现量化模块

## 9.1 模块定位

将作业、刷题、错题重做、限时训练和模拟考试中的原始行为转化为可用于知识追踪和计划调整的学习证据。

不得使用单一正确率代表掌握度，应综合：

- 难度；
- 题型；
- 作答时间；
- 提示依赖；
- 重试次数；
- 解题步骤；
- 保持能力；
- 迁移能力；
- 时间压力；
- 非智力失分；
- 是否独立完成。

## 9.2 子任务拆解

| 编号 | 子任务 | 处理逻辑 | 工具类型 |
|---|---|---|---|
| P1 | 事件接收 | 接收答题、提示、暂停、订正和提交事件 | 事件工具 |
| P2 | 格式标准化 | 转换为统一学习事件 | ETL 工具 |
| P3 | 去重 | 按事件 ID 和幂等键去重 | 去重工具 |
| P4 | 异常检测 | 检测秒答、抄答案、挂时长和批量提交 | 异常检测工具 |
| P5 | 有效时长计算 | 扣除失焦、暂停和无交互时间 | 时长清洗工具 |
| P6 | 特征提取 | 计算正确性、速度、难度校正表现 | 特征工具 |
| P7 | 错因分类 | 识别知识、方法、计算、审题和表达错误 | 错因工具 |
| P8 | 证据权重计算 | 根据独立性和题目质量赋权 | 证据评分工具 |
| P9 | 掌握度更新 | 调用知识追踪模型 | 知识追踪工具 |
| P10 | 趋势分析 | 检测进步、波动、退步和遗忘 | 时序分析工具 |
| P11 | 计划执行对比 | 比较计划任务和实际表现 | 监控工具 |
| P12 | 高考失分归因 | 估算知识性和非知识性失分 | 考试分析工具 |

## 9.3 量化维度

| 维度 | 指标 |
|---|---|
| 正确性 | `accuracy` |
| 难度适应 | `difficulty_adjusted_score` |
| 作答速度 | `normalized_response_time` |
| 稳定性 | `performance_stability` |
| 提示依赖 | `hint_dependency` |
| 重试依赖 | `retry_dependency` |
| 保持能力 | `retention_score` |
| 迁移能力 | `transfer_score` |
| 错误重复度 | `repeated_error_rate` |
| 计划完成度 | `completion_rate` |
| 专注质量 | `engagement_quality` |
| 独立完成度 | `independent_completion` |
| 步骤规范性 | `solution_process_quality` |
| 时间压力表现 | `time_pressure_score` |
| 非智力失分 | `avoidable_error_rate` |

## 9.4 工具设计

### 9.4.1 `practice_event_ingest`

```json
{
  "event_id": "evt_001",
  "student_id": "student_10001",
  "session_id": "practice_session_301",
  "task_id": "task_001",
  "item_id": "item_5001",
  "subject": "mathematics",
  "knowledge_ids": [
    "math_derivative_application"
  ],
  "event_type": "answer_submitted",
  "timestamp": "2026-07-29T20:11:31+08:00",
  "response": {
    "correct": true,
    "score": 5,
    "max_score": 5
  },
  "behavior": {
    "response_time_seconds": 482,
    "hint_count": 1,
    "attempt_count": 1,
    "pause_seconds": 25
  }
}
```

### 9.4.2 `practice_data_clean`

噪声规则：

- 秒答低于题目最小合理时长时标记 `rapid_guessing`；
- 超长停留使用有效交互区间替代；
- 页面失焦超过阈值的时间不计入有效时长；
- 同一事件不得重复更新画像；
- 答案查看后提交降低独立性权重；
- 主观题缺少过程时，不得以满权重证明方法掌握。

### 9.4.3 `practice_feature_extract`

```text
PracticeQuality
= 0.25 × 难度校正正确性
+ 0.15 × 速度合理性
+ 0.15 × 独立完成度
+ 0.15 × 稳定性
+ 0.10 × 保持能力
+ 0.10 × 迁移能力
+ 0.10 × 步骤规范性
```

权重按学科和题型配置。

### 9.4.4 `practice_error_classify`

标准错误类型：

- `knowledge_missing`
- `concept_confusion`
- `method_selection_error`
- `procedure_error`
- `calculation_error`
- `reading_error`
- `careless_error`
- `representation_error`
- `time_pressure_error`
- `answer_format_error`
- `unknown`

### 9.4.5 `practice_evidence_weight`

```text
EvidenceWeight
= ReliabilityScore
× ItemDiscrimination
× DifficultyInformation
× IndependenceScore
× FreshnessWeight
× ExamRelevance
```

### 9.4.6 `mastery_dynamic_update`

输出：

```json
{
  "knowledge_id": "math_derivative_application",
  "old_mastery": 0.64,
  "new_mastery": 0.71,
  "change": 0.07,
  "confidence": 0.85,
  "trend": "improving",
  "trigger_replan_check": true
}
```

### 9.4.7 `exam_loss_attribution`

将试卷失分拆分为：

- 知识缺口失分；
- 方法选择失分；
- 计算失分；
- 审题失分；
- 表达规范失分；
- 时间不足失分；
- 空题失分；
- 随机波动。

该结果用于判断应增加知识学习、限时训练还是规范性训练。

## 9.5 模块输入输出规范

```json
{
  "processed_event_count": 32,
  "invalid_event_count": 2,
  "knowledge_updates": [],
  "practice_summary": {
    "effective_minutes": 46,
    "completion_rate": 0.92,
    "quality_score": 0.78,
    "avoidable_error_rate": 0.12
  },
  "plan_deviations": [],
  "replan_check_required": true
}
```

---

# 10. 模块四：学习时间适配模块

## 10.1 模块定位

将高中生的课程表、早晚自习、学校作业、走班、周末安排和自主学习时间，转换为可用于排期的有效学习容量。

高中生时间具有以下特点：

- 学校固定时间多；
- 作业量随年级和考试周期波动；
- 高三存在一轮、二轮、冲刺等显著阶段；
- 晚间学习精力有限；
- 多科之间竞争时间；
- 节假日、月考和联考会显著改变容量。

## 10.2 子任务拆解

| 编号 | 子任务 | 处理逻辑 | 工具类型 |
|---|---|---|---|
| T1 | 课表和校历读取 | 获取上课、早晚自习、考试和假期 | 日历工具 |
| T2 | 自主时间采集 | 收集平日、周末和假期时间 | 表单工具 |
| T3 | 多来源日历合并 | 合并学校、学生和计划任务 | 日历整合工具 |
| T4 | 时间冲突检测 | 检测重叠和时区问题 | 时间规则工具 |
| T5 | 精力时段建模 | 建模早晨、中午、晚间精力 | 偏好分析工具 |
| T6 | 历史效率估算 | 比较预计时长和实际时长 | 效率分析工具 |
| T7 | 有效容量计算 | 将自然时间转换为有效容量 | 容量计算工具 |
| T8 | 多科时间分配 | 按目标和缺口分配各科时间 | 优化工具 |
| T9 | 任务负荷匹配 | 按难度、题型和精力估算工时 | 工时工具 |
| T10 | 弹性空间分配 | 预留补作业、错题和突发时间 | 缓冲工具 |
| T11 | 容量变化监控 | 检测考试周和作业量变化 | 事件工具 |

## 10.3 工具设计

### 10.3.1 `availability_collect`

首次采集：

- 平日自主时间；
- 周末自主时间；
- 早晚自习可自主支配比例；
- 单次最长专注时间；
- 固定培训或竞赛时间；
- 周末是否可补学；
- 每周最少休息时段。

### 10.3.2 `school_calendar_merge`

优先级：

1. 正式考试和学校课程；
2. 学校统一晚自习；
3. 教师强制任务；
4. 不可移动个人事件；
5. 已发布学习任务；
6. 可移动自主学习任务。

### 10.3.3 `learning_efficiency_infer`

按任务类型分别建模：

- 课本预习；
- 知识讲解；
- 基础题；
- 高考真题；
- 主观题书写；
- 作文；
- 听力；
- 错题复习；
- 整卷训练。

```text
EfficiencyFactor
= 标准预计时长 / 学生实际有效完成时长
```

使用最近同类任务的加权中位数，避免单次异常影响。

### 10.3.4 `effective_capacity_estimate`

```text
EffectiveCapacity
= NaturalAvailableMinutes
× EfficiencyFactor
× EnergyCoefficient
× ExecutionReliability
- SwitchingCost
```

### 10.3.5 `subject_time_budget_allocate`

```text
SubjectBudget
∝ GoalPriority
× ScoreGap
× ExpectedScoreGain
× Urgency
× KnowledgeDependency
```

同时满足：

- 每个高考科目最低维护时间；
- 弱科获得足够修复时间；
- 优势科不因完全停练发生遗忘；
- 高考前按考试日程和模考表现动态调整。

### 10.3.6 `task_effort_estimate`

```text
EstimatedDuration
= BaseDuration
× DifficultyAdjustment
× KnowledgeGapAdjustment
× TaskTypeEfficiencyAdjustment
× WritingLoadAdjustment
```

### 10.3.7 `elastic_buffer_allocate`

默认建议：

| 场景 | 缓冲比例 |
|---|---:|
| 高一、高二稳定期 | 15%—20% |
| 新计划第一周 | 20%—25% |
| 高三一轮 | 15%—20% |
| 高三二轮 | 10%—15% |
| 临近大考 | 10%—20% |
| 时间高度不稳定 | 25%—35% |

缓冲时间不得提前全部排满。

## 10.4 模块输入输出规范

```json
{
  "time_profile_id": "tp_001",
  "weekly_natural_minutes": 1200,
  "weekly_effective_minutes": 980,
  "recommended_scheduled_minutes": 800,
  "buffer_minutes": 180,
  "subject_budgets": {
    "mathematics": 280,
    "physics": 180,
    "english": 140,
    "chinese": 100,
    "chemistry": 60,
    "biology": 40
  },
  "daily_capacity": [],
  "efficiency_by_task_type": {},
  "constraints": []
}
```

---

# 11. 模块五：学习计划生成引擎

## 11.1 模块定位

综合目标、考试配置、知识画像、练习表现、学校进度、内容资源和时间容量，生成长期阶段计划、周计划和日任务。

## 11.2 子任务拆解

| 编号 | 子任务 | 处理逻辑 | 工具类型 |
|---|---|---|---|
| L1 | 目标知识子图构建 | 提取目标知识和前置依赖 | 图谱工具 |
| L2 | 缺口优先级计算 | 综合缺口、考试权重和依赖影响 | 优先级工具 |
| L3 | 学习路径生成 | 满足前置关系和校内进度 | 图路径工具 |
| L4 | 复习阶段识别 | 识别同步学习、一轮、二轮、冲刺 | 阶段工具 |
| L5 | 阶段划分 | 生成阶段目标和完成条件 | 阶段规划工具 |
| L6 | 候选任务生成 | 生成学习、训练、复习、测评任务 | 任务模板工具 |
| L7 | 内容匹配 | 匹配教材、例题、真题和模拟题 | 检索工具 |
| L8 | 工时估算 | 个体化估算任务时间 | 工时工具 |
| L9 | 多科排期 | 分配到具体日期和时段 | 排期工具 |
| L10 | 间隔复习插入 | 根据遗忘风险安排复习 | 复习调度工具 |
| L11 | 限时训练插入 | 根据考试技能缺口安排限时任务 | 考试训练工具 |
| L12 | 阶段测评插入 | 安排专题测验和整卷模拟 | 测评工具 |
| L13 | 完整性校验 | 检查政策、知识、时间和内容 | 校验工具 |
| L14 | 解释生成 | 生成学生和教师版本 | LLM 工具 |
| L15 | 动态触发评估 | 判断调整级别 | 规则工具 |
| L16 | 增量调整 | 调整当天或本周 | 增量排期工具 |
| L17 | 阶段重规划 | 重建剩余阶段 | 全量重规划工具 |
| L18 | 版本发布 | 保存并通知相关角色 | 存储通知工具 |

## 11.3 知识优先级

```text
KnowledgePriority
= 0.22 × GoalRelevance
+ 0.18 × MasteryGap
+ 0.15 × PrerequisiteCentrality
+ 0.15 × ExamImportance
+ 0.10 × ErrorFrequency
+ 0.08 × ForgettingRisk
+ 0.07 × SchoolProgressUrgency
+ 0.05 × TeacherPriority
```

强前置节点即使直接分值较低，也必须优先修复。

## 11.4 高中阶段划分

### 11.4.1 高一

重点：

- 适应高中课程难度；
- 建立学科知识体系；
- 形成稳定学习习惯；
- 识别选科倾向；
- 防止基础知识累积漏洞。

计划周期以校内同步和单元闭环为主。

### 11.4.2 高二

重点：

- 完成核心课程学习；
- 稳定选科组合；
- 加强跨章节综合；
- 提前修复高一遗留问题；
- 建立高考题型意识。

计划周期采用“同步学习 + 周期回顾 + 专题提升”。

### 11.4.3 高三一轮复习

重点：

- 全面覆盖；
- 体系重建；
- 基础和中档题稳定；
- 错题归因；
- 形成知识网络。

### 11.4.4 高三二轮复习

重点：

- 专题突破；
- 跨模块综合；
- 高频题型；
- 限时训练；
- 提升得分效率。

### 11.4.5 高三冲刺

重点：

- 整卷模拟；
- 时间分配；
- 规范表达；
- 高频错误压缩；
- 优势保持；
- 避免大规模学习低收益新内容。

## 11.5 阶段完成条件

```text
阶段任务完成率 ≥ 阈值
且核心知识掌握度 ≥ 阶段目标
且阶段测评达到最低要求
且不存在高风险强前置漏洞
且考试技能指标满足阶段要求
```

## 11.6 候选任务类型

```text
课前预习
→ 概念学习
→ 典型例题
→ 基础练习
→ 错误修复
→ 变式训练
→ 高考真题
→ 限时训练
→ 间隔复习
→ 专题测验
→ 整卷模拟
→ 试卷复盘
```

## 11.7 任务生成规则

| 掌握度 | 推荐任务 |
|---:|---|
| < 0.30 | 概念学习、教材例题、低难练习 |
| 0.30—0.49 | 概念补充、基础训练、错因修复 |
| 0.50—0.69 | 标准题、变式题、专题练习 |
| 0.70—0.84 | 高考真题、综合题、限时训练 |
| ≥ 0.85 | 测评验证、低频维护、迁移应用 |

## 11.8 任务优先级

```text
TaskPriority
= KnowledgePriority
× Urgency
× ExpectedScoreGain
× ExpectedLearningGain
× ContentQuality
× TimeFit
÷ EstimatedEffort
```

## 11.9 排期约束

### 硬约束

- 不与学校固定课程和正式考试冲突；
- 前置任务先于目标任务；
- 不超过每日有效容量；
- 不超过单次专注上限；
- 正式考试前完成核心复习；
- 资源有效且通过教学审核；
- 选科和考试政策合法；
- 保留最低休息和缓冲时间。

### 软约束

- 高难度任务安排在高精力时段；
- 避免一天集中多个高负荷科目；
- 同一科目保持连续性但避免疲劳；
- 新学知识与首次练习相邻；
- 错题复习按间隔规律安排；
- 临近考试逐步增加限时和整卷训练；
- 保持学生偏好。

## 11.10 排期求解

两阶段方法：

1. 使用知识拓扑排序、截止日期和优先级生成初始排期；
2. 使用 CP-SAT、整数规划或启发式搜索优化多科时间分配。

优化目标：

```text
Maximize:
  目标覆盖收益
+ 预期分数提升
+ 预期掌握度提升
+ 时间匹配度
+ 学习连续性
- 超负荷惩罚
- 截止风险
- 任务切换成本
- 高难任务集中度
```

## 11.11 动态调整触发机制

### 掌握度触发

- 连续两次练习后仍低于目标掌握度 0.15 以上；
- 关键知识掌握度下降超过 0.10；
- 提前达到阶段目标；
- 新发现强前置漏洞。

### 执行触发

- 连续三天未完成计划；
- 周任务完成率低于 70%；
- 实际时长连续高于预计 30%；
- 频繁跳过同类任务；
- 学生反馈任务过多或过难。

### 考试触发

- 月考、联考或模考完成；
- 单科得分显著偏离预测；
- 非智力失分显著增加；
- 整卷时间不足；
- 距离高考进入新阶段。

### 时间触发

- 周可用时间变化超过 20%；
- 新增学校考试；
- 作业量显著变化；
- 课程表或培训安排变化。

### 目标触发

- 目标分数、院校或专业变化；
- 选科变化；
- 截止日期变化；
- 教师调整优先级。

## 11.12 调整等级

| 等级 | 范围 |
|---|---|
| `task_swap` | 替换单个资源或题组 |
| `daily_shift` | 调整当天剩余任务 |
| `weekly_replan` | 重排本周 |
| `stage_replan` | 重建当前阶段 |
| `full_replan` | 重建全部剩余计划 |

## 11.13 模块输入输出规范

```json
{
  "plan_id": "plan_001",
  "version": 1,
  "status": "draft",
  "exam_profile_id": "NEW_GAOKAO_NATIONAL_I_2027_HUNAN",
  "stages": [],
  "tasks": [],
  "subject_time_budgets": {},
  "buffer_strategy": {},
  "validation": {},
  "explanations": {
    "student": "",
    "teacher": ""
  },
  "next_action": "request_plan_confirmation"
}
```

---

# 12. 首次使用用户信息获取与冷启动设计

## 12.1 模块定位

第一次使用时，系统需要建立“最小可用学习画像”，而不是要求学生一次性填写全部个人信息。

推荐采用：

```text
已有数据自动读取
→ 学生确认
→ 缺失字段最少追问
→ 必要时诊断测评
→ 初始知识画像
→ 初始时间画像
→ 首版计划
→ 使用行为持续修正
```

## 12.2 首次必须获取的信息

以下信息是发布首版正式计划的最低要求：

1. 学生年级和当前学期；
2. 所在省份；
3. 预计高考年份；
4. 适用高考模式和全国卷类型；
5. 当前选科组合或暂未选科状态；
6. 教材版本和学校教学进度；
7. 学习目标；
8. 当前大致水平；
9. 每周可用学习时间；
10. 历史数据授权或诊断测评选择。

### 12.2.1 高一新增字段

- 是否已经选科；
- 当前选科意向；
- 学科兴趣和成绩；
- 学校预计选科时间；
- 不将临时选科意向作为最终高考科目事实。

### 12.2.2 高二新增字段

- 已确认选科组合；
- 当前课程完成进度；
- 高一知识遗留问题；
- 目标专业是否存在选考要求。

### 12.2.3 高三新增字段

- 当前复习轮次；
- 最近三次重要考试成绩；
- 距离下一次模考和高考的时间；
- 各科预计目标分；
- 整卷时间分配问题；
- 当前学校复习安排。

## 12.3 信息采集分类

### A 类：身份和学业阶段

| 字段 | 必填 | 来源 |
|---|---:|---|
| `student_id` | 是 | 系统生成 |
| `grade` | 是 | 学籍或学生确认 |
| `school_term` | 是 | 系统日期和学校校历 |
| `province_code` | 是 | 学籍或学生确认 |
| `school_entry_year` | 是 | 学籍 |
| `expected_gaokao_year` | 是 | 系统推算后确认 |
| `school_type` | 否 | 学籍 |
| `timezone` | 是 | 账户或设备 |

### B 类：考试与选科信息

| 字段 | 必填 | 说明 |
|---|---:|---|
| `exam_profile_id` | 是 | 由政策工具生成 |
| `national_paper_type` | 是 | 默认全国Ⅰ卷配置 |
| `subject_model` | 是 | 如 3+1+2 |
| `selected_subjects` | 高二高三必填 | 高一可为意向 |
| `foreign_language_type` | 是 | 英语或其他语种 |
| `score_rule_version` | 是 | 省级政策版本 |

### C 类：课程和教材信息

- 各科教材版本；
- 当前课本册次；
- 学校教学进度；
- 已完成章节；
- 正在学习章节；
- 下次校内考试范围；
- 教师布置的强制学习任务。

### D 类：学习目标

必须明确：

- 目标考试；
- 目标科目或总分；
- 当前分数；
- 目标分数；
- 截止节点；
- 目标优先级。

### E 类：当前基础

优先级：

```text
正式考试和联考成绩
＞ 教师评价
＞ 平台练习记录
＞ 作业记录
＞ 学生自评
```

可上传或同步：

- 最近考试总分和单科分；
- 试卷分题得分；
- 成绩单；
- 错题；
- 教师评语；
- 平台历史记录。

### F 类：可用时间

必须获取：

- 平日自主学习时间；
- 周末自主学习时间；
- 固定早晚自习；
- 培训和竞赛时间；
- 单次最长专注时间；
- 周末是否可补学；
- 考试周和假期时间变化。

### G 类：学习偏好

首次只建议询问：

1. 更偏好讲解、例题还是边做边学；
2. 一次连续学习多长时间比较合适。

其他偏好通过行为推断。

### H 类：特殊约束

- 教师指定内容；
- 家长授权边界；
- 每日屏幕时间；
- 设备和网络限制；
- 无障碍需求；
- 禁止安排时间；
- 是否需要教师确认计划。

## 12.4 首次问题数量

推荐：

- 核心问答 6—10 个；
- 首次信息采集 3—6 分钟；
- 初始诊断 10—30 分钟；
- 每轮最多询问两个问题；
- 非必要字段允许跳过。

## 12.5 首次使用五阶段流程

### 阶段一：身份、政策和授权

```text
user_identity_resolve
→ student_profile_query
→ data_authorization_collect
→ exam_policy_resolve
→ exam_policy_validate
```

首次欢迎语：

```text
为了给你制定适合新高考全国Ⅰ卷的学习计划，系统需要了解你的年级、
选科、学习目标、当前基础和每周可用时间。

你可以授权系统读取已有成绩和练习记录，这样能够减少需要填写的信息
和诊断题数量。你也可以拒绝授权并通过诊断测评建立初始画像。
```

### 阶段二：最小目标采集

```text
goal_input_collect
→ goal_parse
→ goal_missing_field_detect
→ goal_clarification_generate
→ goal_feasibility_precheck
```

推荐问题顺序：

1. 目前是高一、高二还是高三；
2. 所在省份和预计高考年份；
3. 当前选科组合；
4. 最想提升哪一科或哪次考试；
5. 当前大约多少分；
6. 希望达到多少分；
7. 目标考试在什么时候。

### 阶段三：历史数据与诊断

```text
learning_history_query
→ exam_paper_evidence_extract
→ knowledge_scope_resolve
→ assessment_evidence_sufficiency_check
→ assessment_mode_select
→ assessment_blueprint_generate
→ adaptive_item_select
→ mastery_infer
→ prerequisite_gap_detect
→ knowledge_profile_build
```

### 阶段四：时间和执行条件

```text
availability_collect
→ school_calendar_merge
→ time_conflict_detect
→ learning_efficiency_infer
→ subject_time_budget_allocate
→ effective_capacity_estimate
→ elastic_buffer_allocate
→ time_profile_build
```

### 阶段五：首版画像和计划确认

必须向学生展示：

- 系统识别的考试配置；
- 当前年级、选科和教材；
- 目标考试和目标分；
- 主要知识缺口；
- 每周有效时间；
- 各科时间预算；
- 首阶段计划；
- 风险和弹性安排。

确认选项：

- 信息正确，生成计划；
- 修改考试或选科信息；
- 修改目标；
- 修改当前水平；
- 修改可用时间；
- 暂时保存，稍后继续。

## 12.6 首次使用工具

### `user_identity_resolve`

识别用户、年级和组织关系。

### `student_profile_query`

查询已有学籍、课程、教材、选科和教师信息，避免重复询问。

### `data_authorization_collect`

记录对成绩、练习、课程表和日历的授权范围。

### `onboarding_question_select`

按以下优先级选择下一问题：

```text
考试配置和身份
＞ 目标定义
＞ 当前基础
＞ 时间容量
＞ 学习偏好
```

### `profile_consistency_check`

检测：

- 年级与学籍冲突；
- 选科与考试配置冲突；
- 当前成绩与最近考试差异过大；
- 学生表示未学过但存在大量学习记录；
- 时间与课表冲突；
- 目标考试日期错误。

### `onboarding_completeness_evaluate`

```text
OnboardingCompleteness
= 0.20 × 考试配置完整度
+ 0.20 × 目标信息完整度
+ 0.25 × 知识基础可信度
+ 0.20 × 时间信息完整度
+ 0.10 × 课程进度完整度
+ 0.05 × 学习偏好完整度
```

首版计划生成最低条件：

- 考试配置已确认；
- 年级和选科已确认或标记为意向；
- 目标已确认；
- 有初步知识基础；
- 有每周可用时间；
- 无未解决的严重冲突；
- 完整度建议不低于 0.75。

## 12.7 首次使用推荐对话脚本

### 第一步：学业阶段

```text
你目前是高一、高二还是高三？
```

### 第二步：考试配置

```text
你所在的省份和预计参加高考的年份是什么？
```

系统调用政策工具后展示：

```text
系统识别到你适用新高考全国Ⅰ卷配置。请确认当前选科组合。
```

### 第三步：学习目标

```text
你目前最希望提升哪一科，或准备哪一次重要考试？
```

### 第四步：量化目标

```text
你最近一次成绩大约是多少，希望达到多少？
```

### 第五步：基础数据

```text
为了减少不必要的测试，你可以选择：
1. 读取平台历史成绩和练习；
2. 上传最近一份成绩或试卷；
3. 完成一次诊断测评；
4. 先进行自我评估。
```

### 第六步：学习时间

```text
除学校课程和作业外，你每周大约能安排多少自主学习时间？
```

### 第七步：确认

展示初始画像和首阶段计划摘要，学生确认后发布。

## 12.8 首次使用状态机

```text
ONBOARDING_STARTED
        ↓
IDENTITY_RESOLVED
        ↓
POLICY_RESOLVED
        ↓
AUTHORIZATION_COLLECTED
        ↓
GOAL_COLLECTING
        ↓
GOAL_CONFIRMED
        ↓
HISTORY_CHECKING
        ↓
ASSESSMENT_PENDING
        ↓
KNOWLEDGE_PROFILE_READY
        ↓
AVAILABILITY_COLLECTING
        ↓
TIME_PROFILE_READY
        ↓
SUMMARY_CONFIRMATION
        ↓
ONBOARDING_COMPLETED
        ↓
PLAN_GENERATING
```

退出后保存进度，下次从中断点恢复。

---

# 13. 首次初始化完整工作流

## 13.1 触发条件

- 首次注册；
- 新增高考备考目标；
- 从高一进入高二或从高二进入高三；
- 正式选科发生变化；
- 进入一轮、二轮或冲刺阶段；
- 旧知识画像过期；
- 教师要求重建计划。

## 13.2 完整流程

```text
1. 创建首次规划会话
2. 识别学生身份、年级和省份
3. 查询并校验高考政策
4. 获取数据授权
5. 读取学籍、选科、教材和课程进度
6. 采集并解析学习目标
7. 补充目标缺失字段
8. 校验目标可行性
9. 读取历史考试、作业和练习
10. 解析历史试卷证据
11. 提取目标知识子图
12. 判断证据是否充分
13. 必要时启动自适应诊断
14. 构建知识、题型和考试技能画像
15. 采集和同步可用时间
16. 建立学习效率模型
17. 分配多科时间预算
18. 计算有效容量和缓冲
19. 生成知识路径
20. 识别复习阶段
21. 划分阶段
22. 生成候选任务
23. 匹配教材、题目和试卷资源
24. 估算任务工时
25. 执行多科排期
26. 插入复习、限时训练和测评
27. 校验计划
28. 生成人类可理解解释
29. 请求学生或教师确认
30. 发布计划
31. 注册动态调整监听器
```

## 13.3 工具调用编排

```text
user_identity_resolve
→ student_profile_query
→ data_authorization_collect
→ exam_policy_resolve
→ exam_policy_validate
→ goal_parse
→ goal_clarification_generate（必要时）
→ goal_decompose
→ goal_feasibility_evaluate
→ goal_conflict_detect
→ learning_history_query
→ exam_paper_evidence_extract
→ knowledge_scope_resolve
→ assessment_evidence_sufficiency_check
  ├── 证据充分 → mastery_infer
  └── 证据不足 → assessment_blueprint_generate
                    → adaptive_item_select
                    → assessment_response_score
                    → mastery_infer
→ prerequisite_gap_detect
→ exam_skill_profile_build
→ knowledge_profile_build
→ availability_collect
→ school_calendar_merge
→ learning_efficiency_infer
→ subject_time_budget_allocate
→ effective_capacity_estimate
→ elastic_buffer_allocate
→ learning_path_build
→ stage_partition
→ candidate_task_generate
→ content_resource_match
→ task_effort_estimate
→ plan_schedule_optimize
→ plan_validate
  ├── 通过 → plan_publish
  └── 未通过 → 修正后重新校验
```

---

# 14. 日常迭代更新工作流

## 14.1 每次练习后的即时更新

```text
接收事件
→ 去重和异常检测
→ 计算有效作答时间
→ 提取练习特征
→ 错因分类
→ 计算证据权重
→ 更新知识掌握度
→ 更新考试技能指标
→ 对比任务完成规则
→ 判断是否需要即时微调
```

即时微调范围：

- 调整下一道题难度；
- 添加短知识补充；
- 替换不匹配资源；
- 调整当天剩余任务顺序。

不得因一次普通错误重建整周计划。

## 14.2 每日更新

```text
practice_event_ingest
→ practice_data_clean
→ practice_feature_extract
→ mastery_dynamic_update
→ plan_execution_compare
→ adjustment_trigger_evaluate
  ├── 无触发 → 更新状态
  ├── task_swap → 替换资源
  └── daily_shift → 调整次日任务
```

## 14.3 每周更新

每周执行：

1. 统计各科计划完成率；
2. 统计有效学习时间；
3. 汇总知识掌握度变化；
4. 检查前置漏洞；
5. 分析题型、速度和非智力失分；
6. 更新任务效率；
7. 检查下周课表和考试；
8. 更新多科时间预算；
9. 判断阶段目标；
10. 重排下周任务；
11. 生成学生版周报；
12. 生成教师版周报。

建议规则：

```text
完成率 ≥ 85% 且知识目标达成：保持或适度加速
完成率 70%—84%：局部调整
完成率 < 70%：重建下一周
连续两周 < 70%：重新评估目标和时间容量
```

## 14.4 重要考试后更新

月考、联考和模考后：

```text
试卷结构化
→ 得分与失分归因
→ 知识画像更新
→ 题型画像更新
→ 时间分配分析
→ 目标达成概率更新
→ 科目时间预算更新
→ 阶段或全量重规划
```

## 14.5 阶段结束更新

```text
阶段测评
→ 知识画像更新
→ 阶段完成判断
→ 下一阶段路径检查
→ 目标可行性重评估
→ 下一阶段计划生成
```

阶段未达标时，可：

- 延长当前阶段；
- 插入漏洞修复阶段；
- 降低下一阶段难度；
- 压缩低优先级内容；
- 调整目标。

---

# 15. 多 Agent 协作规范

## 15.1 与教学讲解 Agent

规划 Agent 提交：

- 学科；
- 知识点；
- 当前掌握度；
- 错误类型；
- 目标难度；
- 讲解时长上限；
- 学生偏好。

讲解 Agent 返回内容资源 ID 和完成要求。

## 15.2 与题目生成 Agent

规划 Agent 不直接生成题目文本，而是提交题目规格：

```json
{
  "subject": "physics",
  "knowledge_ids": [
    "mechanics_momentum_conservation"
  ],
  "question_type": "calculation",
  "difficulty": 0.65,
  "exam_profile_id": "NEW_GAOKAO_NATIONAL_I_2027_HUNAN",
  "count": 5,
  "target_error_tags": [
    "system_boundary_error"
  ]
}
```

## 15.3 与批改 Agent

主观题批改返回：

- 得分；
- 分步得分；
- 缺失步骤；
- 错误类型；
- 表达规范；
- 是否触发知识画像更新。

## 15.4 与教师辅助 Agent

教师端可：

- 设置强制目标；
- 限定教学范围；
- 查看班级和个人风险；
- 调整强约束；
- 审批重大重规划；
- 查看计划依据和版本差异。

---

# 16. Agent 调度决策规范

## 16.1 决策循环

```text
Observe：读取当前状态、政策、目标、画像和事件
Reason：判断缺少的信息和下一工具
Act：调用单一职责工具
Validate：检查输出状态、证据、版本和置信度
Update：更新状态与上下文
Respond：向学生或教师反馈必要信息
```

## 16.2 典型工具选择

| 条件 | 工具 |
|---|---|
| 省份和高考年份已知 | `exam_policy_resolve` |
| 目标自然语言未结构化 | `goal_parse` |
| 目标缺少关键字段 | `goal_clarification_generate` |
| 历史试卷已上传 | `exam_paper_evidence_extract` |
| 画像证据不足 | `assessment_blueprint_generate` |
| 学生完成练习 | `practice_event_ingest` |
| 新模考成绩到达 | `exam_loss_attribution` |
| 可用时间减少 | `plan_schedule_optimize` |
| 阶段测评未通过 | `plan_revise` |
| 计划即将发布 | `plan_validate` |

## 16.3 禁止行为

Agent 不得：

- 未确认高考配置就发布高考计划；
- 虚构省级赋分和考试规则；
- 将选科意向当作最终选科；
- 未完成目标校验就生成正式计划；
- 知识图谱不可用时虚构前置关系；
- 时间容量未知时排满任务；
- 工具失败时伪造结果；
- 根据一次错误判定完全未掌握；
- 用低置信度结论进行大范围重规划；
- 直接覆盖已发布计划。

---

# 17. 计划解释要求

## 17.1 学生版

必须回答：

1. 当前最重要的目标是什么；
2. 为什么先学这些内容；
3. 每周各科需要投入多少时间；
4. 每项任务如何完成；
5. 本周主要风险是什么；
6. 什么情况下计划会调整。

## 17.2 教师版

必须包含：

- 考试配置和政策版本；
- 目标结构；
- 知识、题型和考试技能证据；
- 前置漏洞；
- 各科时间预算；
- 路径选择依据；
- 计划覆盖率；
- 风险和调整记录；
- 算法和数据版本。

---

# 18. 异常处理与降级

| 异常 | 降级策略 |
|---|---|
| 政策服务不可用 | 使用已缓存有效版本，禁止创建涉及未知新规则的计划 |
| 知识图谱不可用 | 使用缓存图谱，不新增关系 |
| 知识追踪模型不可用 | 使用最近画像和规则更新，降低置信度 |
| 日历服务不可用 | 使用学生手动时间模板 |
| 内容服务不可用 | 保留任务槽位，稍后匹配内容 |
| 排期求解超时 | 使用规则排期并标记待优化 |
| LLM 不可用 | 使用结构化表单 |
| 测评中断 | 保存进度并生成部分画像 |
| 数据版本冲突 | 重新读取最新数据后重试 |

自动修正计划最多三次，仍不通过时进入 `MANUAL_REVIEW_REQUIRED`。

---

# 19. 权限、隐私和未成年人保护

## 19.1 权限

| 角色 | 权限 |
|---|---|
| 学生 | 查看计划、确认目标、调整个人可用时间 |
| 教师 | 查看授权学生画像、设置教学约束和审批重大调整 |
| 家长或监护人 | 在授权范围内查看计划和进度 |
| 管理员 | 配置政策、课程、图谱和规则 |
| Agent | 在授权范围内读写计划和画像版本 |

## 19.2 数据最小化

不采集与学习计划无关的信息。学校、地区、家庭信息仅在影响课程、政策、时间或授权时使用。

## 19.3 审计

保存：

- 工具调用；
- 输入和输出版本；
- 决策理由；
- 计划调整前后差异；
- 触发条件；
- 操作者；
- 学生、教师或监护人确认记录。

---

# 20. 核心 API 建议

## 20.1 创建首次使用会话

```http
POST /api/v1/onboarding/sessions
```

## 20.2 获取下一问题

```http
GET /api/v1/onboarding/sessions/{onboarding_id}/next-questions
```

## 20.3 提交首次使用答案

```http
POST /api/v1/onboarding/sessions/{onboarding_id}/answers
```

## 20.4 确认考试配置

```http
POST /api/v1/onboarding/sessions/{onboarding_id}/exam-profile/confirm
```

## 20.5 初始化规划

```http
POST /api/v1/planner/initialize
```

## 20.6 获取当前计划

```http
GET /api/v1/students/{student_id}/plans/active
```

## 20.7 上报学习事件

```http
POST /api/v1/learning-events
```

## 20.8 上传考试结果

```http
POST /api/v1/students/{student_id}/exam-results
```

## 20.9 触发日常更新

```http
POST /api/v1/planner/daily-update
```

## 20.10 手动重规划

```http
POST /api/v1/plans/{plan_id}/replan
```

## 20.11 确认计划

```http
POST /api/v1/plans/{plan_id}/confirm
```

---

# 21. 核心事件

| 事件 | 触发时机 |
|---|---|
| `ExamPolicyResolved` | 高考政策识别完成 |
| `SubjectSelectionChanged` | 选科变化 |
| `GoalCreated` | 新目标创建 |
| `GoalChanged` | 目标修改 |
| `AssessmentCompleted` | 测评完成 |
| `KnowledgeProfileUpdated` | 知识画像更新 |
| `PracticeSubmitted` | 练习提交 |
| `ExamResultImported` | 考试结果导入 |
| `TaskCompleted` | 任务完成 |
| `TaskSkipped` | 任务跳过 |
| `AvailabilityChanged` | 可用时间变化 |
| `PlanGenerated` | 计划生成 |
| `PlanPublished` | 计划发布 |
| `PlanAdjustmentTriggered` | 触发调整 |
| `PlanRevised` | 调整完成 |
| `StageCompleted` | 阶段完成 |
| `GoalAtRisk` | 目标存在风险 |

---

# 22. 非功能需求

## 22.1 性能

| 操作 | 目标 |
|---|---:|
| 政策配置查询 | P95 < 1 秒 |
| 目标解析 | P95 < 3 秒 |
| 单题证据更新 | P95 < 1 秒 |
| 知识画像更新 | P95 < 2 秒 |
| 单周局部调整 | P95 < 5 秒 |
| 完整阶段计划生成 | P95 < 15 秒 |
| 计划读取 | P95 < 500 毫秒 |

## 22.2 可用性

- 核心服务月可用性不低于 99.9%；
- 写操作支持幂等；
- 关键工具支持重试；
- 画像和计划支持版本回滚；
- 关键服务不可用时提供可解释降级结果。

## 22.3 可解释性

每项任务必须能够回答：

1. 为什么安排；
2. 对应哪个目标；
3. 修复哪个缺口；
4. 为什么安排在该时间；
5. 完成标准是什么；
6. 什么情况下调整。

## 22.4 可配置性

以下参数必须配置化：

- 考试政策；
- 省级赋分规则；
- 教材版本；
- 掌握度阈值；
- 阶段长度；
- 测评停止条件；
- 缓冲比例；
- 动态调整阈值；
- 各学科任务权重；
- 内容排序权重；
- 效率系数；
- 教师强约束优先级。

---

# 23. 测试与验收标准

## 23.1 首次使用验收

- 能识别高一、高二、高三；
- 能按省份和高考年份解析考试配置；
- 能区分正式选科和选科意向；
- 已有信息不重复询问；
- 模糊目标触发追问；
- 无历史数据时启动诊断；
- 拒绝数据授权后仍可继续；
- 支持中途退出和恢复；
- 生成计划前展示信息摘要；
- 信息不足时不得发布正式计划。

## 23.2 目标模块验收

- 能识别考试、科目、当前分、目标分和期限；
- 能拆分长期、中期和短期目标；
- 能检测目标与时间冲突；
- 能检测目标与选科冲突；
- 不得虚构未知字段。

## 23.3 测评模块验收

- 能从历史试卷提取知识和题型证据；
- 能生成分层测评；
- 能输出知识点级掌握度；
- 能定位前置漏洞；
- 能输出题型和时间画像；
- 低置信度结论必须标记。

## 23.4 练习模块验收

- 重复事件不重复更新；
- 异常事件降低权重；
- 能区分知识错误和非智力失分；
- 能根据提示、难度和过程调整证据；
- 所有掌握度更新可追溯。

## 23.5 时间模块验收

- 能合并课表、考试和个人时间；
- 能识别冲突；
- 能进行多科时间预算；
- 计划不超过有效容量；
- 必须保留弹性时间。

## 23.6 计划引擎验收

- 强前置顺序正确；
- 目标知识覆盖完整；
- 各科预算合理；
- 任务有时长和完成标准；
- 包含复习、限时训练和测评；
- 排期满足硬约束；
- 动态调整创建新版本；
- 政策过期时不得发布。

## 23.7 端到端场景

### 场景一：高一新用户，尚未选科

期望：

- 记录选科意向而非正式选科；
- 以校内同步和基础能力为主；
- 不生成依赖最终选科的长期高考任务；
- 在选科确认后触发重规划。

### 场景二：高二物化生学生

期望：

- 识别全国Ⅰ卷考试配置；
- 读取物理、化学、生物选科；
- 生成同步学习和高一漏洞修复计划；
- 多科时间预算不超过容量。

### 场景三：高三一轮数学目标提升

输入：最近成绩 92，目标一模 120。

期望：

- 解析一模节点；
- 诊断知识和题型；
- 优先基础和中档题稳定；
- 插入专题训练和阶段测评；
- 输出目标风险。

### 场景四：模考后成绩下降

期望：

- 解析整卷；
- 判断知识退步还是时间、状态问题；
- 更新分数预测；
- 调整本周计划；
- 单次异常不足以触发无依据的全量重规划。

### 场景五：下一周学校考试增多

期望：

- 可用时间减少；
- 优先保留考试相关任务；
- 延后低优先级拓展；
- 保留最低复习和休息时间。

---

# 24. 推荐开发阶段

## 24.1 MVP

1. 用户身份、年级、省份和高考配置；
2. 选科信息；
3. 目标结构化；
4. 历史成绩导入；
5. 基础诊断；
6. 规则式掌握度；
7. 课表和可用时间采集；
8. 多科时间预算；
9. 规则式学习路径；
10. 周计划生成；
11. 练习事件接入；
12. 基础动态调整；
13. 计划版本化。

## 24.2 增强版

- CAT 自适应测评；
- BKT、DKT 或 AKT；
- 试卷自动结构化；
- 个体化效率模型；
- CP-SAT 多科排期；
- 间隔复习；
- 错因自动分类；
- 教师工作台；
- 目标达成概率预测。

## 24.3 智能优化版

- 跨科目标联合规划；
- 高考分数增益预测；
- 内容推荐因果评估；
- 强化学习排期；
- 选科和生涯 Agent 协同；
- 班级教学与个人计划协同；
- 教学策略自动实验。

---

# 25. 最终工具清单

## 25.1 身份、政策与首次使用

```text
user_identity_resolve
student_profile_query
data_authorization_collect
exam_policy_resolve
exam_policy_validate
onboarding_question_select
profile_consistency_check
onboarding_completeness_evaluate
onboarding_summary_generate
```

## 25.2 目标工具

```text
goal_source_resolve
goal_parse
goal_clarification_generate
goal_decompose
goal_metric_map
goal_feasibility_evaluate
goal_conflict_detect
goal_save_version
```

## 25.3 测评与画像工具

```text
learning_history_query
exam_paper_evidence_extract
knowledge_scope_resolve
assessment_evidence_sufficiency_check
assessment_mode_select
assessment_blueprint_generate
adaptive_item_select
assessment_response_score
mastery_infer
practice_error_classify
prerequisite_gap_detect
exam_skill_profile_build
knowledge_profile_build
knowledge_profile_validate
```

## 25.4 练习量化工具

```text
practice_event_ingest
practice_event_normalize
practice_event_deduplicate
practice_data_clean
practice_feature_extract
practice_error_classify
practice_evidence_weight
mastery_dynamic_update
practice_trend_analyze
exam_loss_attribution
plan_execution_compare
```

## 25.5 时间适配工具

```text
availability_collect
school_calendar_merge
time_conflict_detect
learning_preference_infer
learning_efficiency_infer
subject_time_budget_allocate
effective_capacity_estimate
task_effort_estimate
elastic_buffer_allocate
time_profile_build
availability_change_detect
```

## 25.6 计划引擎工具

```text
learning_path_build
knowledge_priority_calculate
stage_partition
candidate_task_generate
content_resource_match
task_effort_estimate
spaced_review_schedule
timed_training_insert
assessment_task_insert
plan_schedule_optimize
plan_validate
plan_explanation_generate
adjustment_trigger_evaluate
plan_revise
plan_publish
plan_version_query
```

---

# 26. 结论

面向新高考全国Ⅰ卷高中生的个性化学习规划 Agent，应被实现为一个由考试政策配置、状态机、知识图谱、知识追踪、时间优化和多 Agent 工具协作共同驱动的长期学习规划系统。

其核心不是“为学生生成一张固定时间表”，而是持续回答以下问题：

- 学生当前真正需要解决什么；
- 哪些知识是高考目标的关键前置；
- 哪类失分来自知识，哪类失分来自考试执行；
- 在学校课程和有限自主时间下，哪些任务收益最高；
- 计划何时应保持、局部调整或重建；
- 学生、教师和家长为什么可以信任这次规划。

最终系统应实现：

```text
政策正确
+ 目标明确
+ 学情可信
+ 路径合理
+ 时间可执行
+ 结果可解释
+ 计划可迭代
```

