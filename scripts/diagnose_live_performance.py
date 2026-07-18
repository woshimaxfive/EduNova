"""Collect privacy-safe, warm-up-aware latency diagnostics from a disposable account."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from time import monotonic
from uuid import uuid4

import requests


QUESTION = "请用一句话说明二叉树的前序遍历。"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose live RAG and Tutor latency without retaining private content.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--samples", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args()


def elapsed_ms(started_at: float) -> float:
    return round((monotonic() - started_at) * 1000, 2)


def api_data(response: requests.Response) -> object:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError("API 响应不包含 data。")
    return payload["data"]


def summary(values: list[float]) -> dict[str, float | int]:
    return {
        "sample_count": len(values),
        "p50_ms": round(float(median(values)), 2),
        "max_ms": round(max(values), 2),
        "values_ms": values,
    }


def create_course_session(client: requests.Session, base_url: str, headers: dict[str, str], course_id: int) -> int:
    session = api_data(
        client.post(
            f"{base_url}/api/v1/tutor/sessions",
            headers=headers,
            json={"scope": "course", "course_id": course_id, "mode": "chat", "title": "性能诊断会话"},
            timeout=30,
        )
    )
    if not isinstance(session, dict) or not str(session.get("id") or "").isdigit():
        raise RuntimeError("课程会话创建失败。")
    return int(str(session["id"]))


def stream_once(
    client: requests.Session,
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, float | str]:
    started_at = monotonic()
    first_status_ms: float | None = None
    first_token_ms: float | None = None
    trace_id: str | None = None
    current_event = ""
    with client.post(
        url,
        headers=headers,
        json={"message": QUESTION, "use_web_search": False, "deep_thinking": False},
        stream=True,
        timeout=timeout_seconds,
    ) as response:
        response.raise_for_status()
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            if raw_line.startswith("event:"):
                current_event = raw_line.removeprefix("event:").strip()
                if first_status_ms is None and current_event in {"status", "metadata", "token"}:
                    first_status_ms = elapsed_ms(started_at)
                continue
            if not raw_line.startswith("data:"):
                continue
            data = json.loads(raw_line.removeprefix("data:").strip())
            if current_event == "metadata" and isinstance(data, dict) and isinstance(data.get("trace_id"), str):
                trace_id = data["trace_id"]
            if current_event == "token" and first_token_ms is None:
                first_token_ms = elapsed_ms(started_at)
            if current_event == "error":
                raise RuntimeError("Tutor 流式诊断返回错误。")
            if current_event == "done":
                break
    if first_status_ms is None or first_token_ms is None or trace_id is None:
        raise RuntimeError("Tutor SSE 未返回完整的状态、首内容或追踪标识。")
    return {
        "first_status_ms": first_status_ms,
        "first_visible_content_ms": first_token_ms,
        "end_to_end_ms": elapsed_ms(started_at),
        "trace_id": trace_id,
    }


def trace_durations(client: requests.Session, base_url: str, headers: dict[str, str], trace_id: str) -> dict[str, int]:
    trace = api_data(client.get(f"{base_url}/api/v1/agents/traces/{trace_id}", headers=headers, timeout=30))
    if not isinstance(trace, dict):
        raise RuntimeError("Agent 轨迹响应格式异常。")
    steps = trace.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError("Agent 轨迹缺少步骤。")
    return {
        str(item["agent_name"]): int(item["duration_ms"])
        for item in steps
        if isinstance(item, dict) and isinstance(item.get("agent_name"), str) and isinstance(item.get("duration_ms"), int)
    }


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    account = f"perfdiag_{uuid4().hex[:12]}"
    password = f"PerfDiag-{uuid4().hex[:16]}"
    client = requests.Session()
    registered = api_data(
        client.post(
            f"{base_url}/api/v1/auth/register",
            json={"account": account, "password": password, "display_name": "性能诊断", "starter_mode": "data_structures"},
            timeout=30,
        )
    )
    if not isinstance(registered, dict) or not isinstance(registered.get("id"), int):
        raise RuntimeError("一次性账号创建失败。")
    user_id = int(registered["id"])
    login = api_data(client.post(f"{base_url}/api/v1/auth/login", json={"account": account, "password": password}, timeout=30))
    if not isinstance(login, dict) or not isinstance(login.get("access_token"), str):
        raise RuntimeError("一次性账号登录失败。")
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    courses = api_data(client.get(f"{base_url}/api/v1/courses", headers=headers, timeout=30))
    course_items = courses.get("data", []) if isinstance(courses, dict) else courses
    if not isinstance(course_items, list) or not course_items:
        raise RuntimeError("示例课程不可用。")
    course_id = int(course_items[0]["id"])
    rag_url = f"{base_url}/api/v1/rag/search"
    rag_payload = {"course_id": course_id, "query": QUESTION, "top_k": 3}

    # Warm-up is deliberately excluded from the reported samples.
    api_data(client.post(rag_url, headers=headers, json=rag_payload, timeout=args.timeout_seconds))
    warmup_session = create_course_session(client, base_url, headers, course_id)
    stream_once(client, f"{base_url}/api/v1/tutor/sessions/{warmup_session}/messages/stream", headers, args.timeout_seconds)

    rag_values: list[float] = []
    tutor_samples: list[dict[str, object]] = []
    for _ in range(args.samples):
        started_at = monotonic()
        api_data(client.post(rag_url, headers=headers, json=rag_payload, timeout=args.timeout_seconds))
        rag_values.append(elapsed_ms(started_at))

        session_id = create_course_session(client, base_url, headers, course_id)
        sample = stream_once(client, f"{base_url}/api/v1/tutor/sessions/{session_id}/messages/stream", headers, args.timeout_seconds)
        durations = trace_durations(client, base_url, headers, str(sample["trace_id"]))
        tutor_samples.append(
            {
                "first_status_ms": sample["first_status_ms"],
                "first_visible_content_ms": sample["first_visible_content_ms"],
                "end_to_end_ms": sample["end_to_end_ms"],
                "trace_step_ms": durations,
            }
        )

    result = {
        "schema_version": 1,
        "sample_count": args.samples,
        "warmup_excluded": True,
        "rag_end_to_end": summary(rag_values),
        "tutor_fresh_session": {
            "first_status": summary([float(item["first_status_ms"]) for item in tutor_samples]),
            "first_visible_content": summary([float(item["first_visible_content_ms"]) for item in tutor_samples]),
            "end_to_end": summary([float(item["end_to_end_ms"]) for item in tutor_samples]),
            "samples": tutor_samples,
        },
        "notes": [
            "不保存问题、模型回答、资料内容、密码、令牌或密钥。",
            "RAG 的外部调用分段由同一一次性用户的 model_call_runs 在清理前单独汇总。",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"account": account, "user_id": user_id, "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
