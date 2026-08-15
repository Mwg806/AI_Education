# 问鹿 AI Education

面向新高考全国Ⅰ卷高中教学场景的多智能体学习与教学平台。问鹿以 LangChain 提供结构化模型与工具接口，以 LangGraph 分别编排个性化学习规划、作业辅导、学情诊断、教师备课、英语阅读与语言学习，以及学生编程成长流程；统一调度层负责消息、状态和学习证据协作，各 Agent 保持独立会话、权限和职责边界。

> **源码真源与发布原则**：GitHub `main` 是唯一长期源码真源。所有修改必须先进入干净的 `main` 并通过发布门禁，再按明确 commit SHA 部署；生产服务器只运行发布产物，不作为开发、提交或推送源。完整复现、部署与回滚顺序见 [`docs/deployment.md`](docs/deployment.md)。

系统包含三个相互独立的前端入口：学生端运行在 `3000` 端口，教师端运行在 `3005` 端口，超级管理员控制台运行在 `3010` 端口；三者统一通过 FastAPI `8000` 端口访问后端。学生和教师使用“业务账号 + 已绑定手机号 + 短信验证码”无密码登录；单一超级管理员负责师生账号检索、学生手机号补绑、离校账号永久注销和操作审计。

规划需求基准是 [`personalized_learning_planner_agent_national1.md`](personalized_learning_planner_agent_national1.md)，教师备课 Agent 以 [`教师备课Agent工程设计说明书_优化版.md`](information/教师备课Agent工程设计说明书_优化版.md) 为工程基准，英语阅读与语言学习 Agent 以 [`阅读与语言学习Agent开发文档.md`](information/阅读与语言学习Agent开发文档.md) 为当前工程基准。当前实现继续为 CAT、知识追踪模型、CP-SAT、内容服务和其他专业 Agent 保留稳定接口；不可用能力不会被 Agent 伪造。

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
- 学生可在一次计划中选择 1–6 科统一规划：五步向导将地区与高考选科、规划范围、学习目标、逐科诊断和学习时间分开呈现；每科独立保存教材与 1–5 个章节、成绩目标和优先级，已选科目可直接切换编辑而不清空原范围；规划 Agent 逐科建立学情画像，再在同一周容量内分配预算和交错排期，任何科目缺少诊断或不足每周 60 分钟的最低可执行预算时都会明确阻断，不会漏科或借用其他科目的学情；
- 学习路径、任务阈值、间隔复习、阶段测评、周内排期和发布前校验；
- 计划确认、幂等写入、增量调整和不可覆盖的版本历史；
- 学生版与教师版解释；
- 学生端“智能规划”作为跨模块学习决策中心，持续汇总对话、诊断、训练和正式计划记录，形成学习总结、当前优先级与可确认的规划建议；与“作业辅导”的单题提示职责明确分离；
- 标准 Agent 协议、消息总线、依赖任务调度、结果聚合和全局状态同步；
- FastAPI 核心接口和可离线运行的确定性降级路径。
- 5·3 新高考题库的 7,577 条资源元数据索引，按学科、A/B 版、地区、专题和内容安全角色检索；原始 39GB 资料不进入 Git 或 Prompt；
- 作业辅导 Agent：支持文字/图片题目、低置信度 OCR 确认、分步最小提示、步骤检查、知识回顾、完整作答校验、同类训练和答案防泄漏；
- 学情诊断 Agent：融合多次独立测评证据，输出带置信度、来源和版本的知识状态、稳定错因、叙事解释与教师审核流；
- 教师备课 Agent：覆盖语文、数学、英语、物理、化学、生物、思想政治、历史、地理九科；教师可从 329 份本地教材 PDF 的真实目录中按教材版本、分册和具体章节选择备课课题，也可使用自定义课题，再结合 27 份优秀教案与班级匿名聚合学情生成目标、活动、板书、检测、作业、动态分层和一致性矩阵；
- 教师备课采用 teacher-in-the-loop：生成、待审核与已批准方案分区展示；候选方案支持完整版本历史、旧版本只读查看及非破坏性回退，仍必须经过质量门禁和教师批准后才能发布；发布时才向学情诊断与作业辅导 Agent 同步评价蓝图；
- 教师备课初稿和 AI 修订接入教师端全局后台任务：教师切换到学生学情、协作管理、通知或诊断卷等业务页面后生成仍继续，右下角持续显示状态，并在完成或失败后提供可点击的结果提醒；生成的方案和版本由服务端保存，刷新后可从备课方案列表继续审核；
- 教案资源保留来源机构、来源定位、版权边界和 SHA256 校验状态；LLM 不可用时明确标记为 `reference_template`，使用教案依据和确定性模板生成可审核草稿；
- 学生端阅读与语言学习 Agent 仅面向参加新高考全国Ⅰ卷的高中英语考生，页面和接口均展示全国Ⅰ卷考试蓝图（150分、阅读/七选五/写作等板块）；不作为四六级、雅思、托福、职场英语或其他试卷类型的泛化工具；
- 英语主控 Agent 根据《阅读与语言学习Agent开发文档》统一路由阅读理解、语境词汇、语法纠错、全国Ⅰ卷应用文/读后续写修改、翻译、文本口语、全国Ⅰ卷训练、学习计划和进度查询；支持快速、教学、引导、考试、沉浸和纠错六种反馈模式，并按 CEFR 动态估计控制反馈数量；
- 英语语法和写作 AI 出题接入统一后台任务运行时：切换模块后请求继续执行，右下角展示出题状态与完成/失败提醒；题组、当前选题和作答进度按学生隔离持久化，刷新后可继续上次训练；
- 阅读结论必须保存逐字原文依据，写作修改必须保留原文数值事实，语法反馈区分错误与风格优化；没有音频时发音分必须为 `null`，模拟反馈不冒充高考官方评分或预测成绩；
- 学习闭环覆盖学习者画像、生词本、重复语法错误置信度、写作与文本口语记录、间隔复习、最近七天周报以及用户主动删除记录；单次错误不会直接升级为稳定薄弱点；原有阅读选择题和七选五证据化训练作为考试阅读专项保留；
- 第六个编程成长 Agent 布置在学生端，首期支持 Python：覆盖最少画像、低门槛诊断、16 周路线、静态检查、H0—H5 渐进提示、高中生小型项目拆解、项目陈述、保守能力更新、周报和考试期自动降载；未进入隔离沙箱时明确标记为“未执行”，默认不提供可提交的完整作业答案；
- MySQL 教师平台支持教师账号、班级、学生匿名学情、通知、诊断卷、版本化教案和课后反馈；学生可随时发起退班申请，但只有所属班级教师审批同意后才会移出班级，拒绝时继续保留班级成员关系；
- Vue 3 + TypeScript 学生端与教师端工作台，教师端提供独立“智能备课”入口和生成—修订—批准—发布—反馈闭环；两端统一采用不小于 14–16px 的主要阅读与输入字号，长列表及教案详情使用显式分页，避免内部横向或纵向滚动条影响课堂浏览；学生端侧栏统一使用“外语学习”和“职业教育”命名，并移除冗余的独立知识画像页，“我的计划”按本周任务、优先补齐和独立规划依据页分层展示，规划说明采用“一个核心总纲—多个分类细节”的主次结构，并将内部知识编号转换为教材中文名称。
- 学生登录页采用问鹿紫色沉浸式背景、居中登录卡片和随机分布的学习主题互动气泡；点击气泡会向上浮出并从页面底部重新进入，同时兼顾移动端布局与减少动态效果偏好。

