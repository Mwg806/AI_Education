# 多 Agent 教育系统渐进式架构重构

## 实施范围

本次重构基于 `4ea9ba55`，开发分支为
`refactor/progressive-multi-agent-orchestration`。遵循兼容优先原则：保留六个既有
LangGraph Agent、原 REST API、领域仓库、MySQL 业务表、前端页面和人工
`CollaborationRequest` DAG；在它们外侧新增共享协议与编排层。

## 重构前审计结论

- 学生端 API 直接调用各 Agent，只有手工协作接口进入 `MultiAgentCoordinator`。
- `GlobalStateStore` 和 `AgentMessageBus` 为进程内状态，重启后不保留。
- 规划、英语、职业编程画像互相独立，诊断结果不会自动进入规划。
- 作业和诊断已经发布部分领域消息，但没有统一消费者与持久事件表。
- Planner、Homework、Diagnosis 分别创建模型客户端，下游服务只部分复用模型。
- 题库检索继续使用当前 SQLite FTS、PDF 检索和 JSON 目录；本阶段不强行引入向量库或 Redis。

## 当前兼容架构

```text
原学生端 REST API ───────────────┐
                                 ├→ AgentExecutionService
自然语言 /orchestration/chat     │     ├→ 注入 UnifiedStudentProfile
  → IntentRouter                 │     ├→ 注入近期 LearningEvent
  → ProgressiveAgentOrchestrator ┘     ├→ 调用原 AgentRegistry 中的 Agent
                                       ├→ 适配旧 AgentMessage 为标准事件
                                       └→ 写执行追踪
                                                │
             ┌──────────────────────────────────┴──────────────────────┐
             ↓                                                         ↓
  StudentProfileService / LearningEventService              原领域仓库与业务表
             ↓
  unified_student_profiles / unified_learning_events
  agent_orchestration_runs / agent_execution_traces
```

`ModelRouter` 在应用容器中只创建一次模型客户端。Planner、Homework、Diagnosis
通过可选构造参数复用该实例；旧构造调用仍然有效。

## 首条跨 Agent 工作流

用户输入“英语阅读一直不好，分析原因然后安排怎么练”时：

1. `IntentRouter` 返回顺序路由：`learning_diagnosis` →
   `personalized_learning_planner`。
2. 编排器读取统一画像和近期事件，把逐题事件转换为诊断 Agent 原有的
   `LearningEvidenceRecord`，不伪造作答证据。
3. 诊断 Agent 执行证据门控并输出结构化 `learning_state`。
4. `AgentHandoff` 把诊断结果交给规划 Agent 的兼容意图
   `apply_diagnosis_to_plan`。
5. 规划 Agent 生成优先薄弱点和 7 天训练建议，明确
   `mutation_applied=false`、`requires_confirmation=true`；未经学生确认不覆盖正式计划。
6. 新事件更新统一画像，运行、延迟、模型、错误、handoff 和事件数量写入审计表。

智能规划的最终综合层读取的是均衡的跨模块证据摘要，而不是事件总数。编排器最多回看
最近 300 条统一事件，并在外语学习、职业教育、学情诊断与导入学习记录、作业辅导、
个性化学习计划等来源之间轮流选取证据；每个模块最多 8 条、合计最多 40 条。进入模型的
字段只包含事件类型、学科、知识点、得分、置信度、时间和白名单元数据。原始作文、代码、
OCR 全文及对话命令不进入该摘要。职业教育入门画像会发布职业目标、编程基础、每周时间与
目标周期事件，因此尚未提交项目评分的学生也能让规划 Agent 使用其职业学习背景。

## 标准事件与画像

统一事件包括正确/错误作答、知识掌握/薄弱、阅读/语法/写作/口语错误、项目与技能评分、
计划变化、复习完成和诊断更新。事件 ID 对旧响应中的请求与题目来源做稳定哈希，重复提交不会
重复改变画像。同一知识点累计 3 次错误会进入 `weak_points` 并形成诊断信号。

当前已接入：

- 原 Planner、Homework、Diagnosis、English、Programming Agent 调用；
- 新版英语模拟卷提交；
- 诊断到规划 handoff。

教师备课仍沿用原教师领域状态，不写学生画像。

## 新增 API

- `POST /api/v1/orchestration/chat`：学生自然语言编排入口；
- `GET /api/v1/orchestration/profile`：统一学生画像；
- `GET /api/v1/orchestration/events`：近期标准学习事件；
- `GET /api/v1/orchestration/runs/{run_id}`：一次编排的持久审计记录；
- `POST /api/v1/orchestration/execute`：原手工 DAG 接口保持不变。

## 数据库与回滚

迁移脚本为 `migrations/20260811_progressive_multi_agent.sql`，只新增四张表，不修改旧表。
代码回滚可切换回基线分支或提交；新增表不会影响旧代码运行。若未来确认不再需要新数据，
应另行审批数据归档与删表操作，本次不执行破坏性回滚。

## 验证

- 全量既有测试通过；
- 新增事件幂等、三次错误触发薄弱点、表结构和诊断→规划场景测试；
- MySQL 健康检查通过，四张新增表已创建；
- FastAPI 路由断言确认旧教师仪表盘和新编排入口绑定正确。
