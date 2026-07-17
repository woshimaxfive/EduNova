import { lazy, Suspense } from "react";

import { type GeneratedResource } from "../../api/resources";
import { MarkdownMessage } from "../feedback/MarkdownMessage";
import { AnimationResource } from "./AnimationResource";
import { ExternalVideoResource } from "./ExternalVideoResource";
import { MermaidDiagram } from "./MermaidDiagram";
import { MindmapResource } from "./MindmapResource";
import { QuizResource } from "./QuizResource";
import { SlideResource } from "./SlideResource";

const CodeLabResource = lazy(() => import("./CodeLabResource").then((module) => ({ default: module.CodeLabResource })));

function legacyMermaidSource(markdown: string) {
  const match = markdown.match(/```mermaid\s*([\s\S]*?)```/i);
  return match?.[1]?.trim() ?? null;
}

export function ResourceRenderer({ resource }: { resource: GeneratedResource }) {
  const content = resource.content_json;
  const artifact = content.schema_version === 2 || content.schema_version === 3 ? content.artifact : undefined;

  if (artifact?.kind === "document") {
    return (
      <div className="resource-document-view">
        {artifact.sections.map((section) => (
          <section key={section.heading}>
            <h3>{section.heading}</h3>
            <MarkdownMessage content={section.body} className="resource-document-section-body" />
          </section>
        ))}
      </div>
    );
  }
  if (artifact?.kind === "mindmap") {
    return <MindmapResource key={resource.id} artifact={artifact} />;
  }
  if (artifact?.kind === "quiz") {
    return <QuizResource key={resource.id} artifact={artifact} />;
  }
  if (artifact?.kind === "code_lab") {
    return (
      <Suspense fallback={<p className="empty-inline-note">正在加载浏览器代码环境。</p>}>
        <CodeLabResource key={resource.id} artifact={artifact} />
      </Suspense>
    );
  }
  if (artifact?.kind === "slide_deck") {
    return <SlideResource key={resource.id} artifact={artifact} resource={resource} />;
  }
  if (artifact?.kind === "animation") {
    return <AnimationResource key={resource.id} artifact={artifact} />;
  }
  if (artifact?.kind === "external_video") {
    return <ExternalVideoResource key={resource.id} artifact={artifact} />;
  }

  const markdown = content.markdown || "资源内容已生成。";
  const mermaid = resource.resource_type === "mindmap" ? legacyMermaidSource(markdown) : null;
  if (mermaid) {
    return (
      <div className="resource-legacy-visual">
        <MermaidDiagram source={mermaid} label="历史思维导图" />
        <details>
          <summary>查看原始资源文本</summary>
          <MarkdownMessage content={markdown} />
        </details>
      </div>
    );
  }
  return <MarkdownMessage content={markdown} className="resource-markdown-content" />;
}
