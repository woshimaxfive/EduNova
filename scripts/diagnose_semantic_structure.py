"""Run a privacy-safe compatibility probe for semantic-routing JSON output.

Execute inside the backend container. The script keeps raw model output in memory only
and emits aggregate validation facts without prompts, completions, credentials, or tokens.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from time import perf_counter
from uuid import uuid4

import requests
from json_repair import repair_json
from pydantic import ValidationError

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.semantic_decision import SemanticDecisionPayload, SemanticDecisionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose semantic-routing structure compatibility.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--samples", type=int, default=10, choices=range(1, 21))
    return parser.parse_args()


def api_data(response: requests.Response) -> object:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError("API 响应不包含 data。")
    return payload["data"]


def _clean_fence(value: str) -> str:
    cleaned = str(value or "").strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        cleaned = cleaned[first_newline + 1 :] if first_newline >= 0 else cleaned.removeprefix("```json").removeprefix("```")
        cleaned = cleaned.removesuffix("```").strip()
    return cleaned


def inspect_structure(value: str) -> dict[str, object]:
    """Mirror parse_json_object while returning only safe structural diagnostics."""
    cleaned = _clean_fence(value)
    if not cleaned:
        return {"json_status": "empty", "schema_valid": False, "errors": []}
    try:
        parsed: object = json.loads(cleaned)
        json_status = "strict_json"
    except (TypeError, ValueError, json.JSONDecodeError):
        try:
            parsed = repair_json(cleaned, return_objects=True, skip_json_loads=True)
            json_status = "locally_repaired"
        except Exception:
            return {"json_status": "invalid_json", "schema_valid": False, "errors": []}
    if not isinstance(parsed, dict):
        return {"json_status": "not_object", "schema_valid": False, "errors": []}
    try:
        SemanticDecisionPayload.model_validate(parsed)
    except ValidationError as exc:
        errors = [
            {
                "path": ".".join(str(part) for part in item.get("loc", ()))[:180],
                "type": str(item.get("type") or "unknown")[:80],
            }
            for item in exc.errors()
        ]
        return {"json_status": json_status, "schema_valid": False, "errors": errors[:12]}
    return {"json_status": json_status, "schema_valid": True, "errors": []}


def invoke(service: SemanticDecisionService, user: User, messages: list[dict[str, str]], task_type: str) -> tuple[str, float]:
    started_at = perf_counter()
    value = service._structured_completion(user, messages, task_type=task_type)
    return value, round((perf_counter() - started_at) * 1000, 2)


def repair_messages(raw: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "修正上一份语义决策的 JSON 结构，只输出一个 JSON 对象，不改变原有语义。"
                "reason_codes、profile_signals、referenced_turn_ids、resource_types 必须是数组；"
                "uses_history、course_related、search_required、answer_requested 必须是布尔值；"
                "字段必须符合原任务要求，不能增加额外字段或输出解释。"
            ),
        },
        {"role": "user", "content": str(raw)[:5000]},
    ]


def main() -> int:
    args = parse_args()
    account = f"semdiag_{uuid4().hex[:12]}"
    password = f"SemDiag-{uuid4().hex[:16]}"
    registered = api_data(
        requests.post(
            f"{args.base_url.rstrip('/')}/api/v1/auth/register",
            json={"account": account, "password": password, "display_name": "结构诊断", "starter_mode": "data_structures"},
            timeout=30,
        )
    )
    if not isinstance(registered, dict) or not isinstance(registered.get("id"), int):
        raise RuntimeError("一次性账号创建失败。")
    user_id = int(registered["id"])

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None:
            raise RuntimeError("一次性账号无法加载。")
        settings = get_settings()
        model_service = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(db),
            settings=settings,
            provider=OpenAICompatibleChatProvider(),
        )
        service = SemanticDecisionService(model_service)
        initial_messages = service._messages(
            question="请用一句话说明二叉树的前序遍历。",
            scope="course",
            course_title="数据结构与算法",
            selected_materials=False,
            conversation_messages=[],
        )
        samples: list[dict[str, object]] = []
        error_counter: Counter[tuple[str, str]] = Counter()
        for _ in range(args.samples):
            raw, initial_ms = invoke(service, user, initial_messages, "semantic_routing")
            initial = inspect_structure(raw)
            for item in initial["errors"]:
                if isinstance(item, dict):
                    error_counter[(str(item.get("path") or ""), str(item.get("type") or ""))] += 1
            sample: dict[str, object] = {"initial": {**initial, "latency_ms": initial_ms}, "repair_called": False}
            if not bool(initial["schema_valid"]):
                repaired_raw, repair_ms = invoke(service, user, repair_messages(raw), "semantic_routing_repair")
                repaired = inspect_structure(repaired_raw)
                for item in repaired["errors"]:
                    if isinstance(item, dict):
                        error_counter[(str(item.get("path") or ""), str(item.get("type") or ""))] += 1
                sample.update({"repair_called": True, "repair": {**repaired, "latency_ms": repair_ms}})
            samples.append(sample)
        output = {
            "schema_version": 1,
            "sample_count": args.samples,
            "initial_schema_pass_count": sum(bool(item["initial"]["schema_valid"]) for item in samples if isinstance(item.get("initial"), dict)),
            "repair_called_count": sum(bool(item["repair_called"]) for item in samples),
            "repair_schema_pass_count": sum(
                bool(item.get("repair", {}).get("schema_valid"))
                for item in samples
                if isinstance(item.get("repair"), dict)
            ),
            "failure_signatures": [
                {"path": path, "type": error_type, "count": count}
                for (path, error_type), count in error_counter.most_common()
            ],
            "samples": samples,
            "privacy": "未输出问题、原始模型回答、资料、密码、令牌或密钥。",
        }
        print(json.dumps({"account": account, "user_id": user_id, "diagnostic": output}, ensure_ascii=False))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
