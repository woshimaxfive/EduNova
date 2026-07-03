from backend.app.models.course import Course, CourseEnrollment, CourseMaterial
from backend.app.models.knowledge import KnowledgeChunk, KnowledgePoint
from backend.app.models.learning import (
    AgentRunLog,
    AssessmentReport,
    ChatMessage,
    ChatSession,
    GeneratedResource,
    LearningPath,
    LearningTask,
    ModelSetting,
    PracticeAnswer,
    PracticeSession,
    ProfileEvent,
    ResourceQualityScore,
    StudentProfile,
    WeaknessReviewItem,
)
from backend.app.models.material import CourseMaterialLink, Material
from backend.app.models.user import User

__all__ = [
    "AgentRunLog",
    "AssessmentReport",
    "ChatMessage",
    "ChatSession",
    "Course",
    "CourseEnrollment",
    "CourseMaterial",
    "CourseMaterialLink",
    "GeneratedResource",
    "KnowledgeChunk",
    "KnowledgePoint",
    "LearningPath",
    "LearningTask",
    "Material",
    "ModelSetting",
    "PracticeAnswer",
    "PracticeSession",
    "ProfileEvent",
    "ResourceQualityScore",
    "StudentProfile",
    "User",
    "WeaknessReviewItem",
]
