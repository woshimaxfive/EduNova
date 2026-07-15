from __future__ import annotations

from backend.app.services.content_locale import ChinaFirstContentPolicy


def test_china_first_policy_classifies_and_ranks_without_claiming_reachability() -> None:
    policy = ChinaFirstContentPolicy()
    citations = [
        {"title": "社区文章", "url": "https://blog.csdn.net/example/article/details/1"},
        {"title": "国际规范", "url": "https://www.rfc-editor.org/rfc/rfc9110"},
        {"title": "高校课程", "url": "https://example.edu.cn/course/1"},
        {"title": "境外视频", "url": "https://www.youtube.com/watch?v=abcDEF_1234"},
    ]

    ranked = policy.decorate_and_rank_citations(citations)

    assert [item["access_scope"] for item in ranked] == [
        "mainland_preferred", "global_source", "mainland_community", "external_fallback"
    ]
    assert all("verified" not in item and "reachable" not in item for item in ranked)


def test_global_required_preserves_relevance_order_and_policy_protects_facts() -> None:
    policy = ChinaFirstContentPolicy()
    citations = [
        {"title": "RFC", "url": "https://www.rfc-editor.org/rfc/rfc9110"},
        {"title": "高校课程", "url": "https://example.edu.cn/course/1"},
    ]

    ranked = policy.decorate_and_rank_citations(citations, "global_required")

    assert [item["title"] for item in ranked] == ["RFC", "高校课程"]
    instruction = policy.prompt_instruction()
    assert "简体中文" in instruction
    assert "不得为本地化改写课程事实、标准答案、公式或引用" in instruction
    assert "代码标识符" in instruction
