# 高考真题专业学情诊断卷

本目录由 `scripts/build_exam_diagnosis_bank.py` 从同级各科高考真题解析卷自动生成。

- 学生端题面：各科目录内的 JSON。
- 后端专用答案：`answers/`，禁止由静态前端直接发布。
- 原题公式和插图：`assets/`。
- 每道题均记录原始 DOCX 相对路径、SHA-256 和原题号。
- `integrity_report.json` 为数量、题型、答案及来源完整性校验结果。
