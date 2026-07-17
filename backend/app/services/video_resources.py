from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

from backend.app.services.web_search import WebSearchService
from backend.app.services.content_locale import china_first_content_policy


YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
BILIBILI_ID = re.compile(r"^BV[A-Za-z0-9]{10}$", re.IGNORECASE)


class VideoSearch(Protocol):
    def search(self, query: str, max_results: int | None = None) -> Any: ...


class VideoCurationError(RuntimeError):
    def __init__(self, message: str, *, diagnostics: dict[str, int] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or {}


@dataclass(frozen=True)
class CuratedVideo:
    platform: str
    video_id: str
    title: str
    watch_url: str
    embed_url: str
    snippet: str
    retrieved_at: str
    access_scope: str
    match_level: str = "exact"

    def artifact(self, *, topic: str, fit_reason: str) -> dict[str, Any]:
        return {
            "kind": "external_video",
            "platform": self.platform,
            "video_id": self.video_id,
            "title": self.title,
            "watch_url": self.watch_url,
            "embed_url": self.embed_url,
            "summary": self.snippet,
            "topic": topic,
            "fit_reason": fit_reason,
            "embed_status": "unknown",
            "external_supplement": True,
            "access_scope": self.access_scope,
            "match_level": self.match_level,
            "citation_refs": [],
        }

    def citation(self) -> dict[str, Any]:
        return {
            "source_type": "web",
            "title": self.title,
            "url": self.watch_url,
            "snippet": self.snippet,
            "search_backend": "external",
            "evidence_role": "external_supplement",
            "platform": self.platform,
            "retrieved_at": self.retrieved_at,
            "access_scope": self.access_scope,
        }


class VideoCurationService:
    def __init__(self, search_service: VideoSearch | None = None) -> None:
        self.search_service = search_service or WebSearchService()

    def curate(self, *, topic: str, profile_summary: dict[str, Any]) -> CuratedVideo:
        warnings: list[str] = []
        diagnostics = {"searches": 0, "candidates": 0, "invalid_candidates": 0, "topic_rejections": 0}
        related_candidates: list[CuratedVideo] = []
        for platform in ("bilibili", "youtube"):
            for query, allow_related in self._search_queries(topic, profile_summary, platform=platform):
                diagnostics["searches"] += 1
                result = self.search_service.search(query, max_results=8)
                for item in list(getattr(result, "citations", []) or []):
                    diagnostics["candidates"] += 1
                    candidate = normalize_video(item)
                    if candidate is None or candidate.platform != platform:
                        diagnostics["invalid_candidates"] += 1
                        continue
                    if video_matches_topic(candidate, topic):
                        return replace(candidate, match_level="exact")
                    if allow_related and video_matches_related_topic(candidate, topic):
                        related_candidates.append(candidate)
                    else:
                        diagnostics["topic_rejections"] += 1
                warning = str(getattr(result, "warning", "") or "").strip()
                if warning:
                    warnings.append(warning)
        if related_candidates:
            return replace(related_candidates[0], match_level="related")
        raise VideoCurationError(warnings[-1] if warnings else "没有找到可靠的教学视频", diagnostics=diagnostics)

    @staticmethod
    def _search_query(topic: str, profile_summary: dict[str, Any], *, platform: str = "bilibili") -> str:
        safe_topic = " ".join(str(topic or "课程知识点").split())[:120]
        foundation = " ".join(
            str(
                profile_summary.get("foundation")
                or profile_summary.get("knowledge_foundation")
                or ""
            ).split()
        )[:40]
        goal = " ".join(str(profile_summary.get("goal") or "").split())[:40]
        qualifiers = " ".join(item for item in (foundation, goal) if item)
        site = "site:bilibili.com/video" if platform == "bilibili" else "site:youtube.com/watch"
        return f"{safe_topic} {qualifiers} 教学讲解 {site}".strip()

    @classmethod
    def _search_queries(cls, topic: str, profile_summary: dict[str, Any], *, platform: str) -> list[tuple[str, bool]]:
        """Try a focused query first, then a broader but still topic-bound query."""
        strict = cls._search_query(topic, profile_summary, platform=platform)
        plain = cls._search_query(topic, {}, platform=platform)
        broad = plain.replace("教学讲解", "原理 基础教程")
        queries = [(strict, False)]
        if plain != strict:
            queries.append((plain, False))
        queries.append((broad, True))
        return queries


def normalize_video(item: dict[str, Any]) -> CuratedVideo | None:
    raw_url = str(item.get("url") or "").strip()
    parsed = urlparse(raw_url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    platform = ""
    video_id = ""
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"} and parsed.path == "/watch":
        video_id = str(parse_qs(parsed.query).get("v", [""])[0])
        platform = "youtube"
    elif host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
        platform = "youtube"
    elif host in {"bilibili.com", "www.bilibili.com", "m.bilibili.com"}:
        match = re.fullmatch(r"/video/(BV[A-Za-z0-9]{10})/?", parsed.path, flags=re.IGNORECASE)
        if match:
            video_id = match.group(1)
            platform = "bilibili"
    if platform == "youtube" and not YOUTUBE_ID.fullmatch(video_id):
        return None
    if platform == "bilibili" and not BILIBILI_ID.fullmatch(video_id):
        return None
    if not platform:
        return None
    title = " ".join(str(item.get("title") or "").split())[:160]
    if not title:
        return None
    snippet = " ".join(str(item.get("snippet") or "").split())[:240]
    watch_url = (
        f"https://www.youtube.com/watch?v={video_id}"
        if platform == "youtube"
        else f"https://www.bilibili.com/video/{video_id}"
    )
    embed_url = (
        f"https://www.youtube.com/embed/{video_id}"
        if platform == "youtube"
        else f"https://player.bilibili.com/player.html?bvid={video_id}"
    )
    return CuratedVideo(
        platform=platform,
        video_id=video_id,
        title=title,
        watch_url=watch_url,
        embed_url=embed_url,
        snippet=snippet,
        retrieved_at=str(item.get("retrieved_at") or datetime.now(UTC).isoformat()),
        access_scope=china_first_content_policy.classify_access_scope(watch_url),
    )


def video_matches_topic(candidate: CuratedVideo, topic: str) -> bool:
    """Require visible search metadata to substantiate topic relevance.

    Search providers can return popular but unrelated videos for narrow queries. We do not
    claim to have watched the video; this gate only accepts a candidate when its title or
    snippet visibly covers the requested knowledge point.
    """
    normalized_topic = _normalized_search_text(topic)
    normalized_metadata = _normalized_search_text(f"{candidate.title} {candidate.snippet}")
    if not normalized_topic or not normalized_metadata:
        return False
    if normalized_topic in normalized_metadata:
        return True

    chinese = "".join(re.findall(r"[一-龥]", str(topic or "")))
    if len(chinese) >= 3:
        bigrams = {chinese[index : index + 2] for index in range(len(chinese) - 1)}
        matched = sum(1 for token in bigrams if token in normalized_metadata)
        if matched >= max(2, (len(bigrams) + 1) // 2):
            return True

    ascii_terms = {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9+#*_.-]{1,24}", str(topic or ""))
    }
    return bool(ascii_terms) and all(_normalized_search_text(token) in normalized_metadata for token in ascii_terms)


def video_matches_related_topic(candidate: CuratedVideo, topic: str) -> bool:
    """Accept a clearly related supplement only after exact matching has failed.

    This deliberately remains lexical: a search result is not evidence that an unrelated
    video teaches the requested concept. The returned artifact is labelled as a related
    supplement and is never presented as an exact explanation.
    """
    chinese = "".join(re.findall(r"[一-龥]", str(topic or "")))
    metadata = _normalized_search_text(f"{candidate.title} {candidate.snippet}")
    if len(chinese) >= 4:
        bigrams = {chinese[index : index + 2] for index in range(len(chinese) - 1)}
        return sum(1 for token in bigrams if token in metadata) >= 2
    ascii_terms = {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9+#*_.-]{1,24}", str(topic or ""))
    }
    return len(ascii_terms) >= 2 and any(_normalized_search_text(token) in metadata for token in ascii_terms)


def _normalized_search_text(value: object) -> str:
    return re.sub(r"[^0-9a-zA-Z一-龥]+", "", str(value or "").casefold())
