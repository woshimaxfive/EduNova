import { FileArrowUp, SealCheck, WarningCircle } from "@phosphor-icons/react";

import { type MaterialSource } from "../../types/api";

type SourceClusterProps = {
  materials: MaterialSource[];
};

export function SourceCluster({ materials }: SourceClusterProps) {
  return (
    <div className="source-cluster" aria-label="资料源簇">
      {materials.map((material) => (
        <div className="source-pill" key={material.id}>
          <span className="source-icon" aria-hidden="true">
            {material.parseStatus === "completed" ? (
              <SealCheck size={17} weight="duotone" />
            ) : material.parseStatus === "failed" ? (
              <WarningCircle size={17} weight="duotone" />
            ) : (
              <FileArrowUp size={17} weight="duotone" />
            )}
          </span>
          <span>
            <strong>{material.title}</strong>
            <small>{material.coverageLabel}</small>
          </span>
        </div>
      ))}
    </div>
  );
}
