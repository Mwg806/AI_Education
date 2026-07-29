# 全国新课标Ⅰ卷教育知识库

本目录是个性化学习规划智能体的可追溯知识底座，覆盖 2026 年采用全国新课标Ⅰ卷的
浙江、山东、江苏、河北、福建、湖北、湖南、广东、江西、安徽、河南 11 个省份。

当前版本已实现：

- 教育部 2020 修订普通高中课程方案及 11 个学科课程标准的官方原文、逐页文本和语义分块；
- 2025 年课程标准日常修订解读专刊的官方目录索引，用于提示版本差异而不冒充全文；
- 11 省“全国统考科目 / 省级选择考科目”路由，含浙江信息技术、通用技术分支；
- 语文、数学、英语、物理、化学、生物学、思想政治、历史、地理、信息技术、通用技术的课程知识分类；
- 教材出版社、版次、册次目录和授权状态，不包含未获授权的教材正文；
- 数学人教 A 版 18 章、人教 B 版 17 章的出版社官方目录；其他版本只登记册次并回退到课标主题；
- JSONL 原始分块、Markdown 页级文本、SQLite FTS5 中文双字检索索引；
- 来源白名单、SHA-256、页码、版权状态、审核状态及质量报告。

## 目录说明

| 目录 | 用途 |
|---|---|
| `00_manifest` | 来源注册表、文件清单、采集队列和覆盖矩阵 |
| `01_official_standards` | 官方公开课程方案与课程标准原始 PDF |
| `02_exam_policy`—`11_error_patterns` | 后续按证据级别扩充的政策、真题、评分、教研资料 |
| `12_student_private` | 学生私有数据隔离区，不进入公共索引 |
| `catalogs` | 省份考试路由、教材版本目录 |
| `curated` | 有出处的人工结构化知识和检索策略 |
| `taxonomy` | 跨学科稳定知识分类 |
| `90_processed` | 页级文本、Markdown 和统一分块 |
| `91_indexes` | 可直接查询的 SQLite FTS5 索引 |
| `92_reports` | 构建与校验报告 |
| `99_quarantine` | 重复、不可读、版权/版本不明资料隔离区 |

## 构建与查询

所有命令必须在项目指定环境中执行：

```bash
conda activate Mamba
python Knowledge/scripts/build_knowledge_base.py
python Knowledge/scripts/validate_knowledge_base.py
python Knowledge/scripts/query_knowledge_base.py "函数单调性与导数" --subject mathematics
python Knowledge/scripts/query_knowledge_base.py "浙江技术选考" --province zhejiang
python Knowledge/scripts/query_knowledge_base.py "一核四层四翼"
```

流水线只会下载 `00_manifest/source_registry.json` 中登记、HTTPS 域名在白名单内且标记为
`OFFICIAL_PUBLIC` 的文件。`--no-download` 可只处理已下载文件，`--only DOCUMENT_ID` 用于单文档调试。

## 智能体检索规则

1. 先固定考试体系、省份、科目、年份、教材版本，再检索内容。
2. 统考语数外使用国家课程标准和全国卷证据；选择考科目使用国家课标和对应省级证据。
3. 教材版本未确认时只返回课标与公共知识，不默认人教版。
4. 回答必须携带标题、来源 URL、原 PDF 页码、版本、版权及审核状态。
5. `AUTO_EXTRACTED_REVIEW_REQUIRED` 内容可用于召回，但高风险结论需人工对照原 PDF。
6. 权威冲突时按 A（官方）→ B（出版社/教研机构）→ C（学校教研）→ D（开放补充）排序，并保留版本差异。

## 版权与数据边界

- 官方公开课标按来源链接和页码存档；不移除署名，不对外再分发为独立出版物。
- 教材、教辅、试题解析只在取得解析、向量化和展示授权后入库；未授权项目保持 `LINK_ONLY` 或
  `AUTHORIZATION_REQUIRED`。
- 学生作答、画像和错题属于私有数据，应单独授权、加密和删除，不得写入公共 FTS 索引。
- 网络流传的“完整版教材”“内部题库”不得作为采集来源。

## 当前缺口

官方 2020 修订课程标准底座已落地；2025 日常修订版目前只有官方专题目录索引，正式全文需待官方
发布页核验后再纳入。全国卷真题、11 省选择性考试真题、评分细则和学校实际教材版本需按
`00_manifest/acquisition_queue.csv` 逐项核验官方来源与版权后扩充；目录中预留了对应位置，但不会用
来源不明资料填充数量。
