# 第六 Agent V2：Python 后端职业技能导师

## 产品范围

V2 按 `information/career_programming_education_agent_development_spec.md` 收敛为首期 MVP：

```text
职业目标 → 6 题诊断 → Skill Gap → 当前代码任务
→ 自动测试 → 分级反馈 → Mastery 更新 → 下一任务
```

学生端不再同时展示项目、面试、周报和多条路线。主界面始终只突出一个下一步；技能证据与三阶段路线默认折叠。

## 核心实现

- `Knowledge/Agent_6/python_backend_skill_graph.json`：Python 后端岗位、10 个技能节点、诊断题、代码任务与路线。
- `CareerProgrammingLearningAgent`：LangGraph V2 意图路由。
- `CareerProgrammingLearningService`：职业画像、Gap、任务、反馈和证据闭环。
- `ProgrammingCodeRunner`：统一代码执行边界。
- `CareerProgrammingWorkspace.vue`：学生端单主流程页面。

## API

- `GET /api/v1/programming-learning/dashboard`
- `PUT /api/v1/programming-learning/career-profile`
- `POST /api/v1/programming-learning/career-diagnostics`
- `POST /api/v1/programming-learning/career-diagnostics/{id}/submission`
- `POST /api/v1/programming-learning/coding/tasks`
- `POST /api/v1/programming-learning/coding/tasks/{id}/submissions`
- `POST /api/v1/programming-learning/coding/tasks/{id}/hint`

## 数据

V2 继续使用第六 Agent 已有的四张 MySQL 私有表：

- `programming_learner_profiles`：长期职业画像；
- `programming_learning_records`：诊断、任务和提交；
- `programming_learning_events`：quiz / coding 技能证据；
- `programming_skill_states`：按学生和技能聚合的掌握度。

`record_type` 新增逻辑类型：`career_diagnostic`、`career_coding_task`、`career_submission`。这样不新增重复表，也保留 V1 数据。

## 代码执行边界

当前主机用户无权连接 `/var/run/docker.sock`。验收环境使用 3 秒、128 MB、1 MB 文件、8 进程限制的隔离 Python 子进程，并阻止 import、高风险内置函数和双下划线内部属性；接口与页面明确返回 `restricted_subprocess_demo`。

这不是生产级安全沙箱。生产部署必须将同一接口替换为独立 Docker Runner，默认禁网、只读基础文件系统，并在每次执行后销毁容器。