## 环境、安装与启动

### 运行要求

- Linux、macOS 或 WSL；
- Python 3.11 或 3.12；
- Node.js 20+ 与 npm；
- MySQL 5.7+ 或 MySQL 8；
- 可选：OpenAI-compatible 模型服务；
- 手机验证码登录需要阿里云号码认证服务 PNVS。

### 1. 获取代码并安装依赖

```bash
git clone https://github.com/Mwg806/AI_Education.git
cd AI_Education

conda create -n Mamba python=3.11 -y
conda activate Mamba
python -m pip install -e ".[dev,knowledge]"

npm ci
```

如果已有名为 `Mamba` 的环境，直接激活即可。可选 Anthropic 适配器使用 `pip install -e ".[anthropic]"`；请先确认它不会与现有 vLLM 依赖冲突。

### 2. 配置环境变量

```bash
cp .env.example .env
```

`.env` 只保存在服务器本地，禁止提交 Git。最小数据库配置：

```dotenv
AI_EDUCATION_MYSQL_ENABLED=true
AI_EDUCATION_MYSQL_HOST=127.0.0.1
AI_EDUCATION_MYSQL_PORT=3306
AI_EDUCATION_MYSQL_USER=root
AI_EDUCATION_MYSQL_PASSWORD=<mysql-password>
AI_EDUCATION_MYSQL_DATABASE=ai_education
AI_EDUCATION_MYSQL_CONNECT_TIMEOUT_SECONDS=5
AI_EDUCATION_AUTH_SESSION_HOURS=168
```

