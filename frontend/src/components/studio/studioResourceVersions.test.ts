import { describe, expect, it } from "vitest";

import { type GeneratedResource } from "../../api/resources";
import { groupResourceVersions, versionLabel } from "./studioResourceVersions";

function resource(id: string, overrides: Partial<GeneratedResource> = {}): GeneratedResource {
  return {
    id,
    course_id: "10",
    knowledge_point_id: "20",
    resource_type: "doc",
    title: `资源 ${id}`,
    content_json: { markdown: `# 资源 ${id}` },
    citation_json: [],
    status: "completed",
    review_status: "passed",
    confidence_score: 0.8,
    agent_trace_id: null,
    created_at: `2026-07-${id.padStart(2, "0")}T10:00:00Z`,
    updated_at: `2026-07-${id.padStart(2, "0")}T10:00:00Z`,
    ...overrides
  };
}

describe("studio resource version grouping", () => {
  it("groups one version family and keeps newest version first", () => {
    const families = groupResourceVersions([
      resource("1", { version_family_id: "family-a", version_number: 1 }),
      resource("2", { version_family_id: "family-a", version_number: 2, generation_action: "alternative" }),
      resource("3", { version_family_id: "family-a", version_number: 3, generation_action: "refine" })
    ]);

    expect(families).toHaveLength(1);
    expect(families[0].latest.id).toBe("3");
    expect(families[0].versions.map((item) => item.id)).toEqual(["3", "2", "1"]);
    expect(versionLabel(families[0].latest)).toBe("v3");
  });

  it("keeps legacy resources as independent families", () => {
    const families = groupResourceVersions([resource("1"), resource("2")]);

    expect(families).toHaveLength(2);
    expect(families.every((family) => family.versions.length === 1)).toBe(true);
    expect(versionLabel(families[0].latest)).toBe("历史版本");
  });
});
