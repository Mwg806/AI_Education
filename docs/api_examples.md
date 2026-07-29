# API 示例

## 获取画像可选目录

`GET /api/v1/catalog/onboarding`

返回全国新课标Ⅰ卷知识库当前覆盖的 11 个省份、各省选科结构，以及语文、数学、英语、
思想政治、历史、地理、物理、化学、生物学、技术 10 个规划科目的教材登记信息、课程标准
模块与官方来源。客户端不得自行补充省份、教材或章节常量：

- `catalog_status=VERIFIED_OFFICIAL` 时，`volumes[].chapters` 可作为教材章节选项；
- 其他状态只允许使用 `standard_modules`，并应提示用户依据学校教材版权页确认；
- 语文、数学、英语始终可作为重点规划科目；省级选考科目必须属于学生已确认的合法选科组合；
- 浙江“技术”同时路由到信息技术和通用技术两份课程标准；
- `scope.annual_reconfirmation_required=true` 表示目标高考年份仍需按当年考试院通知复核。

## 创建首版计划

`POST /api/v1/planner/initialize`

```json
{
  "student_id": "student_10001",
  "idempotency_key": "student_10001_initialize_v1",
  "payload": {
    "student_profile": {
      "student_id": "student_10001",
      "grade": "grade_11",
      "school_term": "grade_11_term_1",
      "province_code": "43",
      "school_entry_year": 2024,
      "target_exam_year": 2027,
      "curriculum_versions": {"mathematics": "people_education_a"},
      "selected_subjects": ["physics", "chemistry", "biology"],
      "subject_selection_confirmed": true,
      "class_progress": {"mathematics": "PEA-E2-C05"}
    },
    "goal_text": "我数学最近92分，希望高三一模达到120分",
    "goal_deadline": "2027-05-20",
    "weekly_available_minutes": 630,
    "knowledge_evidence": [
      {
        "knowledge_id": "math_function_foundation",
        "score": 0.45,
        "weight": 0.9,
        "source_type": "mock_exam",
        "source_id": "mock_001_q1",
        "description": "函数基础题得分证据"
      }
    ],
    "daily_capacity": [
      {"weekday": 1, "available_minutes": 90, "preferred_period": "evening"},
      {"weekday": 3, "available_minutes": 90, "preferred_period": "evening"},
      {"weekday": 6, "available_minutes": 180, "preferred_period": "morning"}
    ]
  }
}
```

成功后返回 `waiting_for_confirmation` 的计划。客户端应展示考试配置、目标、主要缺口、预算、首阶段计划、风险和缓冲，再调用确认接口。

## 确认计划

`POST /api/v1/plans/{plan_id}/confirm`

```json
{
  "student_id": "student_10001",
  "expected_version": 1,
  "idempotency_key": "student_10001_plan_confirm_v1"
}
```

确认成功会创建版本 2，状态变为 `active`，不会覆盖草稿版本 1。

## 上报练习事件

`POST /api/v1/learning-events`

```json
{
  "student_id": "student_10001",
  "idempotency_key": "evt_001",
  "event": {
    "event_id": "evt_001",
    "student_id": "student_10001",
    "session_id": "practice_301",
    "task_id": "task_example",
    "item_id": "item_5001",
    "subject": "mathematics",
    "knowledge_ids": ["math_function_foundation"],
    "event_type": "answer_submitted",
    "timestamp": "2026-07-29T20:11:31+08:00",
    "response": {"correct": true, "score": 5, "max_score": 5, "difficulty": 0.6},
    "behavior": {"response_time_seconds": 300, "hint_count": 0, "attempt_count": 1}
  }
}
```

重复事件返回 `duplicate=true`，不会第二次更新画像。一次普通错误只触发规则检查，不直接重建整周计划。
