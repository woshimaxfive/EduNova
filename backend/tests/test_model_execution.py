from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.providers.openai_compatible import (
    ModelProviderError,
    OpenAICompatibleChatProvider,
    OpenAICompatibleConfig,
)
from backend.app.services.model_execution import (
    ModelExecutionContext,
    ModelExecutionRuntime,
    ModelRuntimeState,
    model_execution_scope,
)


@dataclass
class FakeState:
    before_calls: list[tuple[str, bool]] = field(default_factory=list)
    failures: int = 0
    successes: int = 0
    released: list[str | None] = field(default_factory=list)
    busy_error: ModelProviderError | None = None

    def acquire(self, _user_id: int, _lease_seconds: float) -> str | None:
        if self.busy_error is not None:
            raise self.busy_error
        return "lease"

    def release(self, _user_id: int, member: str | None) -> None:
        self.released.append(member)

    def before_call(self, key: str, *, bypass: bool = False) -> None:
        self.before_calls.append((key, bypass))

    def success(self, _key: str) -> None:
        self.successes += 1

    def failure(self, _key: str) -> None:
        self.failures += 1

    def allow_daily_cleanup(self) -> bool:
        return False


@dataclass
class FakeAudit:
    records: list[dict[str, Any]] = field(default_factory=list)

    def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)


def make_settings(**overrides: Any) -> Settings:
    values = {
        "model_max_attempts": 3,
        "model_retry_base_delay_seconds": 0.5,
        "model_retry_max_delay_seconds": 2.0,
        "model_retry_after_max_seconds": 3.0,
    }
    values.update(overrides)
    return Settings(**values)


def run(runtime: ModelExecutionRuntime, call, *, operation: str = "chat"):
    return runtime.execute(
        user_id=7,
        provider_source="user",
        model_config_id=3,
        model_name="test-model",
        operation=operation,
        call=call,
        timeout_seconds=2,
    )


def test_runtime_retries_transient_error_on_same_call_and_audits_once() -> None:
    state = FakeState()
    audit = FakeAudit()
    sleeps: list[float] = []
    attempts = 0

    def call() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ModelProviderError("busy", code="rate_limited", retryable=True)
        return "ok"

    runtime = ModelExecutionRuntime(
        make_settings(),
        state=state,
        audit=audit,
        sleeper=sleeps.append,
        jitter=lambda _start, _end: 0,
    )
    with model_execution_scope(ModelExecutionContext(trace_id="trace-1", workflow="home_tutor")):
        assert run(runtime, call) == "ok"

    assert attempts == 3
    assert sleeps == [0.5, 1.5]
    assert state.successes == 1
    assert state.failures == 0
    assert audit.records[0]["attempt_count"] == 3
    assert audit.records[0]["context"].trace_id == "trace-1"


def test_runtime_does_not_retry_authentication_or_switch_provider() -> None:
    state = FakeState()
    audit = FakeAudit()
    attempts = 0

    def call() -> str:
        nonlocal attempts
        attempts += 1
        raise ModelProviderError("auth", code="authentication_failed")

    runtime = ModelExecutionRuntime(make_settings(), state=state, audit=audit, sleeper=lambda _delay: None)
    with pytest.raises(ModelProviderError) as raised:
        run(runtime, call)

    assert raised.value.code == "authentication_failed"
    assert attempts == 1
    assert audit.records[0]["provider_source"] == "user"


def test_runtime_audits_model_busy_without_invoking_provider() -> None:
    state = FakeState(busy_error=ModelProviderError("busy", code="model_busy", retryable=True))
    audit = FakeAudit()
    runtime = ModelExecutionRuntime(make_settings(), state=state, audit=audit)
    called = False

    def call() -> str:
        nonlocal called
        called = True
        return "unexpected"

    with model_execution_scope(ModelExecutionContext(trace_id="trace-busy", workflow="course_tutor")):
        with pytest.raises(ModelProviderError):
            run(runtime, call)
    assert called is False
    assert audit.records[0]["error_category"] == "model_busy"


def test_runtime_retries_invalid_response_only_once() -> None:
    attempts = 0
    audit = FakeAudit()

    def call() -> str:
        nonlocal attempts
        attempts += 1
        raise ModelProviderError("invalid", code="invalid_response", retryable=True)

    runtime = ModelExecutionRuntime(
        make_settings(),
        state=FakeState(),
        audit=audit,
        sleeper=lambda _delay: None,
        jitter=lambda _start, _end: 0,
    )
    with pytest.raises(ModelProviderError):
        run(runtime, call)
    assert attempts == 2
    assert audit.records[0]["attempt_count"] == 2


