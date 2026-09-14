from copy import deepcopy

import pytest

from backend.app.core.errors import ConflictDomainError, ValidationDomainError
from backend.app.models import GeneratedResource, LearningTask
from backend.app.schemas.paths import task_to_api
from backend.app.services.task_practice import quiz_questions
from backend.app.services.task_resource_binding import binding_status, resource_snapshot
from backend.tests import test_learning_paths as paths
from backend.tests import test_resource_generation as generation


def bound_pair():
    resource = GeneratedResource(id=8, user_id=1, course_id=3, resource_type="quiz", title="测验", status="completed",
                                 review_status="passed", version_number=1, version_family_id="family", citation_json=[],
                                 content_json={"artifact": {"kind": "quiz", "questions": [{"id": "q1", "type": "single_choice",
                                     "prompt": "选择正确结论", "options": [{"key": "A", "text": "正确"}, {"key": "B", "text": "错误"}],
                                     "answer": "A", "explanation": "依据原文", "citation_refs": [7]}]}})
    item = {"resource_id": 8, "resource_type": "quiz", "binding": resource_snapshot(resource)}
    task = LearningTask(id=9, path_id=2, user_id=1, course_id=3, title="任务", task_type="learn", status="doing",
                        recommended_resource_ids=[8, 10], learning_bundle_json={"binding_contract": 1, "items": [item]})
    return task, resource, item


@pytest.mark.parametrize(("field", "value", "expected"), [
    ("user_id", 2, "invalid_scope"), ("course_id", 4, "invalid_scope"),
    ("resource_type", "doc", "invalid_scope"), ("status", "draft", "unapproved"),
    ("review_status", "low_evidence", "unapproved"), ("version_number", 2, "version_conflict"),
    ("content_json", {"changed": True}, "version_conflict"), ("citation_json", [{"id": 99}], "version_conflict"),
])
def test_binding_rejects_scope_review_or_version_drift(field, value, expected):
    task, resource, item = bound_pair()
    setattr(resource, field, value)
    assert binding_status(task, item, resource) == expected
    detail = task_to_api(task, {8: resource})
    assert detail.learning_bundle.items[0].resource_id is None
    assert detail.learning_bundle.items[0].binding_status == expected


def test_missing_binding_never_substitutes_same_type_recommendation():
    task, resource, item = bound_pair()
    resource.id = 10
    detail = task_to_api(task, {10: resource})
    assert detail.learning_bundle.ready_count == 0
    assert detail.learning_bundle.items[0].binding_status == "missing"
    assert item["resource_id"] == 8


def test_legacy_links_remain_unverified_without_mutating_history():
    task, resource, item = bound_pair()
    del item["binding"]
    del task.learning_bundle_json["binding_contract"]
    before = deepcopy(task.learning_bundle_json)
    assert binding_status(task, item, resource) == "legacy_unverified"
    assert task_to_api(task, {8: resource}).learning_bundle.items[0].binding_status == "legacy_unverified"
    assert task.learning_bundle_json == before


def test_new_binding_cannot_downgrade_to_legacy_when_snapshot_is_missing():
    task, resource, item = bound_pair()
    del item["binding"]
    assert binding_status(task, item, resource) == "unverified"
    assert task_to_api(task, {8: resource}).learning_bundle.ready_count == 0


def test_quiz_adapter_preserves_ids_options_references_and_existing_grading():
    from backend.app.services.practice import PracticeService
    task, resource, _ = bound_pair()
    questions = quiz_questions(resource, task, {7})
    assert questions[0]["id"] == "q1"
    assert questions[0]["citation_refs"] == ["7"]
    assert questions[0]["correct_answer"] == "正确"
    assert PracticeService(None)._evaluate_answer(questions[0], "A").feedback["score"] == 100
    assert PracticeService(None)._evaluate_answer(questions[0], "B").feedback["score"] == 0


@pytest.mark.parametrize("mutation", ["citation", "duplicate", "answer", "type", "options"])
def test_quiz_adapter_rejects_invalid_source(mutation):
    task, resource, _ = bound_pair()
    question = resource.content_json["artifact"]["questions"][0]
    if mutation == "duplicate":
        resource.content_json["artifact"]["questions"].append(deepcopy(question))
    elif mutation == "citation":
        question["citation_refs"] = [999]
    elif mutation == "answer":
        question["answer"] = "Z"
    elif mutation == "type":
        question["type"] = "unsupported"
    else:
        question["options"] = [{"key": "A", "text": "x"}, {"key": "A", "text": "y"}]
    with pytest.raises(ValidationDomainError):
        quiz_questions(resource, task, {7})


def test_draft_approval_rechecks_resource_snapshot():
    repo = paths.make_repo()
    service = paths.make_path_service(repo)
    draft = service.generate_path(paths.make_user(), 101, draft=True)
    bound_id = next(item["resource_id"] for task in repo.tasks for item in task.learning_bundle_json["items"] if item["resource_id"])
    resource = next(resource for resource in repo.resources if resource.id == bound_id)
    resource.content_json = {"changed": True}
    with pytest.raises(ConflictDomainError):
        service.approve_path(paths.make_user(), int(draft.path.id), None)


def test_resource_generation_cannot_overwrite_existing_task_binding():
    repo = generation.make_repo()
    task = LearningTask(id=61, user_id=1, course_id=101, path_id=71, status="doing", title="任务",
                        learning_bundle_json={"items": [{"resource_type": "doc", "resource_id": 999}]})
    repo.learning_tasks.append(task)
    with pytest.raises(generation.ResourceValidationError, match="不能覆盖"):
        generation.make_service(repo).generate_resources(
            generation.make_user(), course_id=101, resource_types=["doc"], path_task_id=61)
