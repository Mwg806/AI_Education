from __future__ import annotations


def planner_payload() -> dict:
    return {
        "student_profile": {
            "student_id": "student_10001",
            "grade": "grade_11",
            "school_term": "grade_11_term_1",
            "province_code": "43",
            "school_entry_year": 2024,
            "target_exam_year": 2027,
            "curriculum_versions": {"mathematics": "people_education_a"},
            "selected_subjects": ["physics", "chemistry", "biology"],
            "subject_selection_confirmed": True,
            "class_progress": {"mathematics": "PEA-E2-C05"},
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
                "description": "函数基础题得分证据",
                "error_tags": ["concept_confusion"],
            },
            {
                "knowledge_id": "math_derivative_application",
                "score": 0.58,
                "weight": 0.9,
                "source_type": "mock_exam",
                "source_id": "mock_001_q12",
                "description": "导数应用得分证据",
            },
            {
                "knowledge_id": "math_analytic_geometry",
                "score": 0.62,
                "weight": 0.8,
                "source_type": "self_assessment",
                "source_id": "self_001",
                "description": "解析几何自评",
            },
        ],
        "prerequisite_edges": [
            {
                "prerequisite": "math_function_foundation",
                "target": "math_derivative_application",
                "strength": 1.0,
            }
        ],
        "daily_capacity": [
            {
                "weekday": day,
                "available_minutes": 90,
                "preferred_period": "evening",
                "energy_coefficient": 0.9,
            }
            for day in range(1, 8)
        ],
        "subject_factors": {
            "mathematics": {"goal_priority": 1, "score_gap": 1, "urgency": 0.8},
            "physics": {"goal_priority": 0.5, "score_gap": 0.6},
        },
        "plan_start": "2026-07-30",
    }
