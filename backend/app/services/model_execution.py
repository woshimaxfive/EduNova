from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import random
import time
from typing import Any, TypeVar
from uuid import uuid4

from sqlalchemy import delete

from backend.app.core.config import Settings
from backend.app.db.session import SessionLocal
from backend.app.models import ModelCallRun
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.providers.model_usage import capture_usage, estimate_cost, normalize_usage, summarize_attempts


T = TypeVar("T")


@dataclass(frozen=True)
class ModelExecutionContext:
    session_id: int | None = None
    usage_attempts: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None
    workflow: str | None = None
    node_name: str | None = None
    ai_job_id: int | None = None
    purpose: str = "generation"
    cancel_check: Callable[[], None] | None = None
    usage_recorder: Callable[[dict[str, Any]], None] | None = None


_execution_context: ContextVar[ModelExecutionContext] = ContextVar(
    "edunova_model_execution_context",
    default=ModelExecutionContext(),
)


@contextmanager
def model_execution_scope(context: ModelExecutionContext):
    token = _execution_context.set(context)
    try:
        yield
    finally:
        _execution_context.reset(token)


def current_model_execution_context() -> ModelExecutionContext:
    return _execution_context.get()


def execution_context_for_state(
    state: dict[str, Any],
    *,
    workflow: str,
    node_name: str | None = None,
    purpose: str | None = None,
) -> ModelExecutionContext:
    job_context = state.get("job_context")
    cancel_check = getattr(job_context, "check_cancelled", None)
    usage_recorder = getattr(job_context, "record_model_usage", None)
    return ModelExecutionContext(
        session_id=getattr(state.get("session"), "id", None),
        trace_id=str(state.get("trace_id")) if state.get("trace_id") else None,
        workflow=workflow,
        node_name=node_name,
        ai_job_id=int(getattr(job_context, "job_id", 0)) or None,
        purpose=purpose or str(state.get("operation") or state.get("trigger") or "generation"),
        cancel_check=cancel_check if callable(cancel_check) else None,
        usage_recorder=usage_recorder if callable(usage_recorder) else None,
    )


