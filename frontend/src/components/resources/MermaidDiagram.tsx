import { useEffect, useId, useRef, useState } from "react";

type MermaidDiagramProps = {
  source: string;
  label: string;
};

export function MermaidDiagram({ source, label }: MermaidDiagramProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const reactId = useId();
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const host = hostRef.current;
    const diagramId = `edunova-mermaid-${reactId.replace(/[^a-zA-Z0-9]/g, "")}`;

    async function renderDiagram() {
      try {
        const { default: mermaid } = await import("mermaid");
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          fontFamily: "Inter, 'Microsoft YaHei', sans-serif",
          themeVariables: {
            primaryColor: "#e0f2ef",
            primaryTextColor: "#10212a",
            primaryBorderColor: "#0f8f83",
            lineColor: "#607876",
            secondaryColor: "#f4f8f7",
            tertiaryColor: "#ffffff"
          }
        });
        const result = await mermaid.render(diagramId, source);
        if (!cancelled && host) {
          host.innerHTML = result.svg;
          result.bindFunctions?.(host);
          setError(false);
        }
      } catch {
        if (!cancelled) {
          setError(true);
        }
      }
    }

    void renderDiagram();
    return () => {
      cancelled = true;
      host?.replaceChildren();
    };
  }, [reactId, source]);

  if (error) {
    return <pre className="resource-diagram-fallback">{source}</pre>;
  }

  return <div className="resource-mermaid-canvas" ref={hostRef} role="img" aria-label={label} />;
}
