# AI Education

面向新高考全国Ⅰ卷高中生的双智能体学习系统。项目以 LangChain 提供结构化模型与工具接口，以 LangGraph 分别编排个性化学习规划和作业辅导流程；统一调度层负责消息、状态和学习证据协作，两个 Agent 保持独立会话与职责边界。

需求基准是 [`personalized_learning_planner_agent_national1.md`](personalized_learning_planner_agent_national1.md)。当前版本实现规格书 24.1 的完整 MVP，并为 CAT、知识追踪模型、CP-SAT、内容服务和其他专业 Agent 保留稳定接口；这些增强能力不会由规划 Agent 伪造。

## 已实现能力

- 最小必要信息首次使用流程，每轮最多两个问题，支持保存与恢复；
- 配置化考试政策解析、选科合法性和政策有效期校验；
- 知识库驱动的画像目录：覆盖当前登记的全国新课标Ⅰ卷 11 省，区分 3+3 与 3+1+2；
- 本地教材 PDF 驱动的 10 科教材选择：覆盖语文、数学、英语、物理、化学、生物学、
  思想政治、历史、地理、技术的版本、册次和章节，逐项保留 PDF 目录页证据；
- 自然语言目标结构化、缺失项追问、拆解、冲突和可行性评估；
- 知识点级证据融合、低置信度标记和前置漏洞检测；
- 练习事件去重、异常清洗、错因分类、证据加权和保守掌握度更新；
- 有效容量、学科时间预算、专注上限和不可排满的弹性缓冲；
- 学习路径、任务阈值、间隔复习、阶段测评、周内排期和发布前校验；
- 计划确认、幂等写入、增量调整和不可覆盖的版本历史；
- 学生版与教师版解释；
- 标准 Agent 协议、消息总线、依赖任务调度、结果聚合和全局状态同步；
- FastAPI 核心接口和可离线运行的确定性降级路径。
- 5·3 新高考题库的 7,577 条资源元数据索引，按学科、A/B 版、地区、专题和内容安全角色检索；原始 39GB 资料不进入 Git 或 Prompt；
- 作业辅导 Agent：支持文字/图片题目、低置信度 OCR 确认、分步最小提示、步骤检查、知识回顾、完整作答校验、同类训练和答案防泄漏；
- 规划 Agent 与辅导 Agent 通过标准事件协议传递知识证据，辅导结果不能直接覆盖规划状态；
- Vue 3 + TypeScript 双智能体工作台，提供学习档案登录、规划/确认、知识画像、练习反馈和独立作业辅导入口。

## 环境与安装

所有命令必须从仓库根目录执行，并先激活指定环境：

```bash
cd /home/mwg/dsj/data/AI_Education
conda activate Mamba
python -m pip install -e '.[dev,knowledge]'
```

实际密钥只通过进程环境提供，不写入仓库。复制 `.env.example` 时也不要提交 `.env`。

OpenAI-compatible 模型示例：

```bash
export AI_EDUCATION_LLM_ENABLED=true
export AI_EDUCATION_LLM_PROVIDER=openai
export AI_EDUCATION_LLM_MODEL='<model-name>'
export OPENAI_API_KEY='<secret>'
export OPENAI_BASE_URL='<compatible-v1-endpoint>'
```

未启用 LLM 或模型调用失败时，目标采集降级为结构化表单与确定性解析；系统不会伪造结果。代码也提供 Anthropic-compatible 可选适配器，但当前共享 `Mamba` 环境中的 vLLM 固定了较早的 `anthropic` 版本，因此本环境应使用已经验证的 OpenAI-compatible 路径；不要在未协调 vLLM 依赖前安装 `.[anthropic]`。

## 运行

启动 API：

```bash
conda activate Mamba
ai-education serve --host 127.0.0.1 --port 8000
```

接口文档：`http://127.0.0.1:8000/docs`，健康检查：`GET /health`，画像目录：
`GET /api/v1/catalog/onboarding`。画像目录覆盖语文、数学、英语、思想政治、历史、地理、
物理、化学、生物学和技术；技术由信息技术与通用技术课程标准共同支撑。

