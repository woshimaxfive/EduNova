"""Collect privacy-safe live performance samples from a disposable EduNova account."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure live release-readiness timings.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--samples", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=240.0)
    return parser.parse_args()


def elapsed_ms(started_at: float) -> float:
    return round((monotonic() - started_at) * 1000, 2)


def api_data(response: requests.Response) -> object:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError("API 响应不包含 data。")
    return payload["data"]


def measure(samples: int, action: Callable[[], None]) -> list[float]:
    values: list[float] = []
    for _ in range(samples):
        started_at = monotonic()
        action()
        values.append(elapsed_ms(started_at))
    return values


def wait_for_first_progress(session: requests.Session, url: str, headers: dict[str, str], timeout_seconds: float) -> float:
    started_at = monotonic()
    with session.get(url, headers=headers, stream=True, timeout=timeout_seconds) as response:
        response.raise_for_status()
        for raw_line in response.iter_lines(decode_unicode=True):
            if raw_line and raw_line.startswith("event: snapshot"):
                return elapsed_ms(started_at)
    raise RuntimeError("AIJob SSE 在超时前没有返回首个进度快照。")


def measure_stream(session: requests.Session, url: str, headers: dict[str, str], payload: dict[str, object], timeout_seconds: float) -> tuple[float, float]:
    started_at = monotonic()
    first_status_ms: float | None = None
    first_token_ms: float | None = None
    with session.post(url, headers=headers, json=payload, stream=True, timeout=timeout_seconds) as response:
        response.raise_for_status()
        current_event = ""
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            if raw_line.startswith("event:"):
                current_event = raw_line.removeprefix("event:").strip()
                if first_status_ms is None and current_event in {"status", "metadata", "token"}:
                    first_status_ms = elapsed_ms(started_at)
                continue
            if raw_line.startswith("data:") and current_event == "token" and first_token_ms is None:
                first_token_ms = elapsed_ms(started_at)
            if current_event in {"done", "error"}:
                break
    if first_status_ms is None or first_token_ms is None:
        raise RuntimeError("Tutor SSE 未同时返回首状态和首 Token，不能作为性能样本。")
    return first_status_ms, first_token_ms


def wait_for_job(session: requests.Session, url: str, headers: dict[str, str], timeout_seconds: float) -> None:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        job = api_data(session.get(url, headers=headers, timeout=20))
        if not isinstance(job, dict):
            raise RuntimeError("AIJob 响应格式异常。")
        if job.get("status") == "completed":
            return
        if job.get("status") in {"failed", "cancelled"}:
            raise RuntimeError(f"AIJob 未完成：{job.get('error_code') or job.get('status')}")
        sleep(0.5)
    raise RuntimeError("AIJob 超时。")


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    account = f"perf_{uuid4().hex[:12]}"
    password = f"Perf-{uuid4().hex[:16]}"
    client = requests.Session()

    register = api_data(
        client.post(
            f"{base_url}/api/v1/auth/register",
            json={"account": account, "password": password, "display_name": "性能验收", "starter_mode": "data_structures"},
            timeout=30,
        )
    )
    if not isinstance(register, dict) or not isinstance(register.get("id"), int):
        raise RuntimeError("一次性账号创建失败。")
    user_id = int(register["id"])
    login = api_data(client.post(f"{base_url}/api/v1/auth/login", json={"account": account, "password": password}, timeout=30))
    if not isinstance(login, dict) or not isinstance(login.get("access_token"), str):
        raise RuntimeError("一次性账号登录失败。")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    courses = api_data(client.get(f"{base_url}/api/v1/courses", headers=headers, timeout=30))
    course_items = courses.get("data", []) if isinstance(courses, dict) else courses
    if not isinstance(course_items, list) or not course_items:
        raise RuntimeError("示例课程不可用。")
    course_id = int(course_items[0]["id"])
    points = api_data(client.get(f"{base_url}/api/v1/courses/{course_id}/knowledge-points", headers=headers, timeout=30))
    if not isinstance(points, list) or not points:
        raise RuntimeError("示例课程知识点不可用。")
    knowledge_point_id = int(points[0]["id"])

    measurements: dict[str, list[float]] = {}
    measurements["non_ai_api_p95"] = measure(
        args.samples,
        lambda: api_data(client.get(f"{base_url}/api/v1/courses/{course_id}/overview", headers=headers, timeout=30)),
    )
    measurements["rag_retrieval_p95"] = measure(
        args.samples,
        lambda: api_data(
            client.post(
                f"{base_url}/api/v1/rag/search",
                headers=headers,
                json={"course_id": course_id, "query": "二叉树遍历的基本顺序是什么？", "top_k": 3},
                timeout=args.timeout_seconds,
            )
        ),
    )

    tutor_session = api_data(
        client.post(
            f"{base_url}/api/v1/tutor/sessions",
            headers=headers,
            json={"scope": "course", "course_id": course_id, "mode": "chat", "title": "性能取证会话"},
            timeout=30,
        )
    )
    if not isinstance(tutor_session, dict):
        raise RuntimeError("课程会话创建失败。")
    tutor_session_id = int(tutor_session["id"])
    status_samples: list[float] = []
    token_samples: list[float] = []
    for _ in range(args.samples):
        first_status_ms, first_token_ms = measure_stream(
            client,
            f"{base_url}/api/v1/tutor/sessions/{tutor_session_id}/messages/stream",
            headers,
            {"message": "请用一句话说明二叉树的前序遍历。", "use_web_search": False, "deep_thinking": False},
            args.timeout_seconds,
        )
        status_samples.append(first_status_ms)
        token_samples.append(first_token_ms)
    measurements["sse_first_status"] = status_samples
    measurements["model_first_token"] = token_samples

    job_create_samples: list[float] = []
    job_progress_samples: list[float] = []
    resource_batch_samples: list[float] = []
    for index in range(args.samples):
        started_at = monotonic()
        job = api_data(
            client.post(
                f"{base_url}/api/v1/resources/generation-jobs",
                headers={**headers, "Idempotency-Key": f"perf-resource-{uuid4().hex}"},
                json={
                    "course_id": course_id,
                    "knowledge_point_id": knowledge_point_id,
                    "resource_types": ["doc", "mindmap", "quiz"],
                    "learning_goal": "理解基础概念",
                    "difficulty": "easy",
                    "generation_action": "new",
                },
                timeout=30,
            )
        )
        job_create_samples.append(elapsed_ms(started_at))
        if not isinstance(job, dict):
            raise RuntimeError("资源 AIJob 创建失败。")
        job_id = int(job["job_id"])
        job_progress_samples.append(
            wait_for_first_progress(client, f"{base_url}/api/v1/ai-jobs/{job_id}/events", headers, args.timeout_seconds)
        )
        wait_for_job(client, f"{base_url}/api/v1/ai-jobs/{job_id}", headers, args.timeout_seconds)
        resource_batch_samples.append(elapsed_ms(started_at))
    measurements["ai_job_create"] = job_create_samples
    measurements["ai_job_progress"] = job_progress_samples
    measurements["resource_batch_3"] = resource_batch_samples

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(measurements, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"account": account, "user_id": user_id, "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
