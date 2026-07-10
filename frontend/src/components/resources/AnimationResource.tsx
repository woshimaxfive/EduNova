import { CaretLeft, CaretRight, Pause, Play } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

import { type ResourceAnimationArtifact } from "../../api/resources";
import { MermaidDiagram } from "./MermaidDiagram";

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function AnimationResource({ artifact }: { artifact: ResourceAnimationArtifact }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const scene = artifact.scenes[activeIndex];

  useEffect(() => {
    if (!isPlaying || prefersReducedMotion()) {
      return;
    }
    const timeout = window.setTimeout(() => {
      if (activeIndex >= artifact.scenes.length - 1) {
        setIsPlaying(false);
        return;
      }
      setActiveIndex((current) => current + 1);
    }, scene.duration_ms || artifact.default_scene_duration_ms);
    return () => window.clearTimeout(timeout);
  }, [activeIndex, artifact.default_scene_duration_ms, artifact.scenes.length, isPlaying, scene.duration_ms]);

  function moveTo(index: number) {
    setActiveIndex(Math.max(0, Math.min(index, artifact.scenes.length - 1)));
  }

  return (
    <div className="resource-animation-shell">
      <div className="resource-animation-stage">
        <div className="resource-animation-copy">
          <span>场景 {activeIndex + 1} / {artifact.scenes.length}</span>
          <h3>{scene.title}</h3>
          <p>{scene.narration}</p>
        </div>
        <MermaidDiagram source={scene.diagram} label={`${scene.title}过程图解`} />
      </div>
      <div className="resource-animation-controls">
        <button type="button" aria-label="上一个动画场景" disabled={activeIndex === 0} onClick={() => moveTo(activeIndex - 1)}>
          <CaretLeft size={18} aria-hidden="true" />
        </button>
        <button
          className="resource-animation-play"
          type="button"
          aria-label={isPlaying ? "暂停动画图解" : "播放动画图解"}
          aria-pressed={isPlaying}
          onClick={() => setIsPlaying((current) => !current)}
        >
          {isPlaying ? <Pause size={18} weight="fill" aria-hidden="true" /> : <Play size={18} weight="fill" aria-hidden="true" />}
          <span>{isPlaying ? "暂停" : "播放"}</span>
        </button>
        <div className="resource-animation-timeline" aria-label="动画场景时间轴">
          {artifact.scenes.map((item, index) => (
            <button
              className={index === activeIndex ? "active" : ""}
              key={item.id}
              type="button"
              aria-label={`跳转到场景 ${index + 1}`}
              aria-pressed={index === activeIndex}
              onClick={() => moveTo(index)}
            />
          ))}
        </div>
        <button
          type="button"
          aria-label="下一个动画场景"
          disabled={activeIndex === artifact.scenes.length - 1}
          onClick={() => moveTo(activeIndex + 1)}
        >
          <CaretRight size={18} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
