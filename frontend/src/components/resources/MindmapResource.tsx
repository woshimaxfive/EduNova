import { ArrowsOut, MagnifyingGlassMinus, MagnifyingGlassPlus, Scan } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

import { type ResourceMindmapArtifact } from "../../api/resources";
import { normalizeMindmapMarkdown } from "./mindmapMarkdown";

type MarkmapInstance = {
  fit: (maxScale?: number) => Promise<void>;
  rescale: (scale: number) => Promise<void>;
  destroy: () => void;
};

export function MindmapResource({ artifact }: { artifact: ResourceMindmapArtifact }) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const instanceRef = useRef<MarkmapInstance | null>(null);
  const [renderError, setRenderError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function renderMarkmap() {
      try {
        const [{ Transformer }, { Markmap }] = await Promise.all([import("markmap-lib"), import("markmap-view")]);
        if (cancelled || !svgRef.current) {
          return;
        }
        const transformer = new Transformer();
        const { root } = transformer.transform(normalizeMindmapMarkdown(artifact.markmap_markdown));
        instanceRef.current?.destroy();
        instanceRef.current = Markmap.create(
          svgRef.current,
          {
            autoFit: true,
            duration: 220,
            fitRatio: 0.92,
            maxWidth: 280,
            paddingX: 12,
            spacingHorizontal: 90,
            spacingVertical: 10
          },
          root
        );
        await instanceRef.current.fit();
        setRenderError(false);
      } catch {
        if (!cancelled) {
          setRenderError(true);
        }
      }
    }

    void renderMarkmap();
    return () => {
      cancelled = true;
      instanceRef.current?.destroy();
      instanceRef.current = null;
    };
  }, [artifact.markmap_markdown]);

  async function openFullscreen() {
    const container = svgRef.current?.parentElement;
    if (container?.requestFullscreen) {
      await container.requestFullscreen();
      await instanceRef.current?.fit();
    }
  }

  return (
    <div className="resource-visual-shell resource-mindmap-shell">
      <div className="resource-visual-toolbar" aria-label="思维导图工具">
        <span>可拖动与缩放</span>
        <div>
          <button type="button" aria-label="放大思维导图" title="放大" onClick={() => void instanceRef.current?.rescale(1.2)}>
            <MagnifyingGlassPlus size={17} aria-hidden="true" />
          </button>
          <button type="button" aria-label="缩小思维导图" title="缩小" onClick={() => void instanceRef.current?.rescale(0.82)}>
            <MagnifyingGlassMinus size={17} aria-hidden="true" />
          </button>
          <button type="button" aria-label="适应思维导图画布" title="适应画布" onClick={() => void instanceRef.current?.fit()}>
            <Scan size={17} aria-hidden="true" />
          </button>
          <button type="button" aria-label="全屏查看思维导图" title="全屏" onClick={() => void openFullscreen()}>
            <ArrowsOut size={17} aria-hidden="true" />
          </button>
        </div>
      </div>
      {renderError ? (
        <pre className="resource-diagram-fallback">{artifact.markmap_markdown}</pre>
      ) : (
        <svg ref={svgRef} className="resource-markmap-canvas" role="img" aria-label="知识点思维导图" />
      )}
    </div>
  );
}
