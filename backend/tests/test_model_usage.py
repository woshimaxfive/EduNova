from __future__ import annotations

import json

import httpx
import pytest

from backend.app.providers.model_usage import capture_usage, estimate_cost, normalize_usage, report_usage, summarize_attempts
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider, OpenAICompatibleConfig, ModelProviderError
from backend.app.services.model_execution import ModelExecutionContext, ModelExecutionRuntime, model_execution_scope
from backend.tests.test_model_execution import FakeAudit, FakeState, make_settings, run


@pytest.mark.parametrize("payload,expected", [
    ({}, (None, None, None, None)),
    ({"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": 60}}, (100, 60, None, None)),
    ({"prompt_tokens": 100, "prompt_cache_hit_tokens": 60, "prompt_cache_miss_tokens": 40}, (100, 60, None, 40)),
    ({"input_tokens": 100, "input_tokens_details": {"cached_tokens": 60, "cache_write_tokens": 10}}, (100, 60, 10, 30)),
    ({"prompt_tokens": 0, "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}}, (0, 0, 0, 0)),
    ({"prompt_tokens": True, "prompt_cache_hit_tokens": -1}, (None, None, None, None)),
    ({"prompt_tokens": 100, "prompt_cache_hit_tokens": 200}, (100, 200, None, None)),
])
def test_usage_unknown_zero_aliases_and_invalid_counts(payload, expected):
    usage = normalize_usage(payload)
    assert tuple(usage[key] for key in ("input_tokens", "cache_read_tokens", "cache_write_tokens", "uncached_input_tokens")) == expected


def test_summary_does_not_hide_unknown_retry_costs_or_double_count_reasoning():
    known = normalize_usage({"prompt_tokens": 100, "completion_tokens": 20, "completion_tokens_details": {"reasoning_tokens": 10}, "prompt_cache_hit_tokens": 60})
    summary = summarize_attempts([normalize_usage(None), known])
    assert summary["input_tokens"] is None
    assert summary["known_input_tokens"] == 100
    assert summary["known_output_tokens"] == 20
    assert summary["cache_hit_ratio"] is None
    assert summary["estimated_cost"] is None
    inconsistent = summarize_attempts([
        normalize_usage({"prompt_tokens": 100, "prompt_cache_hit_tokens": 200}),
        normalize_usage({"prompt_tokens": 300, "prompt_cache_hit_tokens": 0}),
    ])
    assert inconsistent["cache_hit_ratio"] is None


def test_provider_usage_is_recorded_before_invalid_answer_retry():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "" if calls == 1 else "答案"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "prompt_cache_hit_tokens": 60, "prompt_cache_miss_tokens": 40,
                      "secret": "never-store"}})
    provider = OpenAICompatibleChatProvider(httpx.MockTransport(handler))
    audit = FakeAudit()
    runtime = ModelExecutionRuntime(make_settings(), state=FakeState(), audit=audit, sleeper=lambda _: None)
    result = run(runtime, lambda: provider.chat_completion(OpenAICompatibleConfig("https://fixture.test/v1", "synthetic", "fixture"), [{"role": "user", "content": "private question"}], 2))
    assert result == "答案"
    summary = summarize_attempts(audit.records[0]["context"].usage_attempts)
    assert summary["input_tokens"] == 200
    assert summary["output_tokens"] == 40
    assert summary["cache_hit_ratio"] == 0.6
    assert [a["status"] for a in summary["attempts"]] == ["failed", "completed"]
    assert "never-store" not in json.dumps(summary)
    assert "private question" not in json.dumps(summary)


