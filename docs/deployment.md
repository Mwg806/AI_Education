# AI_Education 生产部署与复现

本文档定义从 GitHub `main` 到生产环境的唯一发布顺序。目标是让每次发布都能回答三个问题：源码来自哪个 commit、部署前通过了哪些门禁、失败时如何恢复上一版本。

发布顺序总览：

```text
锁定 main SHA → 完整门禁 → 制作并校验发布包 → 备份 → 数据库迁移
→ 隔离安装/构建 → 后端切换与健康检查 → 前端原子切换 → 公网验收 → 记录/回滚点
```

## 1. 不可破坏的发布原则

1. `origin/main` 是唯一长期源码真源，生产服务器不是开发仓库。
2. 每次发布必须绑定完整 commit SHA；不得用“服务器当前目录”或未提交文件作为发布依据。
3. `.env`、数据库、日志、上传文件、密钥、`node_modules`、`dist` 和 `deploy-backups` 不进入 Git。
4. 禁止在生产脏工作树上直接 `git pull`、`git rebase`、`git commit`、`git push` 或 force push。
5. 数据库迁移、后端切换和前端切换必须按本文顺序执行，并在每个阶段保留停止或回滚点。

## 2. 版本与运行要求

- Linux、macOS 或 WSL 构建环境；
- Python 3.11 或 3.12；
- Node.js 20+ 与 npm；
- MySQL 5.7+ 或 MySQL 8；
- 生产反向代理和进程守护工具，例如 Nginx 与 systemd。

生产服务器的 `.env` 必须从 [`.env.example`](../.env.example) 单独配置。所有模型、数据库和短信服务凭据只保存在服务器密钥管理或受限配置文件中，不得复制到发布包、命令行参数、日志或聊天记录。

## 3. 首次复现环境

在长期使用的干净目录中执行：

```bash
git clone git@github.com:Mwg806/AI_Education.git
cd AI_Education
git switch main
git pull --ff-only origin main

conda create -n Mamba python=3.11 -y
conda activate Mamba
python -m pip install -e ".[dev,knowledge]"
npm ci

cp .env.example .env
```

填写本地 `.env` 后，按 README 的启动顺序启动 MySQL、后端、学生端、教师端和管理员端。不得把真实 `.env` 提交 Git。

## 4. 每次发布的固定顺序

### 4.1 锁定干净的 main

```bash
git switch main
git pull --ff-only origin main
git status --short
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

继续发布前必须同时满足：

- `git status --short` 无输出；
- 本地 HEAD 与 `origin/main` SHA 完全一致；
- 当前分支为 `main`。

将完整 SHA 记为本次 `RELEASE_SHA`。所有备份目录、发布目录和部署记录都应包含该 SHA。

### 4.2 安装锁定依赖并运行完整门禁

```bash
conda activate Mamba
python -m pip install -e ".[dev,knowledge]"
npm ci
npm run preflight:release
```

`preflight:release` 会检查 main/远端一致性、工作树、Python 关键错误、编译、完整后端测试、TypeScript 类型，并构建学生端、教师端和管理员端。任一步失败都必须停止发布。

生产输出目录为：

```text
dist/student
dist/teacher
dist/admin
```

构建脚本显式设置 `VITE_AGENT_DEMO_MODE=false`。任何服务端密钥都不得使用 `VITE_` 前缀。

### 4.3 制作可验证发布包

推荐从 commit 本身生成源码包，而不是复制当前工作目录：

```bash
git archive --format=tar.gz --output "AI_Education-${RELEASE_SHA}.tar.gz" "${RELEASE_SHA}"
sha256sum "AI_Education-${RELEASE_SHA}.tar.gz"
```

上传后在服务器再次计算 SHA256，必须与构建端一致。发布包不得包含 `.env`、运行数据库、日志、上传目录或旧构建缓存。

### 4.4 部署前备份

在修改生产环境前至少备份：

- 当前发布源码或发布目录；
- 当前 `dist/student`、`dist/teacher`、`dist/admin`；
- 数据库（使用云数据库快照或受控备份工具，并验证可恢复）；
- 当前 systemd/Nginx 配置版本；
- 当前线上 commit SHA 和健康检查结果。

`.env` 应保留在生产共享配置目录中，不要复制进可能被提交或公开下载的部署备份。

### 4.5 校验并执行数据库迁移

先在新发布源码中检查迁移清单：

```bash
set -a
source /path/to/shared/.env
set +a
PYTHONPATH=src python scripts/apply_migrations.py --dry-run
PYTHONPATH=src python scripts/apply_migrations.py --rollback-plan
```

确认数据库备份可用后再执行：

```bash
PYTHONPATH=src python scripts/apply_migrations.py
```

迁移器按文件名顺序执行，记录 SHA256，已应用版本会跳过，已应用文件发生校验和漂移时会拒绝继续。回滚计划只打印数据保留型说明，不会自动删除生产数据。已发布迁移文件不得修改；需要修正时新增后续迁移。

### 4.6 在隔离目录安装与构建

不要直接清空或覆盖当前线上目录。将新源码解压到带 SHA 的隔离目录，例如：

```text
/opt/AI_Education/releases/<RELEASE_SHA>
```

在该目录中安装依赖、链接受限的共享 `.env`，并再次运行至少以下检查：

```bash
npm ci
npm run typecheck
NODE_OPTIONS=--max-old-space-size=1024 npm run build:student
npm run build:teacher
npm run build:admin
```

需要更新后端时，应使用该发布目录自己的 Python 环境或一个按锁定依赖管理的共享环境。构建完成后检查三个 `index.html` 和其引用的哈希资源均存在。

### 4.7 切换后端并检查健康状态

如果本次包含后端变更：

1. 让 systemd 的工作目录/启动命令指向新发布目录；
2. 重启后端服务；
3. 确认服务为 `active`；
4. 确认 `http://127.0.0.1:8000/health` 返回 200；
5. 检查启动日志，不得继续发布已出现异常的版本。

