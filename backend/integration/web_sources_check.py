"""Opt-in public-web smoke test. No user records, model keys or database writes."""
from __future__ import annotations

import argparse
import json
import time

from backend.app.services.video_resources import VideoCurationError, VideoCurationService
from backend.app.services.web_reader import WebPageReader
from backend.app.services.web_search import WebSearchService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-body", action="store_true")
    args = parser.parse_args()
    search = WebSearchService()
    assert search.prefer_external_search, "This smoke test requires local SearXNG"
    failed = False
    for topic in ("Python 列表推导式", "二叉树层序遍历"):
        start = time.monotonic()
        try:
            video = VideoCurationService(search).curate(topic=topic, profile_summary={})
            print(json.dumps({"topic": topic, "url": video.watch_url, "title": video.title,
                              "seconds": round(time.monotonic() - start, 2),
                              "playback_verified": False}, ensure_ascii=False), flush=True)
        except VideoCurationError as error:
            print(json.dumps({"topic": topic, "error": str(error), "diagnostics": error.diagnostics},
                             ensure_ascii=False), flush=True)
            failed = True
    page = WebPageReader().read("https://docs.python.org/zh-cn/3/tutorial/datastructures.html", "列表推导式")
    print(json.dumps({"body_status": page.status, "body_chars": len(page.text),
                      "body_verified": page.status == "read" and "列表推导式" in page.text},
                     ensure_ascii=False), flush=True)
    if args.require_body and (page.status != "read" or "列表推导式" not in page.text):
        failed = True
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
