# AI Education

面向新高考全国Ⅰ卷高中生的个性化学习规划智能体。项目以 LangChain 提供结构化模型与工具接口，以 LangGraph 编排首次规划和多智能体协作流程；事实查询、画像计算、时间预算、排期校验和计划版本化由确定性服务完成。

需求基准是 [`personalized_learning_planner_agent_national1.md`](personalized_learning_planner_agent_national1.md)。当前版本实现规格书 24.1 的完整 MVP，并为 CAT、知识追踪模型、CP-SAT、内容服务和其他专业 Agent 保留稳定接口；这些增强能力不会由规划 Agent 伪造。

## 已实现能力

- 最小必要信息首次使用流程，每轮最多两个问题，支持保存与恢复；
- 配置化考试政策解析、选科合法性和政策有效期校验；
- 自然语言目标结构化、缺失项追问、拆解、冲突和可行性评估；
- 知识点级证据融合、低置信度标记和前置漏洞检测；
- 练习事件去重、异常清洗、错因分类、证据加权和保守掌握度更新；
- 有效容量、学科时间预算、专注上限和不可排满的弹性缓冲；
- 学习路径、任务阈值、间隔复习、阶段测评、周内排期和发布前校验；
- 计划确认、幂等写入、增量调整和不可覆盖的版本历史；
- 学生版与教师版解释；
- 标准 Agent 协议、消息总线、依赖任务调度、结果聚合和全局状态同步；
- FastAPI 核心接口和可离线运行的确定性降级路径。
- 响应式 React 学习工作台，覆盖画像采集、计划生成/确认、知识画像和练习反馈闭环。

## 环境与安装

所有命令必须从仓库根目录执行，并先激活指定环境：

```bash
cd /home/mwg/dsj/data/AI_Education
conda activate Mamba
python -m pip install -e '.[dev]'
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

接口文档：`http://127.0.0.1:8000/docs`，健康检查：`GET /health`。

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

访问 `http://127.0.0.1:3000`。Vite 开发服务器将 `/agent-api` 代理到
`http://127.0.0.1:8000`，浏览器无需处理跨域。生产静态构建默认启用显式演示模式；
页面会显示“在线演示模式”，不会把示例计划伪装成真实 Agent 结果。连接公开 API 时，
在构建阶段设置 `VITE_AGENT_API_BASE_URL` 并将 `VITE_AGENT_DEMO_MODE=false`。

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
├── agents/          # 统一 Agent 接口与首个规划 Agent
├── api/             # FastAPI 核心接口
├── domain/          # 领域模型、状态和消息协议
├── llm/             # 可选模型工厂与结构化输出链
├── orchestration/   # 注册、消息总线、聚合、调度和全局状态
├── prompts/         # 版本化系统提示词
├── resources/       # 版本化考试政策配置
├── services/        # 目标、画像、练习、时间和计划确定性服务
└── tools/           # LangChain StructuredTool 适配器

components/          # 学习规划工作台交互组件
lib/                 # 前端协议、API 客户端与显式演示适配器
styles/              # 全局设计令牌与基础样式
```

架构细节见 [`docs/architecture.md`](docs/architecture.md)，需求覆盖见 [`docs/requirements_traceability.md`](docs/requirements_traceability.md)。

## Git 分支

- `feature/base-framework`：协议、统一接口和工程基础；
- `feature/personalized-learning-planner`：首个规划智能体与 API；
- `feature/multi-agent-orchestration`：多智能体调度、文档和最终验证。
- `feature/planner-frontend`：首个 Agent 的可视化工作台与 API 调用闭环。
