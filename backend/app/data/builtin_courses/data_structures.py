from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).with_name("data_structures")
SECTION_KINDS = ("concept", "process", "pitfall")
PLACEHOLDER_MARKERS = ("TODO", "TBD", "待补充", "占位", "示例内容", "lorem ipsum")
COMPLEXITY_PATTERN = re.compile(r"(?:O|Ω|Θ)\([^)]{1,40}\)")


class BuiltinCoursePackageError(ValueError):
    pass


def _read_json(relative_path: str) -> dict[str, Any]:
    path = PACKAGE_DIR / relative_path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuiltinCoursePackageError(f"无法读取内置课程文件：{relative_path}") from exc
    if not isinstance(payload, dict):
        raise BuiltinCoursePackageError(f"内置课程文件必须是对象：{relative_path}")
    return payload


def _normalized_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).casefold()


def _complexity_summary(point: dict[str, Any]) -> str:
    source = " ".join(
        (
            point["summary"],
            point["concept"]["content"],
            point["process"]["content"],
            point["pitfall"]["content"],
        )
    )
    notations = list(dict.fromkeys(COMPLEXITY_PATTERN.findall(source)))
    if notations:
        return f"本知识点涉及的主要渐进复杂度为{'、'.join(notations)}，使用时还需核对输入前提与存储结构。"
    return "本知识点以结构、接口或语义辨析为主，不单独给出渐进复杂度；具体操作成本应结合后续算法过程分析。"


def _enrich_point(
    point: dict[str, Any],
    pseudocode: str | None,
    guidance: dict[str, str],
) -> dict[str, Any]:
    process = dict(point["process"])
    if pseudocode:
        process["content"] = (
            f"{process['content']}\n\nC 风格伪代码：\n```c\n{pseudocode.rstrip()}\n```"
        )
    return {
        **point,
        "process": process,
        "learning_objective": guidance["learning_objective"],
        "complexity": _complexity_summary({**point, "process": process}),
        "check_question": guidance["check_question"],
    }


def _chapter_material(chapter: dict[str, Any]) -> dict[str, Any]:
    lines = [f"# {chapter['title']}", "", "## 学习目标"]
    lines.extend(f"- {item}" for item in chapter["learning_objectives"])
    for point in chapter["knowledge_points"]:
        lines.extend(("", f"## {point['title']}", "", point["summary"]))
        lines.extend(
            (
                "",
                f"学习目标：{point['learning_objective']}",
                f"复杂度说明：{point['complexity']}",
                f"检查问题：{point['check_question']}",
            )
        )
        for kind in SECTION_KINDS:
            section = point[kind]
            lines.extend(("", f"### {section['title']}", "", section["content"]))
    return {
        "key": chapter["key"],
        "filename": f"{chapter['order']:02d}-{chapter['title']}.md",
        "content_type": "text/markdown",
        "storage_path": f"builtin://courses/data-structures/{chapter['key']}.md",
        "parse_status": "completed",
        "extracted_text": "\n".join(lines),
        "metadata_json": {
            "source": "builtin_seed",
            "course_slug": "data-structures-c-python",
            "material_kind": "chapter",
            "chapter_key": chapter["key"],
            "library_visible": False,
        },
    }


def _lab_material(labs: list[dict[str, Any]]) -> dict[str, Any]:
    lines = ["# Python 算法实验与常见错误"]
    for lab in labs:
        lines.extend(
            (
                "",
                f"## {lab['title']}",
                "",
                lab["objective"],
                "",
                "```python",
                lab["code"].rstrip(),
                "```",
                "",
                f"预期输出：`{lab['expected_output']}`",
                f"边界检查：{lab['edge_case']}",
            )
        )
    return {
        "key": "python-labs",
        "filename": "09-Python算法实验与常见错误.md",
        "content_type": "text/markdown",
        "storage_path": "builtin://courses/data-structures/python-labs.md",
        "parse_status": "completed",
        "extracted_text": "\n".join(lines),
        "metadata_json": {
            "source": "builtin_seed",
            "course_slug": "data-structures-c-python",
            "material_kind": "lab",
            "library_visible": False,
        },
    }


