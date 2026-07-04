import { CircleNotch, FileArrowUp, SealCheck, ShieldCheck, WarningCircle } from "@phosphor-icons/react";

import { type WorkspacePanelKind, type WorkspaceStatePanel } from "../../types/api";

type WorkspaceStateStripProps = {
  panels: WorkspaceStatePanel[];
};

const stateIcons = {
  empty: FileArrowUp,
  loading: CircleNotch,
  error: WarningCircle,
  low_evidence: ShieldCheck,
  local_preview: SealCheck
} as const satisfies Record<WorkspacePanelKind, typeof FileArrowUp>;

export function WorkspaceStateStrip({ panels }: WorkspaceStateStripProps) {
  return (
    <section className="workspace-state-strip" aria-label="状态信号">
      {panels.map((panel) => {
        const Icon = stateIcons[panel.kind];

        return (
          <article className={`workspace-state-panel ${panel.kind}`} key={panel.kind}>
            <span className="state-panel-icon" aria-hidden="true">
              <Icon size={18} weight="duotone" />
            </span>
            <span>
              <strong>{panel.title}</strong>
              <small>{panel.description}</small>
            </span>
            <button type="button" aria-label={`${panel.title}：${panel.actionLabel}`}>
              {panel.actionLabel}
            </button>
          </article>
        );
      })}
    </section>
  );
}