@pytest.mark.parametrize("base_url,enabled,requested", [
    ("https://api.openai.com/v1", False, True),
    ("https://api.deepseek.com/v1", False, True),
    ("https://fixture.test/v1", False, False),
    ("https://fixture.test/v1", True, True),
    ("https://api.openai.com.evil.test/v1", False, False),
])
def test_stream_usage_only_frame_and_capability_opt_in(base_url, enabled, requested):
    def handler(request):
        payload = json.loads(request.content)
        assert (payload.get("stream_options") == {"include_usage": True}) is requested
        frames = [
            {"choices": [{"index": 0, "delta": {"content": "答案"}}]},
            {"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 10, "prompt_tokens_details": {"cached_tokens": 80}}},
        ]
        frames.append(frames[-1])
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                             text="".join(f"data: {json.dumps(f)}\n\n" for f in frames) + "data: [DONE]\n\n")
    provider = OpenAICompatibleChatProvider(httpx.MockTransport(handler))
    with capture_usage() as usage:
        assert list(provider.chat_completion_stream(OpenAICompatibleConfig(base_url, "synthetic", "fixture", include_stream_usage=enabled), [], 2)) == ["答案"]
    assert usage["input_tokens"] == 100
    assert usage["cache_read_tokens"] == 80


def test_interleaved_streams_and_close_do_not_leak_usage_context():
    audit = FakeAudit()
    runtime = ModelExecutionRuntime(make_settings(), state=FakeState(), audit=audit)
    def factory(count):
        report_usage({"prompt_tokens": count})
        yield "first"
        report_usage({"prompt_tokens": count, "completion_tokens": 7})
        yield "last"
    def stream(count):
        return runtime.execute_stream(user_id=7, provider_source="user", model_config_id=3, model_name="fixture", call=lambda: factory(count), timeout_seconds=2)
    with model_execution_scope(ModelExecutionContext(session_id=9)):
        left, right = stream(100), stream(200)
    assert next(left) == next(right) == "first"
    report_usage({"prompt_tokens": 999})
    left.close()
    assert list(right) == ["last"]
    assert audit.records[0]["status"] == "cancelled"
    assert audit.records[0]["context"].session_id == 9
    assert audit.records[0]["context"].usage_attempts[0]["input_tokens"] == 100
    assert audit.records[1]["context"].usage_attempts[0]["input_tokens"] == 200


def test_stream_failure_without_usage_stays_unknown():
    audit = FakeAudit()
    runtime = ModelExecutionRuntime(make_settings(), state=FakeState(), audit=audit)
    def factory():
        yield "partial"
        raise ModelProviderError("private", code="stream_interrupted")
    stream = runtime.execute_stream(user_id=7, provider_source="user", model_config_id=3, model_name="fixture", call=factory, timeout_seconds=2)
    assert next(stream) == "partial"
    with pytest.raises(ModelProviderError):
        next(stream)
    assert audit.records[0]["context"].usage_attempts[0]["input_tokens"] is None


