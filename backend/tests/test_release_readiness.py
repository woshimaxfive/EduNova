from backend.evals.release_readiness import PERFORMANCE_TARGETS_MS, build_report, percentile_95


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


def test_fast_single_samples_cannot_pass_performance_gate() -> None:
    report = build_report({name: [1] for name in PERFORMANCE_TARGETS_MS})
    assert report["status"] == "evidence_gap"
    assert not report["performance_evidence_complete"]
    assert all(item["status"] == "insufficient_samples" for item in report["performance"].values())


def test_nonfinite_and_boolean_samples_are_not_timings() -> None:
    report = build_report({"model_first_token": [True, False, float("inf"), float("nan"), -1, 10]})
    assert report["performance"]["model_first_token"]["sample_count"] == 1
    assert report["performance"]["model_first_token"]["observed_p95_ms"] == 10


def test_offline_quality_and_flat_timings_cannot_prove_live_readiness() -> None:
    report = build_report({name: [1] * 30 for name in PERFORMANCE_TARGETS_MS})
    assert report["performance_evidence_complete"]
    assert report["live_quality_status"] == "not_reviewed"
    assert report["quality_evidence_source"] == "offline_fixtures"
    assert report["status"] == "evidence_gap"
    assert not report["release_evidence_complete"]


def test_failed_calls_are_not_hidden_by_fast_successes() -> None:
    report = build_report({name: [1] * 30 for name in PERFORMANCE_TARGETS_MS},
                          {"attempts": [{"ok": True}] * 30 + [{"ok": False}], "complete": True})
    assert report["status"] == "failed"
    assert report["collection"]["failed_attempts"] == 1
    assert report["collection"]["error_rate"] > 0.01