学生和教师无密码登录使用阿里云 PNVS：

```dotenv
AI_EDUCATION_PHONE_AUTH_ENABLED=true
ALIBABA_CLOUD_ACCESS_KEY_ID=<access-key-id>
ALIBABA_CLOUD_ACCESS_KEY_SECRET=<access-key-secret>
AI_EDUCATION_PHONE_AUTH_SCHEME_NAME=问鹿用户认证
AI_EDUCATION_PHONE_AUTH_SIGN_NAME=<已审核签名>
AI_EDUCATION_PHONE_AUTH_TEMPLATE_CODE=<模板编号>
AI_EDUCATION_PHONE_AUTH_CODE_LENGTH=6
AI_EDUCATION_PHONE_AUTH_CODE_TTL_SECONDS=300
AI_EDUCATION_PHONE_AUTH_RESEND_SECONDS=60
```

单一超级管理员必须使用服务端密码哈希，不能把明文密码写入 `.env`：

```bash
PYTHONPATH=src python -m ai_education.cli admin-password-hash
```

将输出的完整 `scrypt_v1$...$...` 结果用单引号包裹后写入：

```dotenv
AI_EDUCATION_ADMIN_USERNAME=super_admin
AI_EDUCATION_ADMIN_PASSWORD_HASH='scrypt_v1$<salt>$<digest>'
AI_EDUCATION_ADMIN_SESSION_HOURS=8
```

管理员账号只允许英文字母、数字、点、下划线和连字符。实际密码只在登录页面输入；`.env` 中只保存哈希。

可选模型配置：

```dotenv
AI_EDUCATION_LLM_ENABLED=true
AI_EDUCATION_LLM_PROVIDER=openai
AI_EDUCATION_LLM_MODEL=<model-name>
AI_EDUCATION_LLM_TEMPERATURE=0.3
AI_EDUCATION_LLM_TIMEOUT_SECONDS=90
AI_EDUCATION_ALLOW_RULE_FALLBACK=false
OPENAI_API_KEY=<secret>
OPENAI_BASE_URL=<compatible-v1-endpoint>
```

所有服务端密钥都不能使用 `VITE_` 前缀。完整变量及安全默认值见 [`.env.example`](.env.example)。

### 3. 初始化数据库

先确保 MySQL 服务已启动且配置账号有建库权限。API 第一次启动会以 `CREATE DATABASE/TABLE IF NOT EXISTS` 方式初始化基础结构。版本化迁移可执行：

```bash
set -a
source .env
set +a
PYTHONPATH=src python scripts/apply_migrations.py
```

迁移脚本记录校验和并跳过已执行版本；回滚文件默认只提供数据保留型说明，不自动删除生产数据。

### 4. 启动后端

```bash
cd /path/to/AI_Education
set -a
source .env
set +a
export PYTHONPATH=/path/to/AI_Education/src
python -m ai_education.cli serve --host 127.0.0.1 --port 8000
```

