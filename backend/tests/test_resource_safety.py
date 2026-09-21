import pytest

from backend.app.services.resource_modeling import ResourceModelingService
from backend.app.services.resource_quality import quality_risks
from backend.app.services.resource_safety import sensitive_output_flags


@pytest.mark.parametrize("text,blocked", [
    ('{"id":"task-1","title":"mask-node"}', False),
    ("sk-real-secret", True), ("密钥sk-real-secret", True),
    ("SK-real-secret", True), ("sk-", True),
    ("系统提示词", True), ("System Prompt", True),
    ("资料原文", True), ("API KEY", True),
])
def test_resource_checks_agree_on_credentials_and_ordinary_node_ids(text, blocked):
    assert ResourceModelingService.contains_sensitive(text) is blocked
    risks = quality_risks("doc", {"markdown": text}, topic="", evidence_terms=[], valid_citation_refs=set())
    assert ("sensitive_output" in risks) is blocked


def test_safety_diagnostics_never_contain_the_candidate():
    assert sensitive_output_flags("系统提示词 sk-real-secret") == [
        "sensitive_system_prompt_zh", "sensitive_credential_prefix",
    ]
