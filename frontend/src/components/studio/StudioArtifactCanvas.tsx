import { ArrowClockwise, FolderOpen, Sparkle } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { type GeneratedResource } from "../../api/resources";
import { PATHS } from "../../app/routePaths";
import { InlineFeedback } from "../feedback/InlineFeedback";
import { ResourceRenderer } from "../resources/ResourceRenderer";
import { generationModeLabel, isLowEvidenceResource, resourceTypeMeta } from "./studioResourceMeta";

type StudioArtifactCanvasProps = {
  resource: GeneratedResource | null;
  hasCourse: boolean;
  courseTitle: string | null;
  knowledgePointTitle: string;
  isLoading: boolean;
  isError: boolean;
  onCreate: () => void;
  onRetry: () => void;
};

export function StudioArtifactCanvas({
  resource,
  hasCourse,
  courseTitle,
  knowledgePointTitle,
  isLoading,
  isError,
  onCreate,
  onRetry
}: StudioArtifactCanvasProps) {
  if (isLoading && !resource) {
    return (
      <main className="studio-artifact-canvas" aria-label="成果画布">
        <div className="studio-canvas-skeleton" aria-label="正在读取资源">
          <span /><span /><span /><span />
        </div>
      </main>
    );
  }

  if (isError && !resource) {
    return (
      <main className="studio-artifact-canvas studio-canvas-empty" aria-label="成果画布">
        <ArrowClockwise size={30} weight="duotone" aria-hidden="true" />
        <h2>资源暂时没有读取成功</h2>
        <p>已有成果不会被修改，可以重新读取。</p>
        <button className="soft-button" type="button" onClick={onRetry}>重新读取</button>
      </main>
    );
  }

  if (!resource) {
    return (
      <main className="studio-artifact-canvas studio-canvas-empty" aria-label="成果画布">
        <FolderOpen size={34} weight="duotone" aria-hidden="true" />
        <h2>{hasCourse ? "这门课还没有学习资源" : "先准备一门课程"}</h2>
        <p>{hasCourse ? "从当前课程和知识点生成第一份成果。" : "到资料库上传资料并生成课程后，再回到这里制作成果。"}</p>
        {hasCourse ? (
          <button className="primary-action" type="button" onClick={onCreate}>
            <Sparkle size={17} weight="fill" aria-hidden="true" />
            <span>新建资源</span>
          </button>
        ) : (
          <Link className="soft-button" to={PATHS.library}>进入资料库</Link>
        )}
      </main>
    );
  }

  const { Icon, label } = resourceTypeMeta[resource.resource_type];
  return (
    <main className="studio-artifact-canvas" aria-label="成果画布">
      <article className="studio-artifact-document" role="region" aria-label="资源完整内容">
        <header className="studio-artifact-header">
          <span className="studio-artifact-type-icon"><Icon size={20} weight="duotone" /></span>
          <div>
            <span>{courseTitle ?? "当前课程"} · {knowledgePointTitle}</span>
            <h2>{resource.title}</h2>
            <p>{label} · {generationModeLabel(resource)}</p>
          </div>
        </header>
        {isLowEvidenceResource(resource) ? (
          <InlineFeedback
            message="资料依据不足，这份资源是低依据草稿，请补充课程资料后重新生成。"
            tone="warning"
            className="studio-artifact-warning"
          />
        ) : null}
        {resource.personalization?.status === "stale" ? (
          <InlineFeedback
            message="学习画像已变化，可重新生成以应用新的个性化依据。"
            tone="warning"
            className="studio-artifact-warning"
          />
        ) : null}
        <div className="studio-artifact-content">
          <ResourceRenderer resource={resource} />
        </div>
      </article>
    </main>
  );
}
