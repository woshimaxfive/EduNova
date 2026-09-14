from types import SimpleNamespace as NS

import pytest

from backend.app.services.task_progress import project_task_progress
from backend.app.services.task_resource_binding import resource_snapshot


def fixture():
    resources = {
        i: NS(
            id=i,
            user_id=1,
            course_id=2,
            resource_type=kind,
            status="completed",
            review_status="passed",
            version_number=1,
            version_family_id=f"family-{i}",
            content_json={"text": "课程原文"},
            citation_json=[{"chunk_id": 4}],
        )
        for i, kind in [(10, "doc"), (11, "quiz")]
    }
    items = [
        {
            "resource_type": resource.resource_type,
            "resource_id": resource.id,
            "binding": resource_snapshot(resource),
        }
        for resource in resources.values()
    ]
    task = NS(
        id=3,
        path_id=5,
        user_id=1,
        course_id=2,
        status="completed",
        learning_bundle_json={"binding_contract": 1, "items": items},
    )
    path = NS(approval_status="approved")
    events = [
        NS(
            path_task_id=3,
            resource_id=i,
            event_type="completed",
            event_id=f"event-{i}",
            evidence_json={
                "path_id": 5,
                "task_id": 3,
                "binding_status": "verified",
                "resource": resource_snapshot(r),
            },
        )
        for i, r in resources.items()
    ]
    session = NS(
        id=6,
        status="completed",
        score=100,
        assessment_json={
            "grading_status": "complete",
            "source_binding": {
                "task_id": 3,
                "path_id": 5,
                "resource": resource_snapshot(resources[11]),
            },
        },
    )
    return task, path, resources, events, session


def test_user_marks_and_quiz_activity_do_not_become_assessment_or_mastery():
    task, path, resources, events, _ = fixture()
    result = project_task_progress(task, path, resources, events, [])
    assert result.user_reported_completed
    assert (
        not result.activity_completed
        and not result.assessment_passed
        and not result.mastered
    )
    assert result.completed_activity_count == 1
    assert result.next_step == "take_assessment" and result.next_resource_id == "11"


def test_complete_chain_uses_existing_mastery_and_is_read_only():
    task, path, resources, events, session = fixture()
    task.status = "todo"
    result = project_task_progress(
        task, path, resources, events, [session], NS(status="mastered", score=100)
    )
    assert not result.user_reported_completed
    assert result.activity_completed and result.assessment_passed and result.mastered
    assert (
        result.next_step == "continue_learning"
        and result.assessment_session_ids == ["6"]
    )
    assert task.status == "todo" and session.score == 100
    assert (
        project_task_progress(task, path, resources, events, [session]).mastered
        is False
    )


@pytest.mark.parametrize(
    "damage",
    [
        "version",
        "owner",
        "missing",
        "review",
        "legacy",
        "session_path",
        "session_task",
        "partial",
        "low_score",
        "event_path",
    ],
)
def test_incomplete_or_mismatched_evidence_cannot_close_task(damage):
    task, path, resources, events, session = fixture()
    if damage == "version":
        resources[11].version_number = 2
    elif damage == "owner":
        resources[11].user_id = 9
    elif damage == "missing":
        resources.pop(11)
    elif damage == "review":
        resources[11].review_status = "failed"
    elif damage == "legacy":
        path.approval_status = "legacy"
    elif damage == "session_path":
        session.assessment_json["source_binding"]["path_id"] = 9
    elif damage == "session_task":
        session.assessment_json["source_binding"]["task_id"] = 9
    elif damage == "partial":
        session.assessment_json["grading_status"] = "partial"
    elif damage == "low_score":
        session.score = 60
    elif damage == "event_path":
        events[0].evidence_json["path_id"] = 9
    result = project_task_progress(task, path, resources, events, [session])
    assert result.next_step != "continue_learning"
    assert not (result.activity_completed and result.assessment_passed)


def test_empty_bundle_does_not_complete_vacuously():
    task, path, resources, events, _ = fixture()
    task.learning_bundle_json = {}
    assert (
        project_task_progress(task, path, resources, events, []).next_step
        == "resolve_binding"
    )