@pytest.mark.parametrize("reported", [True, False])
def test_home_answer_exhausts_stream_without_emitting_trailing_text(monkeypatch, reported):
    from backend.app.services.tutor_home_graph import HomeTutorGraphRunner

    def handler(request):
        frames = [
            {"choices": [{"delta": {"content": part}}]}
            for part in ["<final_answer>答案</final_", "answer>隐藏尾文", "更多隐藏尾文"]
        ]
        if reported:
            frames.append({"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 12}})
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              text="".join(f"data: {json.dumps(f)}\n\n" for f in frames) + "data: [DONE]\n\n")

    provider = OpenAICompatibleChatProvider(httpx.MockTransport(handler))
    audit, state, emitted = FakeAudit(), FakeState(), []
    runtime = ModelExecutionRuntime(make_settings(), state=state, audit=audit)
    tokens = runtime.execute_stream(user_id=7, provider_source="user", model_config_id=3,
        model_name="fixture", timeout_seconds=2,
        call=lambda: provider.chat_completion_stream(
            OpenAICompatibleConfig("https://fixture.test/v1", "synthetic", "fixture", include_stream_usage=True), [], 2))
    runner = object.__new__(HomeTutorGraphRunner)
    monkeypatch.setattr(runner, "_write", lambda _state, event, data: emitted.append((event, data)))
    assert runner._consume_stream_tokens({}, tokens) == "答案"
    assert "".join(data["content"] for event, data in emitted) == "答案"
    assert len(audit.records) == 1
    assert audit.records[0]["status"] == "completed"
    usage = summarize_attempts(audit.records[0]["context"].usage_attempts)
    assert usage["input_tokens"] == (100 if reported else None)
    assert usage["output_tokens"] == (12 if reported else None)
    assert state.released == ["lease"]


@pytest.mark.parametrize("cancel", [True, False])
def test_home_stream_tail_cancellation_or_failure_is_not_success(monkeypatch, cancel):
    from backend.app.services.ai_job_contracts import AiJobCancelled
    from backend.app.services.tutor_home_graph import HomeTutorGraphRunner

    cancelled = False
    closed = []
    audit, state = FakeAudit(), FakeState()
    runtime = ModelExecutionRuntime(make_settings(), state=state, audit=audit)

    def check():
        if cancelled:
            raise AiJobCancelled()

    def factory():
        nonlocal cancelled
        try:
            cancelled = cancel
            yield "<final_answer>答案</final_answer>"
            raise ModelProviderError("tail interrupted", code="stream_interrupted")
        finally:
            closed.append(True)

    with model_execution_scope(ModelExecutionContext(cancel_check=check)):
        tokens = runtime.execute_stream(user_id=7, provider_source="user", model_config_id=3,
            model_name="fixture", call=factory, timeout_seconds=2)
    runner = object.__new__(HomeTutorGraphRunner)
    monkeypatch.setattr(runner, "_write", lambda *_: None)
    with pytest.raises(AiJobCancelled if cancel else ModelProviderError):
        runner._consume_stream_tokens({}, tokens)
    assert len(audit.records) == 1
    assert audit.records[0]["status"] == ("cancelled" if cancel else "failed")
    assert state.released == ["lease"]
    assert closed == [True]


def test_explicit_price_only_and_no_reasoning_double_count():
    summary = summarize_attempts([normalize_usage({"prompt_tokens": 100, "completion_tokens": 20,
        "prompt_tokens_details": {"cached_tokens": 60, "cache_write_tokens": 10},
        "completion_tokens_details": {"reasoning_tokens": 15}})])
    rates = {"currency": "CNY", "uncached_input_tokens": "2", "cache_read_tokens": "0.2",
             "cache_write_tokens": "3", "output_tokens": "8"}
    assert estimate_cost(summary, rates)["estimated_cost"] == "0.000262"
    assert estimate_cost(summary, None)["estimated_cost"] is None
    assert estimate_cost(summary, {**rates, "cache_read_tokens": "NaN"})["cost_status"] == "pricing_invalid"
    assert estimate_cost(summarize_attempts([normalize_usage(None)]), rates)["cost_status"] == "usage_incomplete"


def test_trace_usage_is_owned_and_preserves_unknown_legacy_rows():
    from backend.app.models import ModelCallRun
    from backend.app.services.agents import AgentTraceService
    from backend.tests.test_agent_traces import FakeAgentTraceRepository, make_log, make_user
    known = summarize_attempts([normalize_usage({"prompt_tokens": 100, "prompt_cache_hit_tokens": 80})])
    repo = FakeAgentTraceRepository(logs=[make_log(1, 1, "trace", "persist", 1)], model_calls=[
        ModelCallRun(user_id=1, trace_id="trace", usage_json=known, status="completed", attempt_count=1),
        ModelCallRun(user_id=1, trace_id="trace", usage_json=None, status="completed", attempt_count=1),
        ModelCallRun(user_id=2, trace_id="trace", usage_json=known, status="completed", attempt_count=1),
        ModelCallRun(user_id=1, trace_id="trace", usage_json=summarize_attempts([]), status="failed", attempt_count=1),
    ])
    summary = AgentTraceService(repo).get_trace(make_user(1), "trace").summary
    assert len(summary["model_calls"]) == 3
    assert summary["model_usage"]["observed_attempt_count"] == 2
    assert summary["model_usage"]["input_tokens"] is None
    assert summary["model_usage"]["known_input_tokens"] == 100