如果只修改前端或文档，不需要重启后端。

### 4.8 原子切换前端

先把新构建产物放入非线上目录并完成本机 HTTP/文件检查，再通过同一文件系统内的目录重命名或 `current` 软链接切换。推荐布局：

```text
/opt/AI_Education/
├── releases/<RELEASE_SHA>/
├── shared/.env
├── current -> releases/<RELEASE_SHA>
└── deploy-backups/<previous-release>/
```

Nginx 静态目录和 systemd 工作目录应指向 `current` 下的对应路径。软链接切换后重新加载 Nginx；配置检查失败时不得 reload。

### 4.9 线上验收

至少检查：

- AI 后端服务和 Nginx 均为 active；
- 后端 `/health` 为 HTTP 200；
- 学生端首页、当前 JS、当前 CSS 为 HTTP 200；
- 教师端和管理员端入口可访问；
- 登录、快速诊断、规划、作业辅导、英语语法/写作出题、后台完成提醒和刷新恢复正常；
- 教师端备课初稿与 AI 修订在切换到其他业务模块后仍继续生成，右下角进行中/完成/失败提醒可见且能返回对应备课页面，刷新后服务端方案记录仍可加载；
- 生产 bundle 没有 demo 模式阻断或服务端密钥；
- 数据库迁移账本、关键日志和错误率正常。

验收完成后记录：commit SHA、时间、操作者、迁移版本、构建资源名、测试结果和回滚目录。

## 5. 回滚顺序

发现故障时按以下顺序处理：

1. 停止继续发布；
2. 将前端 `current` 或静态目录切回上一份已验证产物；
3. 如后端变更导致故障，将 systemd 指回上一发布目录并重启；
4. 验证上一版本健康接口和公网入口；
5. 数据库默认保留新增表/列，不自动 DROP；只有在确认数据影响并有可恢复备份时，才人工执行审核过的回滚方案；
6. 在 GitHub 使用 `git revert` 生成新的 main 提交，再重新走完整发布流程。

禁止通过 force push、`git reset --hard` 生产仓库或直接修改线上源码来“修复”发布。

## 6. 日常开发与紧急修复

日常变更：

```bash
git switch main
git pull --ff-only origin main
# 修改与验证
git add -- <明确文件路径>
git commit -m "feat: describe the change"
git pull --rebase origin main
git push origin main
```

紧急问题也遵循相同顺序：先在 GitHub 修复、验证和提交，再部署该 commit。生产 ECS 上的临时排查不得演变为长期源码；如确实发生应急热修，必须立即把同一修复还原为 GitHub 提交，并用 GitHub 构建产物覆盖临时版本。

## 7. 发布完成判定

只有同时满足以下条件，发布才算完成：

- GitHub `main`、部署记录和线上版本指向同一 SHA；
- 发布门禁、迁移和线上验收均通过；
- 回滚产物与数据库备份可用；
- 生产源码没有未归档的独有修改；
- README、本文档和必要交接记录已同步更新。
