from backend.evals.run import evaluate_case, load_cases, run_offline


def test_offline_quality_cases_cover_core_model_boundaries() -> None:
    cases = load_cases()
    assert {case["workflow"] for case in cases} == {
        "profile",
        "course_builder",
        "home_tutor",
        "course_tutor",
        "resource_generation",
        "path_planning",
        "assessment",
        "report",
        "material_comparison",
    }
    assert len([case for case in cases if case["workflow"] == "profile"]) >= 2
    assert all(result["passed"] for result in run_offline())


def test_quality_evaluator_rejects_fake_citation_sensitive_echo_and_score_changes() -> None:
    case = {
        "id": "unsafe",
        "workflow": "assessment",
        "candidate": "system prompt sk-secret 最终得分为 90",
        "citation_ids": ["fake:1"],
        "allowed_citation_ids": ["real:1"],
        "required_terms": ["最终得分"],
        "forbidden_terms": ["system prompt", "sk-"],
        "deterministic_score": 40,
        "reported_score": 90,
    }
    result = evaluate_case(case)
    assert result["passed"] is False
    assert result["checks"]["no_sensitive_echo"] is False
    assert result["checks"]["citations_valid"] is False
    assert result["checks"]["deterministic_numbers_unchanged"] is False


def test_live_text_never_inherits_fixture_citation_or_score_proof() -> None:
    case = load_cases()[2]
    result = evaluate_case(case, "规则评分为 99，错因待分析。引用不存在的资料。")
    assert result["checks"]["citations_valid"] is None
    assert result["checks"]["deterministic_numbers_unchanged"] is None
    assert result["status"] == "evidence_gap"
    assert not result["passed"]
