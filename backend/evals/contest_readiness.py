from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any

from backend.evals.run import run_offline


DEFAULT_OUTPUT = Path("output/contest-readiness/latest.json")
PERFORMANCE_TARGETS_MS = {
    "non_ai_api_p95": 2_000,
    "rag_retrieval_p95": 3_000,
    "sse_first_status": 2_000,
    "model_first_token": 15_000,
    "ai_job_create": 2_000,
    "ai_job_progress": 3_000,
    "resource_batch_3": 180_000,
}


def percentile_95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return round(ordered[index], 2)


def build_report(measurements: dict[str, list[float]] | None = None) -> dict[str, Any]:
    quality_cases = run_offline()
    citation_checks = [item["checks"]["citations_valid"] for item in quality_cases]
    number_checks = [item["checks"]["deterministic_numbers_unchanged"] for item in quality_cases]
    privacy_checks = [item["checks"]["no_sensitive_echo"] for item in quality_cases]
    quality = {
        "citation_valid_rate": round(sum(citation_checks) / len(citation_checks), 4) if citation_checks else 0,
        "deterministic_number_consistency_rate": round(sum(number_checks) / len(number_checks), 4) if number_checks else 0,
        "sensitive_or_prompt_leak_hits": sum(1 for value in privacy_checks if not value),
        "case_count": len(quality_cases),
        "passed": all(item["passed"] for item in quality_cases),
    }
    supplied = measurements or {}
    performance: dict[str, dict[str, Any]] = {}
    for metric, target_ms in PERFORMANCE_TARGETS_MS.items():
        samples = [float(item) for item in supplied.get(metric, []) if isinstance(item, (int, float)) and item >= 0]
        observed = percentile_95(samples)
        performance[metric] = {
            "target_ms": target_ms,
            "sample_count": len(samples),
            "observed_p95_ms": observed,
            "status": "not_measured" if observed is None else "passed" if observed <= target_ms else "failed",
        }
    performance_complete = all(item["status"] != "not_measured" for item in performance.values())
    performance_passed = performance_complete and all(item["status"] == "passed" for item in performance.values())
    performance_failed = any(item["status"] == "failed" for item in performance.values())
    status = (
        "failed"
        if not quality["passed"] or performance_failed
        else "passed"
        if performance_passed
        else "evidence_gap"
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "quality": quality,
        "performance": performance,
        "performance_evidence_complete": performance_complete,
        "notes": [
            "未提供的真实耗时保持 not_measured，不用离线结果代替外部 Provider 证据。",
            "输出仅包含聚合指标，不保存模型响应原文、密钥或用户资料。",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate privacy-safe EduNova contest readiness evidence.")
    parser.add_argument("--measurements", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-live", action="store_true")
    args = parser.parse_args()
    measurements = None
    if args.measurements:
        measurements = json.loads(args.measurements.read_text(encoding="utf-8"))
        if not isinstance(measurements, dict):
            raise ValueError("measurements 必须是指标名到毫秒样本数组的 JSON 对象。")
    report = build_report(measurements)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output)}, ensure_ascii=False))
    if report["status"] == "failed":
        return 1
    if args.require_live and report["status"] != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