def test_stream_retries_before_first_token_but_never_replays_after_output() -> None:
    attempts = 0
    audit = FakeAudit()

    def stream_factory() -> Iterator[str]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ModelProviderError("timeout", code="timeout", retryable=True)
        yield "第一段"
        raise ModelProviderError("interrupted", code="stream_interrupted", retryable=False)

    runtime = ModelExecutionRuntime(
        make_settings(),
        state=FakeState(),
        audit=audit,
        sleeper=lambda _delay: None,
        jitter=lambda _start, _end: 0,
    )
    stream = runtime.execute_stream(
        user_id=7,
        provider_source="user",
        model_config_id=3,
        model_name="test-model",
        call=stream_factory,
        timeout_seconds=2,
    )
    assert next(stream) == "第一段"
    with pytest.raises(ModelProviderError) as raised:
        next(stream)
    assert raised.value.code == "stream_interrupted"
    assert attempts == 2
    assert audit.records[0]["attempt_count"] == 2


def test_runtime_checks_cancellation_before_call_and_records_cancelled() -> None:
    audit = FakeAudit()

    class Cancelled(RuntimeError):
        pass

    runtime = ModelExecutionRuntime(make_settings(), state=FakeState(), audit=audit)
    with model_execution_scope(ModelExecutionContext(trace_id="trace-cancel", cancel_check=lambda: (_ for _ in ()).throw(Cancelled()))):
        with pytest.raises(Cancelled):
            run(runtime, lambda: "never")
    assert audit.records[0]["status"] == "cancelled"
    assert audit.records[0]["error_category"] == "cancelled"


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.eval_result = 1

    def eval(self, *_args: Any) -> int:
        return self.eval_result

    def zrem(self, *_args: Any) -> None:
        return None

    def exists(self, key: str) -> bool:
        return key in self.values

    def set(self, key: str, value: Any, *, nx: bool = False, ex: int | None = None) -> bool:
        del ex
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def incr(self, key: str) -> int:
        self.values[key] = int(self.values.get(key, 0)) + 1
        return int(self.values[key])

    def expire(self, _key: str, _seconds: int) -> None:
        return None

    def delete(self, *keys: str) -> None:
        for key in keys:
            self.values.pop(key, None)

    def ttl(self, _key: str) -> int:
        return 30


def test_redis_state_enforces_busy_limit_and_circuit_half_open_probe() -> None:
    settings = make_settings(model_concurrency_wait_seconds=0, model_circuit_failure_threshold=2)
    state = ModelRuntimeState(settings)
    fake = FakeRedis()
    state.redis = fake
    state._disabled_until = 0
    state._disabled_by_url.pop(settings.redis_url, None)

    fake.eval_result = 0
    with pytest.raises(ModelProviderError) as busy:
        state.acquire(7, 10)
    assert busy.value.code == "model_busy"

    key = "edunova:model:circuit:test"
    state.failure(key)
    state.failure(key)
    with pytest.raises(ModelProviderError) as opened:
        state.before_call(key)
    assert opened.value.code == "circuit_open"

    fake.delete(f"{key}:open")
    state.before_call(key)
    with pytest.raises(ModelProviderError):
        state.before_call(key)
    state.success(key)
    state.before_call(key)


@pytest.mark.parametrize(
    ("status", "payload", "expected_code", "retryable"),
    [
        (401, {"error": {"message": "bad key"}}, "authentication_failed", False),
        (429, {"error": {"message": "rate"}}, "rate_limited", True),
        (500, {"error": {"message": "down"}}, "provider_unavailable", True),
        (400, {"error": {"code": "context_length_exceeded"}}, "context_too_long", False),
        (422, {"error": {"message": "bad"}}, "invalid_request", False),
    ],
)
def test_provider_classifies_http_failures(status: int, payload: dict, expected_code: str, retryable: bool) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        headers = {"Retry-After": "9"} if status == 429 else {}
        return httpx.Response(status, json=payload, headers=headers)

    provider = OpenAICompatibleChatProvider(transport=httpx.MockTransport(handler))
    with pytest.raises(ModelProviderError) as raised:
        provider.chat_completion(
            OpenAICompatibleConfig("https://model.example/v1", "key", "model"),
            [{"role": "user", "content": "hello"}],
            2,
        )
    assert raised.value.code == expected_code
    assert raised.value.retryable is retryable
    if status == 429:
        assert raised.value.retry_after_seconds == 9


def test_model_call_migration_is_privacy_safe() -> None:
    migration = Path(__file__).parents[1] / "migrations" / "versions" / "20260711_0015_create_model_call_runs.py"
    text = migration.read_text(encoding="utf-8")
    assert 'revision = "20260711_0015"' in text
    assert 'down_revision = "20260711_0014"' in text
    assert "prompt" not in text.lower()
    assert "response_body" not in text
    assert "api_key" not in text
