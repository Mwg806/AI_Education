# 作业辅导 Agent 设计与运行说明

## 职责边界

`HomeworkTutorAgent` 只负责一道作业题的读取、分步提示、过程检查、作答校验和同类迁移。
它不生成学习计划，也不能直接修改 `PersonalizedLearningPlannerAgent` 的计划或画像。
完成辅导后，它只发布带来源和置信度的学习证据，由规划 Agent 的既有校验规则决定是否更新。

学生未提交完整作答前，系统禁止输出可直接抄写的完整答案、连续推导或解析原文。每轮只释放
一个最小提示；所有候选输出必须经过 `AnswerLeakageGuard` 后才进入学生可见消息。

## LangGraph 流程

```text
统一请求协议
  -> 会话/身份校验
  -> 文字或内存图片输入
  -> 低置信度 OCR 人工确认
  -> 题目解析与学科/题型/知识点识别
  -> 5·3 元数据检索
  -> 提示 / 步骤检查 / 知识回顾 / 作答校验 / 同类训练
  -> 答案泄漏守卫
  -> 乐观锁持久化、审计事件、规划证据事件
  -> 统一响应协议
```

会话、题目、答案保险库、审计记录和幂等键分别存储。答案保险库只允许校验节点读取，
公共 API 与前端类型中不存在答案字段。

## 题库利用方式

原始资料在生产环境保存在私有 OSS 的 `knowledge/raw/title/` 前缀，约 39GB；本地开发可按相同
相对结构放在 `Knowledge/title/2026五年高考三年模拟53A、B版新高考全套资料`。原件不会提交
Git、不会批量塞入 Prompt，也不会通过 API 暴露文件路径。构建脚本只生成以下元数据：

- `Knowledge/catalogs/question_bank_catalog.json`：可复核的 JSON 目录；
- `Knowledge/91_indexes/question_bank.db`：按学科、内容角色和地区建立索引的 SQLite 文件；
- 内容角色分为练习、答案隔离、解析隔离、配套材料和封面；
- 检索结果只返回标题、专题、A/B 版、地区、文件类型和匹配置信度。

重新构建索引：

```bash
conda activate Mamba
python Knowledge/scripts/build_question_bank_index.py
```

当前语料没有可靠的技术学科 5·3 文件，因此技术科目不会伪造题库命中；仍可依据已验证教材目录
进行输入和通用辅导，界面会如实显示无题库证据。

## API

- `GET /api/v1/agents/manifest`：两个 Agent 的独立工具能力；
- `GET /api/v1/homework/question-bank/summary`：安全的题库统计；
- `POST /api/v1/homework/question-bank/search`：安全的题库元数据检索；
- `POST /api/v1/homework/sessions`：创建或恢复辅导会话；
- `POST /api/v1/homework/sessions/{session_id}/turns`：提交文字、步骤和最多三张图片；
- `POST /api/v1/homework/sessions/{session_id}/ocr-confirmation`：确认低置信度识别文本；
- `POST /api/v1/homework/questions/{question_id}/submission`：提交完整作答；
- `POST /api/v1/homework/questions/{question_id}/variants`：请求同类训练来源；
- `GET /api/v1/homework/sessions/{session_id}`：读取本人会话状态。

Vue 工作台的“作业辅导”入口可以无计划独立使用；已有计划时可关联同科目任务。生产静态站点默认
显示安全演示数据，服务器开发页通过 `/agent-api` 代理调用真实后端。
