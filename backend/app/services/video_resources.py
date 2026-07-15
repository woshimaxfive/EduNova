from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

from backend.app.services.web_search import WebSearchService


YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
BILIBILI_ID = re.compile(r"^BV[A-Za-z0-9]{10}$", re.IGNORECASE)


class VideoSearch(Protocol):
    def search(self, query: str, max_results: int | None = None) -> Any: ...


class VideoCurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CuratedVideo:
    platform: str
    video_id: str
    title: str
    watch_url: str
    embed_url: str
    snippet: str
    retrieved_at: str

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
        }


class VideoCurationService:
    def __init__(self, search_service: VideoSearch | None = None) -> None:
        self.search_service = search_service or WebSearchService()

    def curate(self, *, topic: str, profile_summary: dict[str, Any]) -> CuratedVideo:
        query = self._search_query(topic, profile_summary)
        result = self.search_service.search(query, max_results=8)
        for item in list(getattr(result, "citations", []) or []):
            candidate = normalize_video(item)
            if candidate is not None:
                return candidate
        warning = str(getattr(result, "warning", "") or "没有找到合格的教学视频")
        raise VideoCurationError(warning)

    @staticmethod
    def _search_query(topic: str, profile_summary: dict[str, Any]) -> str:
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
        return f"{safe_topic} {qualifiers} 教学讲解 site:bilibili.com/video OR site:youtube.com/watch".strip()


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
    )