作业辅导主要接口：`POST /api/v1/homework/sessions`、
`POST /api/v1/homework/sessions/{session_id}/turns`、
`POST /api/v1/homework/questions/{question_id}/submission`；题库概览为
`GET /api/v1/homework/question-bank/summary`。图片只在内存中处理，最多 10MB。

打印全部规划工具能力：

```bash
conda activate Mamba
ai-education tools
```

请求示例见 [`docs/api_examples.md`](docs/api_examples.md)。

### 启动前端

另开一个已经激活 `Mamba` 的终端：

```bash
conda activate Mamba
npm install
npm run dev
```

访问 `http://127.0.0.1:3000`；同一局域网设备可访问服务器的局域网 IP，例如
`http://192.168.58.33:3000`。Vite 开发服务器将 `/agent-api` 代理到
`http://127.0.0.1:8000`，浏览器无需处理跨域。生产静态构建默认启用显式演示模式；
页面会显示“在线演示模式”，不会把示例计划伪装成真实 Agent 结果。连接公开 API 时，
在构建阶段设置 `VITE_AGENT_API_BASE_URL` 并将 `VITE_AGENT_DEMO_MODE=false`。

## MySQL 学习档案与学生账号

生产环境可通过以下服务端环境变量启用 MySQL 5.7+ 持久化：

```dotenv
AI_EDUCATION_MYSQL_ENABLED=true
AI_EDUCATION_MYSQL_HOST=127.0.0.1
AI_EDUCATION_MYSQL_PORT=13306
AI_EDUCATION_MYSQL_USER=root
AI_EDUCATION_MYSQL_PASSWORD=
AI_EDUCATION_MYSQL_DATABASE=ai_education
AI_EDUCATION_AUTH_SESSION_HOURS=168
```

服务启动时会以 `CREATE DATABASE/TABLE IF NOT EXISTS` 方式执行幂等迁移，不会删除已有数据。
数据库包含学生账号与会话、规划状态、学习计划、作业辅导会话与轮次、学情证据与报告、
高考诊断会话及逐题记录等表。学生密码采用带随机盐的 scrypt 哈希，浏览器只保存不透明会话令牌，
MySQL 密码只能放在服务端 `.env`，禁止使用 `VITE_` 前缀。
构建脚本同时生成 Sites 所需的 Workers 入口与部署元数据。

## 验证

```bash
conda activate Mamba
ruff format --check src tests
ruff check src tests
pytest
python -m compileall -q src tests
npm run typecheck
npm run build
npm audit --audit-level=high
```

## 代码结构

```text
src/ai_education/
├── agents/          # 学习规划 Agent 与作业辅导 Agent
├── api/             # FastAPI 核心接口
├── domain/          # 领域模型、状态和消息协议
├── llm/             # 可选模型工厂与结构化输出链
├── orchestration/   # 注册、消息总线、聚合、调度和全局状态
├── prompts/         # 版本化系统提示词
├── resources/       # 版本化考试政策配置
├── services/        # 目标、画像、练习、时间和计划确定性服务
└── tools/           # LangChain StructuredTool 适配器

components/          # Vue 登录、规划与作业辅导工作台组件
lib/                 # 双 Agent 前端协议、API 客户端与演示适配器
styles/              # 蓝白主题、响应式布局与基础样式
```

架构细节见 [`docs/architecture.md`](docs/architecture.md)，需求覆盖见 [`docs/requirements_traceability.md`](docs/requirements_traceability.md)。

## Git 分支

- `feature/base-framework`：协议、统一接口和工程基础；
- `feature/personalized-learning-planner`：首个规划智能体与 API；
- `feature/multi-agent-orchestration`：多智能体调度、文档和最终验证。
- `feature/planner-frontend`：首个 Agent 的可视化工作台与 API 调用闭环。
- `feature/vue-learning-workspace`：Vue 3 登录页、蓝白主题与学习工作台迁移。
- `feature/homework-tutoring-agent`：第二个作业辅导 Agent、5·3 题库索引与双智能体前端。
