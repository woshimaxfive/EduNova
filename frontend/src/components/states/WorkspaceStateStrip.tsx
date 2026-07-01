import { CircleNotch, FileArrowUp, SealCheck, ShieldCheck, WarningCircle } from "@phosphor-icons/react";

import { ActionNotice } from "../feedback/ActionNotice";
import { useActionNotice } from "../feedback/useActionNotice";
import { type WorkspacePanelKind, type WorkspaceStatePanel } from "../../types/api";

type WorkspaceStateStripProps = {
  panels: WorkspaceStatePanel[];
};

const stateIcons = {
  empty: FileArrowUp,
  loading: CircleNotch,
  error: WarningCircle,
  low_evidence: ShieldCheck,
  demo_fallback: SealCheck
} as const satisfies Record<WorkspacePanelKind, typeof FileArrowUp>;

export function WorkspaceStateStrip({ panels }: WorkspaceStateStripProps) {
  const { notice, showNotice } = useActionNotice();

  return (
    <section className="workspace-state-strip" aria-label="学习空间状态设计">
      <div className="state-strip-heading">
        <span>状态信号</span>
        <strong>把异常、低依据和演示来源放在画布旁边，不做卡片墙。</strong>
      </div>
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
            <button
              type="button"
              aria-label={`${panel.title}：${panel.actionLabel}`}
              onClick={() => showNotice(`已选择「${panel.title}」处理入口，真实任务接入后会打开对应流程。`)}
            >
              {panel.actionLabel}
            </button>
          </article>
        );
      })}
      <ActionNotice notice={notice} className="state-strip-notice" />
    </section>
  );
}
