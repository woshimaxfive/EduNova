from backend.app.services.learner_context import LearnerContextService


def test_personalization_freshness_distinguishes_legacy_stale_and_current() -> None:
    legacy = LearnerContextService.freshness({}, 3)
    stale = LearnerContextService.freshness({"profile_applied_version": 2}, 3)
    current = LearnerContextService.freshness({"profile_applied_version": 3}, 3)

    assert legacy.status == "legacy"
    assert stale.status == "stale"
    assert stale.profile_applied_version == 2
    assert current.status == "current"


def test_mastery_scores_keep_course_evidence_isolated() -> None:
    from backend.app.models import KnowledgePoint, WeaknessReviewItem

    points = [
        KnowledgePoint(id=11, course_id=101, title="A", order_index=0, difficulty="medium"),
        KnowledgePoint(id=12, course_id=101, title="B", order_index=1, difficulty="medium"),
    ]
    weaknesses = [
        WeaknessReviewItem(id=1, user_id=1, course_id=101, knowledge_point_id=11, title="A", source_type="practice", status="confirmed"),
        WeaknessReviewItem(id=2, user_id=1, course_id=202, knowledge_point_id=99, title="其他课程", source_type="practice", status="confirmed"),
    ]

    assert LearnerContextService._mastery_scores(points, weaknesses, []) == [35]


def test_mastery_scores_use_answer_evidence_and_ignore_path_progress() -> None:
    from backend.app.models import KnowledgePoint, PracticeAnswer, WeaknessReviewItem

    points = [KnowledgePoint(id=11, course_id=101, title="反向传播", order_index=0, difficulty="medium")]
    weaknesses = [
        WeaknessReviewItem(
            id=1,
            user_id=1,
            course_id=101,
            knowledge_point_id=11,
            title="反向传播",
            source_type="practice",
            status="confirmed",
        )
    ]
    answers = [
        PracticeAnswer(
            id=1,
            session_id=1,
            user_id=1,
            question_json={"knowledge_point_id": 11},
            answer_text="错误回答",
            feedback_json={"score": 0},
            is_correct=False,
        )
    ]
    assert LearnerContextService._mastery_scores(points, weaknesses, answers) == [0]


def test_all_graph_state_contracts_preserve_learner_context() -> None:
    from backend.app.agents.assessment import AssessmentState
    from backend.app.agents.course_builder import CourseBuilderState
    from backend.app.agents.material_comparison import MaterialComparisonState
    from backend.app.agents.path_planning import PathPlanningState
    from backend.app.agents.reporting import ReportState
    from backend.app.agents.schemas import AgentState

    state_contracts = (
        AgentState,
        CourseBuilderState,
        MaterialComparisonState,
        PathPlanningState,
        AssessmentState,
        ReportState,
    )
    for state_contract in state_contracts:
        assert "learner_context" in state_contract.__annotations__
