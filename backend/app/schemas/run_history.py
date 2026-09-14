from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RunSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    job_id: str
    workflow: str
    status: Literal["completed", "failed", "cancelled"]
    course_id: str | None
    parent_job_id: str | None
    trace_id: str
    captured_at: str
    artifact_refs: dict[str, Any]
    request_hash: str
    path_content_hash: str | None = None
    steps: list[dict[str, Any]]
    telemetry: dict[str, int]
    error_code: str | None
    digest: str


class SnapshotOperationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class BranchRunRequest(SnapshotOperationRequest):
    expected_active_path_id: int | None = Field(..., gt=0)


class RuntimeCapability(BaseModel):
    name: str
    transport: str
    input_contract: str
    output_contract: str
    snapshot: bool
    replay: bool
    branch: bool
    reexecute: bool
    boundary: str


class RuntimeCatalog(BaseModel):
    workflows: list[RuntimeCapability]
    provider_contracts: dict[str, dict[str, Any]]
    tool_contracts: dict[str, dict[str, Any]]