def _validate_package(package: dict[str, Any]) -> None:
    expected = package["expected_counts"]
    chapters = package["chapters"]
    points = package["knowledge_points"]
    labs = package["labs"]
    materials = package["materials"]
    quality = package["quality_benchmarks"]

    actual = {
        "materials": len(materials),
        "chapters": len(chapters),
        "knowledge_points": len(points),
        "concept_chunks": sum(len(point["sections"]) for point in points),
        "labs": len(labs),
        "chunks": sum(len(point["sections"]) for point in points) + len(labs),
    }
    if actual != expected:
        raise BuiltinCoursePackageError(f"内置课程数量不符合清单：expected={expected}, actual={actual}")

    if [chapter["order"] for chapter in chapters] != list(range(1, 9)):
        raise BuiltinCoursePackageError("章节顺序必须连续且从 1 开始。")

    keys = [point["key"] for point in points]
    if len(keys) != len(set(keys)):
        raise BuiltinCoursePackageError("知识点 key 必须唯一。")
    point_keys = set(keys)
    guidance_keys = set(quality["point_guidance"])
    if guidance_keys != point_keys:
        missing = sorted(point_keys - guidance_keys)
        extra = sorted(guidance_keys - point_keys)
        raise BuiltinCoursePackageError(
            f"知识点教学指引不完整：missing={missing}, extra={extra}"
        )
    material_keys = {material["key"] for material in materials}
    if len(material_keys) != len(materials):
        raise BuiltinCoursePackageError("内部资料 key 必须唯一。")

    seen_texts: set[str] = set()
    for point in points:
        if point["material_key"] not in material_keys:
            raise BuiltinCoursePackageError(f"知识点引用了不存在的资料：{point['key']}")
        prerequisites = point.get("prerequisites", [])
        if point["key"] in prerequisites or any(item not in point_keys for item in prerequisites):
            raise BuiltinCoursePackageError(f"知识点先修关系无效：{point['key']}")
        sections = point["sections"]
        if [item["kind"] for item in sections] != list(SECTION_KINDS):
            raise BuiltinCoursePackageError(f"知识点必须按概念、过程、易错点组织：{point['key']}")
        for section in sections:
            content = section["content"].strip()
            if len(content) < 65 or len(content) > 1600:
                raise BuiltinCoursePackageError(f"知识切片长度不合格：{point['key']}/{section['kind']}")
            if any(marker.casefold() in content.casefold() for marker in PLACEHOLDER_MARKERS):
                raise BuiltinCoursePackageError(f"知识切片包含占位内容：{point['key']}/{section['kind']}")
            normalized = _normalized_text(content)
            if normalized in seen_texts:
                raise BuiltinCoursePackageError(f"知识切片完全重复：{point['key']}/{section['kind']}")
            seen_texts.add(normalized)
        if not point["learning_objective"].strip() or not point["complexity"].strip():
            raise BuiltinCoursePackageError(f"知识点缺少学习目标或复杂度说明：{point['key']}")
        if not point["check_question"].strip().endswith(("。", "？", "?")):
            raise BuiltinCoursePackageError(f"知识点检查问题格式无效：{point['key']}")

    visiting: set[str] = set()
    visited: set[str] = set()
    prerequisites_by_key = {point["key"]: point.get("prerequisites", []) for point in points}

    def visit(key: str) -> None:
        if key in visiting:
            raise BuiltinCoursePackageError(f"知识点先修关系存在环：{key}")
        if key in visited:
            return
        visiting.add(key)
        for prerequisite in prerequisites_by_key[key]:
            visit(prerequisite)
        visiting.remove(key)
        visited.add(key)

    for key in keys:
        visit(key)

    lab_ids: set[str] = set()
    for lab in labs:
        if lab["id"] in lab_ids or lab["knowledge_point_key"] not in point_keys:
            raise BuiltinCoursePackageError(f"实验标识或知识点引用无效：{lab['id']}")
        lab_ids.add(lab["id"])
        try:
            compile(lab["code"], f"<{lab['id']}>", "exec")
            compile(lab["verification_code"], f"<{lab['id']}-verification>", "exec")
        except SyntaxError as exc:
            raise BuiltinCoursePackageError(f"实验代码无法编译：{lab['id']}") from exc
        if not lab["expected_output"].strip() or len(lab["edge_case"].strip()) < 8:
            raise BuiltinCoursePackageError(f"实验缺少预期输出或边界检查：{lab['id']}")

    for case in quality["retrieval_cases"]:
        if case["expected_point_key"] not in point_keys:
            raise BuiltinCoursePackageError(
                f"检索基准引用了不存在的知识点：{case['expected_point_key']}"
            )
        if not case["query"].strip() or not case["required_terms"]:
            raise BuiltinCoursePackageError("检索基准缺少问题或关键事实。")


@lru_cache(maxsize=1)
def load_builtin_data_structures_course() -> dict[str, Any]:
    manifest = _read_json("manifest.json")
    pseudocode_payload = _read_json(manifest["pseudocode_file"])
    pseudocode_by_point = dict(pseudocode_payload["snippets"])
    quality = _read_json(manifest["quality_file"])
    point_guidance = dict(quality["point_guidance"])
    raw_chapters = [_read_json(path) for path in manifest["chapter_files"]]
    chapters = [
        {
            **chapter,
            "knowledge_points": [
                _enrich_point(
                    point,
                    pseudocode_by_point.get(point["key"]),
                    point_guidance[point["key"]],
                )
                for point in chapter["knowledge_points"]
            ],
        }
        for chapter in raw_chapters
    ]
    lab_payload = _read_json(manifest["lab_file"])
    lab_verification_payload = _read_json(manifest["lab_verification_file"])
    lab_verification = dict(lab_verification_payload["verification"])
    labs = [
        {**lab, "verification_code": lab_verification[lab["id"]]}
        for lab in lab_payload["labs"]
    ]

    points: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = []
    order_index = 0
    for chapter in chapters:
        materials.append(_chapter_material(chapter))
        for point in chapter["knowledge_points"]:
            order_index += 1
            points.append(
                {
                    **point,
                    "chapter": chapter["title"],
                    "chapter_key": chapter["key"],
                    "material_key": chapter["key"],
                    "order_index": order_index,
                    "sections": [
                        {"kind": kind, **point[kind]}
                        for kind in SECTION_KINDS
                    ],
                }
            )
    materials.append(_lab_material(labs))

    package = {
        **manifest,
        "chapters": chapters,
        "knowledge_points": points,
        "labs": labs,
        "materials": materials,
        "quality_benchmarks": quality,
    }
    _validate_package(package)
    return package


BUILTIN_DATA_STRUCTURES_COURSE = load_builtin_data_structures_course()
