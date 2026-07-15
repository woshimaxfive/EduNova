from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse


SourceScope = Literal["mainland_preferred", "global_required"]
AccessScope = Literal[
    "mainland_preferred",
    "mainland_community",
    "global_source",
    "external_fallback",
]


@dataclass(frozen=True)
class ChinaFirstContentPolicy:
    version: str = "china-first-v1"
    locale: str = "zh-CN"
    audience: str = "mainland_college_student"

    def prompt_instruction(self, source_scope: SourceScope = "mainland_preferred") -> str:
        source_rule = (
            "检索和举例优先采用中国大陆可访问且与问题直接相关的来源；国际原始规范、论文和框架文档仍可作为必要补充。"
            if source_scope == "mainland_preferred"
            else "问题需要国际原始来源时保留并优先使用直接相关的官方规范、论文或框架文档。"
        )
        return (
            "学生可见内容默认使用自然简体中文，并优先采用中国大陆高校、考试、实习和工程实践场景。"
            "不得为本地化改写课程事实、标准答案、公式或引用。国外专有名词、论文、标准和框架保留原文名称，"
            "首次出现时给出简短中文解释。代码标识符遵循语言生态，讲解、注释和操作说明默认中文。"
            f"{source_rule}"
        )

    def metadata(self, source_scope: SourceScope = "mainland_preferred") -> dict[str, str]:
        return {
            "locale_policy_version": self.version,
            "locale": self.locale,
            "audience": self.audience,
            "source_scope": source_scope,
        }

    @staticmethod
    def classify_access_scope(url: object) -> AccessScope:
        host = (urlparse(str(url or "")).hostname or "").lower().rstrip(".")
        if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
            return "external_fallback"
        if (
            host.endswith(".gov.cn")
            or host.endswith(".edu.cn")
            or host in {"gov.cn", "smartedu.cn", "www.smartedu.cn", "bilibili.com", "www.bilibili.com"}
            or host.endswith(".bilibili.com")
            or host.endswith(".icourse163.org")
        ):
            return "mainland_preferred"
        if host in {
            "csdn.net", "www.csdn.net", "blog.csdn.net", "juejin.cn", "www.juejin.cn",
            "cnblogs.com", "www.cnblogs.com", "zhihu.com", "www.zhihu.com", "gitee.com", "www.gitee.com",
        }:
            return "mainland_community"
        return "global_source"

    def decorate_and_rank_citations(
        self,
        citations: list[dict[str, Any]],
        source_scope: SourceScope = "mainland_preferred",
    ) -> list[dict[str, Any]]:
        decorated = [
            {**item, "access_scope": item.get("access_scope") or self.classify_access_scope(item.get("url"))}
            for item in citations
        ]
        if source_scope == "global_required":
            return decorated
        priority = {
            "mainland_preferred": 0,
            "global_source": 1,
            "mainland_community": 2,
            "external_fallback": 3,
        }
        return [
            item
            for _, item in sorted(
                enumerate(decorated),
                key=lambda pair: (priority.get(str(pair[1].get("access_scope")), 4), pair[0]),
            )
        ]


china_first_content_policy = ChinaFirstContentPolicy()
