"""Domain binding rules; resource IDs identify versions, never a latest-version alias."""
from __future__ import annotations

import hashlib
import json

from backend.app.models import GeneratedResource, LearningTask


def resource_snapshot(resource: GeneratedResource) -> dict:
    payload = {"content": resource.content_json or {}, "citations": resource.citation_json or []}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"resource_id": resource.id, "version_number": resource.version_number,
            "version_family_id": resource.version_family_id, "sha256": digest}


def binding_status(task: LearningTask, item: dict, resource: GeneratedResource | None) -> str:
    if resource is None:
        return "missing" if item.get("resource_id") else "unbound"
    if (resource.user_id != task.user_id or resource.course_id != task.course_id
            or resource.resource_type != item.get("resource_type")):
        return "invalid_scope"
    if resource.status != "completed" or resource.review_status != "passed":
        return "unapproved"
    snapshot = item.get("binding")
    if not isinstance(snapshot, dict):
        return "unverified" if (task.learning_bundle_json or {}).get("binding_contract") else "legacy_unverified"
    return "verified" if snapshot == resource_snapshot(resource) else "version_conflict"


def exact_item(task: LearningTask, resource_id: int) -> dict | None:
    return next((item for item in (task.learning_bundle_json or {}).get("items", [])
                 if isinstance(item, dict) and str(item.get("resource_id")) == str(resource_id)), None)
