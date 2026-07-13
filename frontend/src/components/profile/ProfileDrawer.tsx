import { Brain, CheckCircle, ClockCounterClockwise, ShieldCheck, WarningCircle, X } from "@phosphor-icons/react";
import { useEffect, useRef } from "react";

import type { ProfileEventResponse } from "../../api/profiles";
import {
  buildProfileEventView,
  profileDimensionMeta,
  type ProfileDimensionView
} from "../../features/profile/profileViewModel";
import { AgentTraceDisclosure } from "../evidence/AgentTraceDisclosure";

export type ProfileDrawerMode = "dimension" | "event" | null;

type ProfileDrawerProps = {
  mode: ProfileDrawerMode;
  dimension: ProfileDimensionView | null;
  event: ProfileEventResponse | null;
  relatedEvents: ProfileEventResponse[];
  onClose: () => void;
  onOpenEvent: (eventId: string) => void;
};

function formatEventTime(value: string) {
  if (!value) return "时间未记录";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function ProfileDrawer({ mode, dimension, event, relatedEvents, onClose, onOpenEvent }: ProfileDrawerProps) {
  const drawerRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!mode) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const drawer = drawerRef.current;
    const selector = "button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";
    const focusable = () => Array.from(drawer?.querySelectorAll<HTMLElement>(selector) ?? [])
      .filter((item) => !item.hasAttribute("hidden") && item.getAttribute("aria-hidden") !== "true");
    (focusable()[0] ?? drawer)?.focus();

    function handleKeyDown(keyEvent: KeyboardEvent) {
      if (keyEvent.key === "Escape") {
        keyEvent.preventDefault();
        onCloseRef.current();
        return;
      }
      if (keyEvent.key !== "Tab") return;
      const items = focusable();
      if (items.length === 0) {
        keyEvent.preventDefault();
        drawer?.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (keyEvent.shiftKey && document.activeElement === first) {
        keyEvent.preventDefault();
        last.focus();
      } else if (!keyEvent.shiftKey && document.activeElement === last) {
        keyEvent.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [mode]);

  if (!mode) return null;
  const eventView = event ? buildProfileEventView(event) : null;
  const title = mode === "dimension" ? dimension?.label ?? "维度详情" : "证据详情";

  return (
    <div className="profile-drawer-layer" role="presentation" onMouseDown={(mouseEvent) => {
      if (mouseEvent.target === mouseEvent.currentTarget) onClose();
    }}>
      <aside ref={drawerRef} className="profile-drawer" role="dialog" aria-modal="true" aria-labelledby="profile-drawer-title" tabIndex={-1}>
        <header>
          <div><span>动态学习画像</span><h2 id="profile-drawer-title">{title}</h2></div>
          <button type="button" aria-label={`关闭${title}`} onClick={onClose}><X size={19} weight="bold" aria-hidden="true" /></button>
        </header>

        {mode === "dimension" && dimension ? (
          <div className="profile-drawer-content">
            <section className="profile-dimension-summary">
              <div><Brain size={24} weight="duotone" aria-hidden="true" /><span><small>维度可信度</small><strong>{dimension.confidence}%</strong></span></div>
              <p>{dimension.value}</p>
              <small>{dimension.description}</small>
            </section>
            <dl className="profile-drawer-facts">
              <div><dt>已应用证据</dt><dd>{dimension.appliedCount}</dd></div>
              <div><dt>候选证据</dt><dd>{dimension.candidateCount}</dd></div>
              <div><dt>独立来源</dt><dd>{dimension.sourceCount}</dd></div>
              <div><dt>可信等级</dt><dd>{dimension.evidenceLevel === "trusted" ? "可信" : dimension.evidenceLevel === "advisory" ? "参考" : "待补充"}</dd></div>
            </dl>
            <section className="profile-related-events">
              <header><span>相关证据</span><strong>{relatedEvents.length} 条</strong></header>
              {relatedEvents.length > 0 ? (
                <ol>
                  {relatedEvents.map((item) => {
                    const view = buildProfileEventView(item);
                    return (
                      <li key={item.id}>
                        <button type="button" onClick={() => onOpenEvent(item.id)}>
                          {view.status === "applied" ? <CheckCircle size={17} weight="duotone" aria-hidden="true" /> : <WarningCircle size={17} weight="duotone" aria-hidden="true" />}
                          <span><strong>{item.change_summary}</strong><small>{view.sourceLabel} · {view.statusLabel}</small></span>
                        </button>
                      </li>
                    );
                  })}
                </ol>
              ) : <p className="empty-inline-note">当前维度还没有可展示的画像证据。</p>}
            </section>
          </div>
        ) : event && eventView ? (
          <div className="profile-drawer-content">
            <section className="profile-evidence-summary" data-status={eventView.status}>
              <div>{eventView.status === "applied" ? <ShieldCheck size={26} weight="duotone" aria-hidden="true" /> : <WarningCircle size={26} weight="duotone" aria-hidden="true" />}</div>
              <span><small>{eventView.sourceLabel}</small><strong>{event.change_summary}</strong></span>
            </section>
            <dl className="profile-evidence-facts">
              <div><dt>证据状态</dt><dd>{eventView.statusLabel}</dd></div>
              <div><dt>事件置信度</dt><dd>{eventView.confidencePercent === null ? "未提供" : `${eventView.confidencePercent}%`}</dd></div>
              <div><dt>画像提取</dt><dd>{eventView.generationModeLabel}</dd></div>
              <div><dt>画像审核</dt><dd>{eventView.reviewMode === "model_and_rules" ? "模型与规则审核" : "规则复核"}</dd></div>
              {eventView.repairCount > 0 ? <div><dt>结构修复</dt><dd>{eventView.repairCount} 次</dd></div> : null}
              <div><dt><ClockCounterClockwise size={14} aria-hidden="true" />记录时间</dt><dd>{formatEventTime(event.created_at)}</dd></div>
            </dl>
            <section className="profile-evidence-dimensions">
              <span>已应用维度</span>
              <p>{eventView.appliedDimensions.length > 0 ? eventView.appliedDimensions.map((key) => profileDimensionMeta(key).label).join("、") : "本次没有直接写入长期画像"}</p>
              <span>候选维度</span>
              <p>{eventView.candidateDimensions.length > 0 ? eventView.candidateDimensions.map((key) => profileDimensionMeta(key).label).join("、") : "没有等待确认的候选维度"}</p>
            </section>
            <section className="profile-graph-replay">
              <header><span>ProfileGraph</span><small>真实执行轨迹</small></header>
              <AgentTraceDisclosure traceId={event.agent_trace_id} label="回放 ProfileGraph" staggered />
              {!event.agent_trace_id ? <p className="empty-inline-note">当前历史事件没有可查询的协作轨迹。</p> : null}
            </section>
          </div>
        ) : (
          <div className="profile-drawer-empty"><Brain size={30} weight="duotone" /><p>当前没有可展示的画像详情。</p></div>
        )}
      </aside>
    </div>
  );
}
