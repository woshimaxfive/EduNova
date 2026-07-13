from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ARTIFACT_KINDS = {
    "doc": "document",
    "mindmap": "mindmap",
    "quiz": "quiz",
    "code": "code_lab",
    "slide": "slide_deck",
    "animation": "animation",
}

FORBIDDEN_CODE_MARKERS = (
    "from js import",
    "import js",
    "import pyodide",
    "import micropip",
    "__import__",
    "eval(",
    "exec(",
    "compile(",
    "open(",
)


@dataclass(frozen=True)
class ArtifactBuildInput:
    resource_type: str
    topic: str
    course_title: str
    difficulty: str
    citation_lines: list[str]
    excerpt_lines: list[str]
    weak_points: str
    profile_goal: str
    foundation: str
    learning_preference: str
    citation_refs: list[int]


def build_resource_content(source: ArtifactBuildInput) -> dict[str, Any]:
    artifact = _artifact_builders()[source.resource_type](source)
    markdown = artifact_to_markdown(source.resource_type, artifact, source)
    return {
        "schema_version": 3,
        "format": "rich",
        "topic": source.topic,
        "course_title": source.course_title,
        "summary": _summary(source),
        "learning_objectives": _learning_objectives(source),
        "markdown": markdown,
        "artifact": artifact,
        "citation_summaries": list(source.citation_lines),
        "metadata": {"learning_preference": source.learning_preference},
    }


