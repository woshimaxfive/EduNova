import { type ChangeEvent, useState } from "react";

import { type ResourceType } from "../../api/resources";
import { type GeneratedResource } from "../../api/resources";
import { ResourceRenderer } from "../resources/ResourceRenderer";
import { resourceTypeLabels } from "./courseSpaceLabels";

const orderedResourceTypes: ResourceType[] = ["doc", "mindmap", "quiz", "code", "slide", "animation"];

type CourseInlineResourcePanelProps = {
  selectedTypes: ResourceType[];
  isGenerating: boolean;
  feedback: string | null;
  generatedCount: number;
  generatedResources?: GeneratedResource[];
  onToggleType: (resourceType: ResourceType) => void;
  onGenerate: () => void;
};

export function CourseInlineResourcePanel({
  selectedTypes,
  isGenerating,
  feedback,
  generatedCount,
  generatedResources = [],
  onToggleType,
  onGenerate
}: CourseInlineResourcePanelProps) {
  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onToggleType(event.target.value as ResourceType);
  }

  return (
    <section className="course-inline-resource-panel" role="region" aria-label="课程资源生成">
      <div className="course-inline-resource-heading">
        <div>
          <span>多智能体资源生成</span>
          <h3>从当前课程证据生成 A3 资源</h3>
        </div>
        <button type="button" disabled={isGenerating || selectedTypes.length === 0} onClick={onGenerate}>
          {isGenerating ? "生成中" : `生成 ${selectedTypes.length} 类个性化资源`}
        </button>
      </div>
      <div className="course-resource-type-grid">
        {orderedResourceTypes.map((resourceType) => (
          <label key={resourceType}>
            <input
              type="checkbox"
              value={resourceType}
              checked={selectedTypes.includes(resourceType)}
              onChange={handleChange}
            />
            <span>{resourceTypeLabels[resourceType]}</span>
          </label>
        ))}
      </div>
      <p className="course-inline-resource-summary">当前课程已有 {generatedCount} 个资源。生成后可在资源工坊继续查看和导出。</p>
      {feedback ? <p className="course-inline-resource-feedback">{feedback}</p> : null}
      {generatedResources.length > 0 ? <CourseInlineResourceResults resources={generatedResources} /> : null}
    </section>
  );
}

function CourseInlineResourceResults({ resources }: { resources: GeneratedResource[] }) {
  const [selectedId, setSelectedId] = useState(resources[0]?.id ?? "");
  const effectiveSelectedId = resources.some((resource) => resource.id === selectedId) ? selectedId : resources[0]?.id ?? "";
  const selected = resources.find((resource) => resource.id === effectiveSelectedId) ?? resources[0];

  if (!selected) {
    return null;
  }
  return (
    <div className="course-inline-resource-results">
      <div className="course-inline-resource-tabs" role="tablist" aria-label="已生成课程资源">
        {resources.map((resource) => (
          <button
            key={resource.id}
            type="button"
            role="tab"
            aria-selected={resource.id === selected.id}
            onClick={() => setSelectedId(resource.id)}
          >
            {resourceTypeLabels[resource.resource_type]}
          </button>
        ))}
      </div>
      <article className="course-inline-resource-preview">
        <strong>{selected.title}</strong>
        <ResourceRenderer resource={selected} />
      </article>
    </div>
  );
}