class ModelRuntimeState:
    _disabled_by_url: dict[str, float] = {}
    _acquire_script = """
local now = tonumber(ARGV[1])
local expires = tonumber(ARGV[2])
local member = ARGV[3]
local user_limit = tonumber(ARGV[4])
local global_limit = tonumber(ARGV[5])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
if redis.call('ZCARD', KEYS[1]) >= user_limit or redis.call('ZCARD', KEYS[2]) >= global_limit then
  return 0
end
redis.call('ZADD', KEYS[1], expires, member)
redis.call('ZADD', KEYS[2], expires, member)
redis.call('EXPIRE', KEYS[1], math.ceil((expires - now) / 1000) + 5)
redis.call('EXPIRE', KEYS[2], math.ceil((expires - now) / 1000) + 5)
return 1
"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._disabled_until = 0.0
        try:
            from redis import Redis

            self.redis = Redis.from_url(
                settings.redis_url,
                socket_connect_timeout=0.2,
                socket_timeout=0.5,
                decode_responses=True,
            )
        except Exception:
            self.redis = None

    def acquire(self, user_id: int, lease_seconds: float) -> str | None:
        if not self._available():
            return None
        member = uuid4().hex
        deadline = time.monotonic() + max(0.0, self.settings.model_concurrency_wait_seconds)
        while True:
            now_ms = int(time.time() * 1000)
            expires_ms = now_ms + int(max(5.0, lease_seconds) * 1000)
            try:
                acquired = self.redis.eval(
                    self._acquire_script,
                    2,
                    f"edunova:model:concurrency:user:{user_id}",
                    "edunova:model:concurrency:global",
                    now_ms,
                    expires_ms,
                    member,
                    self.settings.model_max_concurrent_per_user,
                    self.settings.model_max_concurrent_global,
                )
            except Exception:
                self._disable_temporarily()
                return None
            if int(acquired or 0) == 1:
                return member
            if time.monotonic() >= deadline:
                raise ModelProviderError(
                    "当前模型请求较多，请稍后重试。",
                    code="model_busy",
                    retryable=True,
                    retry_after_seconds=1.0,
                )
            time.sleep(0.05)

    def release(self, user_id: int, member: str | None) -> None:
        if not member or not self._available():
            return
        try:
            self.redis.zrem(f"edunova:model:concurrency:user:{user_id}", member)
            self.redis.zrem("edunova:model:concurrency:global", member)
        except Exception:
            self._disable_temporarily()

    def before_call(self, key: str, *, bypass: bool = False) -> None:
        if bypass or not self._available():
            return
        try:
            if self.redis.exists(f"{key}:open"):
                raise ModelProviderError(
                    "模型服务暂时不可用，请稍后重试。",
                    code="circuit_open",
                    retryable=True,
                    retry_after_seconds=float(self.redis.ttl(f"{key}:open") or 1),
                )
            if self.redis.exists(f"{key}:recover"):
                probe = self.redis.set(f"{key}:probe", uuid4().hex, nx=True, ex=30)
                if not probe:
                    raise ModelProviderError(
                        "模型服务正在恢复，请稍后重试。",
                        code="circuit_open",
                        retryable=True,
                        retry_after_seconds=1.0,
                    )
        except ModelProviderError:
            raise
        except Exception:
            self._disable_temporarily()

    def success(self, key: str) -> None:
        if not self._available():
            return
        try:
            self.redis.delete(f"{key}:failures", f"{key}:open", f"{key}:recover", f"{key}:probe")
        except Exception:
            self._disable_temporarily()

    def failure(self, key: str) -> None:
        if not self._available():
            return
        try:
            recovering = bool(self.redis.exists(f"{key}:recover"))
            failure_key = f"{key}:failures"
            count = int(self.redis.incr(failure_key))
            if count == 1:
                self.redis.expire(failure_key, self.settings.model_circuit_window_seconds)
            if recovering or count >= self.settings.model_circuit_failure_threshold:
                self.redis.set(f"{key}:open", "1", ex=self.settings.model_circuit_open_seconds)
                self.redis.set(f"{key}:recover", "1", ex=self.settings.model_circuit_open_seconds + 60)
                self.redis.delete(f"{key}:probe")
        except Exception:
            self._disable_temporarily()

    def allow_daily_cleanup(self) -> bool:
        if not self._available():
            return False
        try:
            day = datetime.now(UTC).date().isoformat()
            return bool(self.redis.set(f"edunova:model:audit-cleanup:{day}", "1", nx=True, ex=172800))
        except Exception:
            self._disable_temporarily()
            return False

    def _available(self) -> bool:
        disabled_until = max(self._disabled_until, self._disabled_by_url.get(self.settings.redis_url, 0.0))
        return self.redis is not None and time.monotonic() >= disabled_until

    def _disable_temporarily(self) -> None:
        self._disabled_until = time.monotonic() + 30.0
        self._disabled_by_url[self.settings.redis_url] = self._disabled_until


class ModelCallAuditRecorder:
    def __init__(self, settings: Settings, state: ModelRuntimeState) -> None:
        self.settings = settings
        self.state = state

    def record(
        self,
        *,
        user_id: int,
        provider_source: str,
        model_config_id: int | None,
        model_name: str,
        operation: str,
        status: str,
        error_category: str | None,
        attempt_count: int,
        latency_ms: int,
        context: ModelExecutionContext,
    ) -> None:
        try:
            usage = summarize_attempts(context.usage_attempts)
            pricing_key = f"{provider_source}:{model_config_id if model_config_id is not None else 'system'}:{model_name}"
            usage.update(estimate_cost(usage, self.settings.model_usage_pricing.get(pricing_key)))
            with SessionLocal() as session:
                session.add(
                    ModelCallRun(
                        user_id=user_id,
                        ai_job_id=context.ai_job_id,
                        model_config_id=model_config_id,
                        trace_id=context.trace_id,
                        workflow=context.workflow,
                        node_name=context.node_name,
                        purpose=context.purpose,
                        operation=operation,
                        provider_source=provider_source,
                        model_name=model_name[:120],
                        session_id=context.session_id,
                        usage_json=usage,
                        status=status,
                        error_category=error_category,
                        attempt_count=attempt_count,
                        retry_count=max(0, attempt_count - 1),
                        latency_ms=max(0, latency_ms),
                        started_at=datetime.now(UTC) - timedelta(milliseconds=max(0, latency_ms)),
                        completed_at=datetime.now(UTC),
                    )
                )
                if self.state.allow_daily_cleanup():
                    cutoff = datetime.now(UTC) - timedelta(days=max(1, self.settings.model_call_log_retention_days))
                    session.execute(delete(ModelCallRun).where(ModelCallRun.completed_at < cutoff))
                session.commit()
        except Exception:
            return


class ModelExecutionRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        state: ModelRuntimeState | None = None,
        audit: ModelCallAuditRecorder | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self.settings = settings
        self.state = state or ModelRuntimeState(settings)
        self.audit = audit or ModelCallAuditRecorder(settings, self.state)
        self.sleeper = sleeper
        self.jitter = jitter

    def execute(
        self,
        *,
        user_id: int,
        provider_source: str,
        model_config_id: int | None,
        model_name: str,
        operation: str,
        call: Callable[[], T],
        timeout_seconds: float,
        max_attempts: int | None = None,
        bypass_circuit: bool = False,
    ) -> T:
        context = replace(current_model_execution_context(), usage_attempts=[])
        attempts_allowed = max(1, max_attempts or self.settings.model_max_attempts)
        circuit_key = self._circuit_key(provider_source, model_config_id, model_name, operation)
        started = time.perf_counter()
        lease: str | None = None
        attempt = 0
        final_error: ModelProviderError | None = None
        try:
            lease = self.state.acquire(user_id, timeout_seconds * attempts_allowed + 10)
            self.state.before_call(circuit_key, bypass=bypass_circuit)
            while attempt < attempts_allowed:
                attempt += 1
                self._check_cancel(context)
                try:
                    with self._observe_attempt(context):
                        result = call()
                    self.state.success(circuit_key)
                    self._audit(user_id, provider_source, model_config_id, model_name, operation, "completed", None, attempt, started, context)
                    return result
                except ModelProviderError as exc:
                    final_error = exc
                    invalid_retry_exhausted = exc.code == "invalid_response" and attempt >= 2
                    if not exc.retryable or invalid_retry_exhausted or attempt >= attempts_allowed:
                        break
                    self._sleep_before_retry(exc, attempt, context)
            assert final_error is not None
            if final_error.retryable:
                self.state.failure(circuit_key)
            self._audit(user_id, provider_source, model_config_id, model_name, operation, "failed", final_error.code, attempt, started, context)
            raise final_error
        except ModelProviderError as exc:
            if final_error is None:
                self._audit(user_id, provider_source, model_config_id, model_name, operation, "failed", exc.code, max(1, attempt), started, context)
            raise
        except Exception as exc:
            cancelled = "cancel" in exc.__class__.__name__.lower()
            self._audit(
                user_id,
                provider_source,
                model_config_id,
                model_name,
                operation,
                "cancelled" if cancelled else "failed",
                "cancelled" if cancelled else "internal_error",
                max(1, attempt),
                started,
                context,
            )
            raise
        finally:
            self.state.release(user_id, lease)

    def execute_stream(
        self,
        *,
        user_id: int,
        provider_source: str,
        model_config_id: int | None,
        model_name: str,
        call: Callable[[], Iterator[str]],
        timeout_seconds: float,
    ) -> Iterator[str]:
        context = replace(current_model_execution_context(), usage_attempts=[])
        operation = "stream"
        attempts_allowed = max(1, self.settings.model_max_attempts)
        circuit_key = self._circuit_key(provider_source, model_config_id, model_name, operation)

        def generate() -> Iterator[str]:
            started = time.perf_counter()
            lease: str | None = None
            attempt = 0
            yielded = False
            final_error: ModelProviderError | None = None
            try:
                lease = self.state.acquire(user_id, timeout_seconds * attempts_allowed + 10)
                self.state.before_call(circuit_key)
                while attempt < attempts_allowed and not yielded:
                    attempt += 1
                    self._check_cancel(context)
                    try:
                        yield_stream = self._observe_stream(context, call)
                        try:
                            for token in yield_stream:
                                yielded = True
                                yield token
                        finally:
                            yield_stream.close()
                        self.state.success(circuit_key)
                        self._audit(user_id, provider_source, model_config_id, model_name, operation, "completed", None, attempt, started, context)
                        return
                    except ModelProviderError as exc:
                        final_error = exc
                        if yielded or not exc.retryable or attempt >= attempts_allowed:
                            break
                        self._sleep_before_retry(exc, attempt, context)
                assert final_error is not None
                if final_error.retryable:
                    self.state.failure(circuit_key)
                self._audit(user_id, provider_source, model_config_id, model_name, operation, "failed", final_error.code, attempt, started, context)
                raise final_error
            except ModelProviderError as exc:
                if final_error is None:
                    self._audit(user_id, provider_source, model_config_id, model_name, operation, "failed", exc.code, max(1, attempt), started, context)
                raise
            except GeneratorExit:
                self._audit(user_id, provider_source, model_config_id, model_name, operation, "cancelled", "cancelled", attempt, started, context)
                raise
            except Exception as exc:
                cancelled = "cancel" in exc.__class__.__name__.lower()
                self._audit(
                    user_id,
                    provider_source,
                    model_config_id,
                    model_name,
                    operation,
                    "cancelled" if cancelled else "failed",
                    "cancelled" if cancelled else "internal_error",
                    max(1, attempt),
                    started,
                    context,
                )
                raise
            finally:
                self.state.release(user_id, lease)

        return generate()

    @staticmethod
    def _observe_stream(context: ModelExecutionContext, call: Callable[[], Iterator[str]]) -> Iterator[str]:
        started = time.perf_counter()
        usage = normalize_usage(None)
        status = "completed"
        first_token_ms = None
        stream = None
        try:
            with capture_usage(usage):
                stream = iter(call())
            while True:
                ModelExecutionRuntime._check_cancel(context)
                # Do not leave a ContextVar set across a consumer yield: streams
                # can be interleaved or resumed in another worker context.
                with capture_usage(usage):
                    try:
                        token = next(stream)
                    except StopIteration:
                        break
                if first_token_ms is None:
                    first_token_ms = max(0, int((time.perf_counter() - started) * 1000))
                yield token
        except BaseException as exc:
            status = "cancelled" if isinstance(exc, GeneratorExit) or "cancel" in type(exc).__name__.lower() else "failed"
            raise
        finally:
            try:
                if stream is not None and hasattr(stream, "close"):
                    with capture_usage(usage):
                        stream.close()
            finally:
                context.usage_attempts.append({
                    **usage, "attempt": len(context.usage_attempts) + 1, "status": status,
                    "first_token_ms": first_token_ms,
                    "latency_ms": max(0, int((time.perf_counter() - started) * 1000)),
                })

    @staticmethod
    @contextmanager
    def _observe_attempt(context: ModelExecutionContext):
        started = time.perf_counter()
        with capture_usage() as usage:
            status = "completed"
            try:
                yield
            except BaseException as exc:
                status = "cancelled" if isinstance(exc, GeneratorExit) or "cancel" in type(exc).__name__.lower() else "failed"
                raise
            finally:
                context.usage_attempts.append({
                    **usage,
                    "attempt": len(context.usage_attempts) + 1,
                    "status": status,
                    "latency_ms": max(0, int((time.perf_counter() - started) * 1000)),
                })

    def _sleep_before_retry(self, error: ModelProviderError, attempt: int, context: ModelExecutionContext) -> None:
        self._check_cancel(context)
        if error.retry_after_seconds is not None:
            delay = min(error.retry_after_seconds, self.settings.model_retry_after_max_seconds)
        else:
            raw = self.settings.model_retry_base_delay_seconds * (3 ** max(0, attempt - 1))
            delay = min(raw, self.settings.model_retry_max_delay_seconds)
            delay += self.jitter(0.0, delay * 0.2)
        self.sleeper(max(0.0, delay))
        self._check_cancel(context)

    @staticmethod
    def _check_cancel(context: ModelExecutionContext) -> None:
        if context.cancel_check is not None:
            context.cancel_check()

    @staticmethod
    def _circuit_key(source: str, config_id: int | None, model_name: str, operation: str) -> str:
        identity = f"{source}:{config_id or 'system'}:{model_name}:{operation}"
        digest = sha256(identity.encode("utf-8")).hexdigest()[:24]
        return f"edunova:model:circuit:{digest}"

    def _audit(
        self,
        user_id: int,
        provider_source: str,
        model_config_id: int | None,
        model_name: str,
        operation: str,
        status: str,
        error_category: str | None,
        attempt_count: int,
        started: float,
        context: ModelExecutionContext,
    ) -> None:
        self.audit.record(
            user_id=user_id,
            provider_source=provider_source,
            model_config_id=model_config_id,
            model_name=model_name,
            operation=operation,
            status=status,
            error_category=error_category,
            attempt_count=attempt_count,
            latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
            context=context,
        )