def validate_resource_content(resource_type: str, content: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    if content.get("schema_version") not in {2, 3} or content.get("format") != "rich":
        risks.append("invalid_schema")
    artifact = content.get("artifact")
    if not isinstance(artifact, dict) or artifact.get("kind") != ARTIFACT_KINDS.get(resource_type):
        return [*risks, "invalid_artifact_kind"]
    markdown = content.get("markdown")
    if not isinstance(markdown, str) or len(markdown.strip()) < 40:
        risks.append("incomplete_markdown")

    validators = {
        "doc": _validate_document,
        "mindmap": _validate_mindmap,
        "quiz": _validate_quiz,
        "code": _validate_code,
        "slide": _validate_slides,
        "animation": _validate_animation,
    }
    risks.extend(validators.get(resource_type, lambda _artifact: ["unsupported_resource_type"])(artifact))
    return list(dict.fromkeys(risks))


def artifact_to_markdown(resource_type: str, artifact: dict[str, Any], source: ArtifactBuildInput) -> str:
    if resource_type == "doc":
        lines = [f"# {source.topic}个性化讲解", f"课程：{source.course_title}", f"难度：{source.difficulty}", ""]
        for section in artifact["sections"]:
            lines.extend([f"## {section['heading']}", section["body"], ""])
        lines.extend(["## 引用依据", *source.citation_lines])
        return "\n".join(lines).strip()

    if resource_type == "mindmap":
        return "\n".join([f"# {source.topic}思维导图", "", artifact["markmap_markdown"]]).strip()

    if resource_type == "quiz":
        lines = [f"# {source.topic}练习题", f"难度：{source.difficulty}"]
        for index, question in enumerate(artifact["questions"], start=1):
            type_label = {
                "single_choice": "单选题",
                "multiple_choice": "多选题",
                "short_answer": "简答题",
            }.get(question["type"], "练习题")
            lines.extend(["", f"## {type_label}", f"{index}. {question['prompt']}"])
            for option in question.get("options", []):
                lines.append(f"- {option['key']}. {option['text']}")
            answer = question["answer"]
            answer_text = "、".join(answer) if isinstance(answer, list) else str(answer)
            lines.extend([f"答案：{answer_text}", f"解析：{question['explanation']}"])
        return "\n".join(lines)

    if resource_type == "code":
        entry_file = artifact["entry_file"]
        file_content = next(item["content"] for item in artifact["files"] if item["path"] == entry_file)
        return "\n".join(
            [
                f"# {source.topic}代码实操",
                f"难度：{source.difficulty}",
                "",
                "## 可运行示例",
                "```python",
                file_content,
                "```",
                "",
                "## 运行说明",
                *[f"- {item}" for item in artifact["instructions"]],
                "",
                "## 改造任务",
                *[f"- {item}" for item in artifact["tasks"]],
            ]
        )

    if resource_type == "slide":
        lines = [f"# {source.topic}PPT"]
        for index, slide in enumerate(artifact["slides"], start=1):
            lines.extend(
                [
                    "",
                    f"## 第 {index} 页：{slide['title']}",
                    *[f"- 要点：{bullet}" for bullet in slide["bullets"]],
                    f"讲稿：{slide['speaker_notes']}",
                ]
            )
        return "\n".join(lines)

    lines = [f"# {source.topic}动画图解"]
    for index, scene in enumerate(artifact["scenes"], start=1):
        lines.extend(
            [
                "",
                f"## 场景 {index}：{scene['title']}",
                scene["narration"],
                "```mermaid",
                scene["diagram"],
                "```",
            ]
        )
    return "\n".join(lines)


def _artifact_builders():
    return {
        "doc": _build_document,
        "mindmap": _build_mindmap,
        "quiz": _build_quiz,
        "code": _build_code,
        "slide": _build_slides,
        "animation": _build_animation,
    }


def _summary(source: ArtifactBuildInput) -> str:
    return f"围绕 {source.topic}，结合课程依据和当前学习目标生成的{ARTIFACT_KINDS[source.resource_type]}资源。"


def _learning_objectives(source: ArtifactBuildInput) -> list[str]:
    return [
        f"能用自己的话解释 {source.topic} 的核心概念",
        f"能依据课程资料判断 {source.topic} 的关键步骤",
        f"能针对当前薄弱点完成一次 {source.difficulty} 难度练习",
    ]


def _citation_ref(source: ArtifactBuildInput) -> list[int]:
    return list(source.citation_refs[:5])


def _evidence_concepts(source: ArtifactBuildInput, *, limit: int = 3) -> list[str]:
    concepts: list[str] = []
    for line in source.excerpt_lines:
        cleaned = line.removeprefix("- ").strip()
        if not cleaned:
            continue
        compact = cleaned if len(cleaned) <= 110 else f"{cleaned[:107]}..."
        if compact not in concepts:
            concepts.append(compact)
        if len(concepts) >= limit:
            break
    return concepts


def _build_document(source: ArtifactBuildInput) -> dict[str, Any]:
    evidence_concepts = _evidence_concepts(source)
    evidence = "；".join(evidence_concepts)
    lead_concept = evidence_concepts[0] if evidence_concepts else source.topic
    return {
        "kind": "document",
        "sections": [
            {
                "heading": "概念解释",
                "body": f"围绕 {source.topic}，先抓住课程中的真实结论：{lead_concept}。再区分它的输入、条件、过程和输出。",
            },
            {"heading": "课程依据", "body": evidence},
            {
                "heading": "关键步骤",
                "body": f"先识别 {source.topic} 的条件，再拆解处理步骤，最后通过例题或反例验证结论。",
            },
            {
                "heading": "易错点",
                "body": f"不要只背结论而忽略适用条件。当前画像提示需要重点关注：{source.weak_points}。",
            },
            {
                "heading": "复习建议",
                "body": (
                    f"当前基础：{source.foundation}。学习目标：{source.profile_goal}。"
                    f"偏好方式：{source.learning_preference or '综合学习'}。完成复述、做题、标记卡点三个动作。"
                ),
            },
        ],
        "citation_refs": _citation_ref(source),
    }


def _build_mindmap(source: ArtifactBuildInput) -> dict[str, Any]:
    evidence_concepts = _evidence_concepts(source)
    evidence_titles = [line.removeprefix("- ").split("（", 1)[0] for line in source.citation_lines[:3]] or ["课程知识点"]
    markmap_lines = [
        f"# {source.topic}",
        "## 真实概念",
        *[f"- {concept}" for concept in evidence_concepts],
        "## 课程依据",
        *[f"- {title}" for title in evidence_titles],
        "## 概念关系",
        f"- {source.topic}",
        "  - 条件与输入",
        "  - 处理过程",
        "  - 结果与验证",
        "## 学习动作",
        "- 复述概念",
        "- 做题验证",
        "- 标记卡点",
        "## 个性化提醒",
        f"- {source.weak_points}",
    ]
    return {
        "kind": "mindmap",
        "markmap_markdown": "\n".join(markmap_lines),
        "tree": {
            "id": "root",
            "title": source.topic,
            "children": [
                {
                    "id": "concept",
                    "title": "真实概念",
                    "children": [
                        {"id": f"concept-{index}", "title": concept, "children": []}
                        for index, concept in enumerate(evidence_concepts, start=1)
                    ],
                },
                {
                    "id": "evidence",
                    "title": "课程依据",
                    "children": [
                        {"id": f"evidence-{index}", "title": title, "children": []}
                        for index, title in enumerate(evidence_titles, start=1)
                    ],
                },
                {"id": "action", "title": "学习动作", "children": [{"id": "practice", "title": "做题验证", "children": []}]},
            ],
        },
        "citation_refs": _citation_ref(source),
    }


def _build_quiz(source: ArtifactBuildInput) -> dict[str, Any]:
    evidence = source.excerpt_lines[0].removeprefix("- ")
    return {
        "kind": "quiz",
        "questions": [
            {
                "id": "q1",
                "type": "single_choice",
                "prompt": f"学习 {source.topic} 时，哪一种方法最能验证自己是否真正理解？",
                "options": [
                    {"key": "A", "text": "只背结论"},
                    {"key": "B", "text": "说明条件、步骤并用例题验证"},
                    {"key": "C", "text": "跳过课程依据"},
                    {"key": "D", "text": "只记录关键词"},
                ],
                "answer": "B",
                "explanation": f"课程依据“{evidence}”要求把概念、条件和验证过程联系起来。",
                "citation_refs": _citation_ref(source),
            },
            {
                "id": "q2",
                "type": "multiple_choice",
                "prompt": f"复习 {source.topic} 时应同时检查哪些内容？",
                "options": [
                    {"key": "A", "text": "适用条件"},
                    {"key": "B", "text": "关键步骤"},
                    {"key": "C", "text": "验证结果"},
                    {"key": "D", "text": "与知识点无关的记忆"},
                ],
                "answer": ["A", "B", "C"],
                "explanation": "完整掌握需要能够说明条件、执行步骤和验证方式。",
                "citation_refs": _citation_ref(source),
            },
            {
                "id": "q3",
                "type": "short_answer",
                "prompt": f"用三句话解释 {source.topic}，并指出一个容易混淆的点。",
                "options": [],
                "answer": "说明用途、关键步骤和限制条件。",
                "explanation": f"回答应覆盖用途、步骤与边界，并结合薄弱点“{source.weak_points}”自查。",
                "citation_refs": _citation_ref(source),
            },
        ],
        "citation_refs": _citation_ref(source),
    }


def _build_code(source: ArtifactBuildInput) -> dict[str, Any]:
    code = "\n".join(
        [
            "from dataclasses import dataclass",
            "",
            "@dataclass",
            "class StudyStep:",
            "    name: str",
            "    known_cost: float",
            "    estimate: float",
            "",
            "    @property",
            "    def priority(self) -> float:",
            "        return self.known_cost + self.estimate",
            "",
            "steps = [",
            "    StudyStep('read-concept', 1.0, 2.0),",
            "    StudyStep('work-example', 2.0, 0.8),",
            "    StudyStep('explain-in-words', 1.5, 1.2),",
            "]",
            "",
            "for step in sorted(steps, key=lambda item: item.priority):",
            "    print(f'{step.name}: priority={step.priority:.1f}')",
        ]
    )
    return {
        "kind": "code_lab",
        "language": "python",
        "runtime": "pyodide",
        "entry_file": "study_case.py",
        "files": [{"path": "study_case.py", "content": code}],
        "instructions": ["点击运行，在浏览器隔离环境中查看输出。", f"把排序过程对应回 {source.topic} 的判断步骤。"],
        "expected_output": "explain-in-words: priority=2.7\nwork-example: priority=2.8\nread-concept: priority=3.0",
        "tasks": [f"增加一个针对“{source.weak_points}”的学习步骤。", "调整代价并解释排序变化。"],
        "citation_refs": _citation_ref(source),
    }


def _build_slides(source: ArtifactBuildInput) -> dict[str, Any]:
    evidence = source.excerpt_lines[0].removeprefix("- ")
    slide_specs = [
        ("为什么要学", [f"{source.course_title} 中的 {source.topic}", source.profile_goal], "先把学习目标和当前任务联系起来。"),
        ("核心概念", [evidence, "明确输入、处理步骤与输出"], "使用课程依据解释概念，不扩展未经核实的事实。"),
        ("关键步骤", ["识别条件", "拆解过程", "验证结果"], "引导学生逐步复述，而不是只记结论。"),
        ("易错点", [source.weak_points, "忽略适用条件", "缺少验证"], "把薄弱点作为下一步练习入口。"),
        ("课堂练习", [f"用三句话解释 {source.topic}", "完成一道判断题", "说明引用依据"], "先作答，再展示解析。"),
        ("复习任务", ["复述概念", "做题验证", "标记仍未解决的问题"], "把课后任务收束为三个可执行动作。"),
    ]
    return {
        "kind": "slide_deck",
        "theme": {"name": "edunova-light", "aspect_ratio": "16:9", "accent": "#0f8f83"},
        "slides": [
            {
                "id": f"slide-{index}",
                "title": title,
                "bullets": bullets,
                "speaker_notes": notes,
                "layout": "title_and_content" if index > 1 else "title",
                "citation_refs": _citation_ref(source),
            }
            for index, (title, bullets, notes) in enumerate(slide_specs, start=1)
        ],
        "citation_refs": _citation_ref(source),
    }


def _build_animation(source: ArtifactBuildInput) -> dict[str, Any]:
    safe_topic = source.topic.replace('"', "").replace("[", "").replace("]", "")[:32]
    scenes = [
        {
            "id": "scene-1",
            "title": "明确学习目标",
            "narration": f"先确认 {source.topic} 要解决的问题，并把它和当前学习目标联系起来。",
            "duration_ms": 4200,
            "diagram": f"flowchart LR\n  A[学习目标] --> B[{safe_topic}]",
        },
        {
            "id": "scene-2",
            "title": "拆解关键步骤",
            "narration": "把概念拆成条件、处理过程和输出，逐步检查每一环。",
            "duration_ms": 4600,
            "diagram": "flowchart LR\n  A[识别条件] --> B[执行步骤]\n  B --> C[得到结果]",
        },
        {
            "id": "scene-3",
            "title": "用证据验证",
            "narration": "将课程依据与推导结果对照，避免只凭记忆给出结论。",
            "duration_ms": 4600,
            "diagram": "flowchart LR\n  A[课程依据] --> C{结果一致?}\n  B[当前结论] --> C\n  C -->|是| D[形成理解]\n  C -->|否| E[回到卡点]",
        },
        {
            "id": "scene-4",
            "title": "形成学习回流",
            "narration": f"根据薄弱点“{source.weak_points}”安排练习，并把结果回流到下一步学习。",
            "duration_ms": 5000,
            "diagram": "flowchart LR\n  A[薄弱点] --> B[生成资源]\n  B --> C[完成练习]\n  C --> D[更新路径]",
        },
    ]
    return {
        "kind": "animation",
        "scenes": scenes,
        "default_scene_duration_ms": 4600,
        "citation_refs": _citation_ref(source),
    }


def _validate_document(artifact: dict[str, Any]) -> list[str]:
    sections = artifact.get("sections")
    if not isinstance(sections, list) or len(sections) < 4:
        return ["incomplete_document"]
    return []


def _validate_mindmap(artifact: dict[str, Any]) -> list[str]:
    markdown = artifact.get("markmap_markdown")
    tree = artifact.get("tree")
    if not isinstance(markdown, str) or "# " not in markdown or not isinstance(tree, dict):
        return ["incomplete_mindmap"]
    return []


def _validate_quiz(artifact: dict[str, Any]) -> list[str]:
    questions = artifact.get("questions")
    if not isinstance(questions, list) or len(questions) < 3:
        return ["incomplete_quiz"]
    for question in questions:
        if not isinstance(question, dict) or not question.get("prompt") or not question.get("answer") or not question.get("explanation"):
            return ["invalid_quiz_question"]
    return []


def _validate_code(artifact: dict[str, Any]) -> list[str]:
    files = artifact.get("files")
    entry_file = artifact.get("entry_file")
    if artifact.get("language") != "python" or not isinstance(files, list) or not files or not entry_file:
        return ["incomplete_code_lab"]
    entry = next((item for item in files if isinstance(item, dict) and item.get("path") == entry_file), None)
    if entry is None or not isinstance(entry.get("content"), str):
        return ["missing_entry_file"]
    lowered = entry["content"].lower()
    if any(marker in lowered for marker in FORBIDDEN_CODE_MARKERS):
        return ["unsafe_code"]
    return []


def _validate_slides(artifact: dict[str, Any]) -> list[str]:
    slides = artifact.get("slides")
    if not isinstance(slides, list) or len(slides) < 5:
        return ["incomplete_slide_deck"]
    if any(not slide.get("title") or not slide.get("bullets") for slide in slides if isinstance(slide, dict)):
        return ["invalid_slide"]
    return []


def _validate_animation(artifact: dict[str, Any]) -> list[str]:
    scenes = artifact.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < 3:
        return ["incomplete_animation"]
    for scene in scenes:
        if not isinstance(scene, dict) or not str(scene.get("diagram", "")).startswith("flowchart"):
            return ["invalid_animation_scene"]
    return []
