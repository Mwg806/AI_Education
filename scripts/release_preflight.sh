#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "发布检查失败：当前分支不是 main。" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "发布检查失败：工作树不干净，请先提交或妥善处理改动。" >&2
  git status --short >&2
  exit 1
fi

echo "[1/8] 同步并核对 origin/main"
git fetch origin main --quiet
if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
  echo "发布检查失败：本地 main 与 origin/main 不一致。" >&2
  exit 1
fi

echo "[2/8] 检查 Git 差异格式"
git diff --check

echo "[3/8] 检查关键 Python 错误规则"
ruff check --select E9,F63,F7,F82 src tests scripts

echo "[4/8] 检查本次上线关键后端模块"
ruff check \
  src/ai_education/agents/teacher_preparation.py \
  src/ai_education/api/app.py \
  src/ai_education/api/teacher_preparation_schemas.py \
  src/ai_education/services/quick_diagnostic_bank.py \
  src/ai_education/services/teacher_preparation.py \
  src/ai_education/teacher_preparation_repository.py \
  src/ai_education/tools/teacher_preparation.py

echo "[5/8] 编译 Python 运行代码"
python -m compileall -q src/ai_education

echo "[6/8] 运行完整后端测试（禁止排除已知失败）"
pytest -q

echo "[7/8] 检查前端类型"
npm run typecheck

echo "[8/8] 构建学生端、教师端和管理员端"
npm run build:student
npm run build:teacher
npm run build:admin

echo "发布前检查全部通过。"
