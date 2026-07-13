import {
  BookOpenText,
  Brain,
  Briefcase,
  Gauge,
  ListBullets,
  Shapes,
  Sparkle,
  Target,
  WarningCircle
} from "@phosphor-icons/react";

import type { ProfileDimensionKey, ProfileDimensionView } from "../../features/profile/profileViewModel";
import { ProfileConfidenceRadar } from "./ProfileConfidenceRadar";

type ProfileDimensionRailProps = {
  dimensions: ProfileDimensionView[];
  selectedKey: ProfileDimensionKey | null;
  highlightedKeys: ProfileDimensionKey[];
  onSelect: (key: ProfileDimensionKey | null) => void;
};

function DimensionIcon({ dimensionKey }: { dimensionKey: ProfileDimensionKey }) {
  if (dimensionKey === "major_background") return <Briefcase size={17} weight="duotone" aria-hidden="true" />;
  if (dimensionKey === "knowledge_foundation") return <BookOpenText size={17} weight="duotone" aria-hidden="true" />;
  if (dimensionKey === "learning_goal") return <Target size={17} weight="duotone" aria-hidden="true" />;
  if (dimensionKey === "cognitive_style") return <Brain size={17} weight="duotone" aria-hidden="true" />;
  if (dimensionKey === "learning_preference") return <Shapes size={17} weight="duotone" aria-hidden="true" />;
  if (dimensionKey === "weak_points") return <WarningCircle size={17} weight="duotone" aria-hidden="true" />;
  if (dimensionKey === "learning_pace") return <Gauge size={17} weight="duotone" aria-hidden="true" />;
  return <Sparkle size={17} weight="duotone" aria-hidden="true" />;
}

export function ProfileDimensionRail({ dimensions, selectedKey, highlightedKeys, onSelect }: ProfileDimensionRailProps) {
  return (
    <aside className="profile-dimension-rail" aria-label="八维学习画像">
      <div className="profile-radar-heading">
        <div><span>当前轮廓</span><h2>画像可信度分布</h2></div>
        <small>证据充分程度</small>
      </div>
      <ProfileConfidenceRadar dimensions={dimensions} selectedKey={selectedKey} onSelect={onSelect} />
      <nav className="profile-dimension-nav" aria-label="画像维度">
        <button type="button" className={selectedKey === null ? "active" : ""} aria-pressed={selectedKey === null} onClick={() => onSelect(null)}>
          <ListBullets size={17} weight="duotone" aria-hidden="true" />
          <span><strong>全部画像动态</strong><small>查看全部证据变化</small></span>
        </button>
        {dimensions.map((dimension) => (
          <button
            type="button"
            key={dimension.key}
            className={`${selectedKey === dimension.key ? "active" : ""} ${highlightedKeys.includes(dimension.key) ? "just-updated" : ""}`.trim()}
            aria-pressed={selectedKey === dimension.key}
            onClick={() => onSelect(dimension.key)}
          >
            <DimensionIcon dimensionKey={dimension.key} />
            <span>
              <strong>{dimension.label}<b>{dimension.confidence}%</b></strong>
              <small>{dimension.value}</small>
              <i aria-hidden="true"><em style={{ width: `${dimension.confidence}%` }} /></i>
            </span>
            {dimension.candidateCount > 0 ? <mark aria-label={`${dimension.candidateCount} 条候选证据`}>{dimension.candidateCount}</mark> : null}
          </button>
        ))}
      </nav>
    </aside>
  );
}