- 健康检查：`http://127.0.0.1:8000/health`
- OpenAPI 文档：`http://127.0.0.1:8000/docs`

### 5. 分别启动学生端与教师端

学生端使用 3000 端口：

```bash
cd /path/to/AI_Education
npm run dev:student
```

访问 `http://127.0.0.1:3000`。

另开终端启动教师端，使用 3005 端口：

```bash
cd /path/to/AI_Education
npm run dev:teacher
```

访问 `http://127.0.0.1:3005`。两个前端都会把 `/agent-api` 代理到 `127.0.0.1:8000`，但登录入口、会话和工作台按角色隔离。

### 6. 启动超级管理员端

另开终端：

```bash
cd /path/to/AI_Education
npm run dev:admin
```

访问 `http://127.0.0.1:3010`。管理员端使用独立会话，只提供：

- 分页检索学生和教师账号；
- 学生新手机号短信验证与补绑；
- 师生离校账号永久注销及关联数据清理；
- 登录、补绑和注销操作审计。

局域网设备可将 `127.0.0.1` 替换为服务器局域网 IP。开发服务器不包含进程守护、TLS 或日志轮转，正式部署应配合 systemd、Docker Compose 或反向代理。

### 生产构建

```bash
npm run build:student
npm run build:teacher
npm run build:admin
```

学生端、教师端和管理员端必须分别构建到 `dist/student`、`dist/teacher` 和 `dist/admin`；构建产物不能包含服务端密钥。

## 验证

日常开发至少运行：

```bash
conda activate Mamba
ruff check --select E9,F63,F7,F82 src tests scripts
ruff check src/ai_education/api/app.py src/ai_education/services/quick_diagnostic_bank.py
pytest -q
python -m compileall -q src/ai_education
npm run typecheck
npm run build:student
npm run build:teacher
npm run build:admin
```

正式上线前，先把验收通过的代码合并并推送到 `origin/main`，然后在干净的本地
`main` 工作树执行统一门禁：

```bash
npm run preflight:release
```

该命令会核对本地与远端主干、运行关键 Python 静态检查与编译、完整后端测试，
并构建学生端、教师端和管理员端。任一步失败都不得继续部署。

## 代码结构

```text
src/ai_education/
├── agents/          # 六个独立 LangGraph Agent
├── api/             # FastAPI 核心接口
├── domain/          # 领域模型、状态和消息协议
├── llm/             # 可选模型工厂与结构化输出链
├── orchestration/   # 注册、消息总线、聚合、调度和全局状态
├── prompts/         # 版本化系统提示词
├── resources/       # 版本化考试政策配置
├── services/        # 目标、画像、练习、时间和计划确定性服务
└── tools/           # LangChain StructuredTool 适配器

components/          # Vue 学生端、教师端与智能备课工作台组件
lib/                 # 多 Agent 前端协议、API 客户端与演示适配器
styles/              # 蓝白主题、响应式布局与基础样式
```

生产部署与回滚见 [`docs/deployment.md`](docs/deployment.md)，架构细节见 [`docs/architecture.md`](docs/architecture.md)，渐进式多 Agent 重构见 [`docs/progressive_multi_agent_refactor.md`](docs/progressive_multi_agent_refactor.md)，需求覆盖见 [`docs/requirements_traceability.md`](docs/requirements_traceability.md)。

## 源码与变更流程

- `origin/main` 是唯一长期维护分支和发布依据；历史功能分支只保留在提交记录中，不作为部署源。
- 开始工作前执行 `git switch main && git pull --ff-only origin main`，并确认工作树干净。
- 只暂存明确文件路径；提交后执行 `git pull --rebase origin main`，再普通 `git push origin main`。
- 禁止从生产 ECS 的脏工作树直接 `pull`、`commit`、`rebase`、`push`，禁止 force push。
- 线上修复也必须先提交 GitHub，再从 GitHub commit 构建和部署；回退使用 `git revert` 与上一份发布产物，不重写 `main` 历史。
