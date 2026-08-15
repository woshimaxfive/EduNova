from backend.evals.release_readiness import build_report, percentile_95


def test_percentile_95_uses_nearest_rank() -> None:
    assert percentile_95([10, 20, 30, 40, 50]) == 50
    assert percentile_95([]) is None


def test_release_report_never_claims_unmeasured_live_performance() -> None:
    report = build_report()

    assert report["quality"]["citation_valid_rate"] == 1
    assert report["quality"]["deterministic_number_consistency_rate"] == 1
    assert report["quality"]["sensitive_or_prompt_leak_hits"] == 0
    assert report["performance_evidence_complete"] is False
    assert report["performance"]["model_first_token"]["status"] == "not_measured"
    assert report["status"] == "evidence_gap"


def test_release_report_fails_a_measured_threshold_without_changing_quality() -> None:
    measurements = {
        "non_ai_api_p95": [150],
        "rag_retrieval_p95": [400],
        "sse_first_status": [300],
        "model_first_token": [16_000],
        "ai_job_create": [200],
        "ai_job_progress": [500],
        "resource_batch_3": [20_000],
    }

    report = build_report(measurements)

    assert report["quality"]["passed"] is True
    assert report["performance"]["model_first_token"]["status"] == "failed"
    assert report["status"] == "failed"
