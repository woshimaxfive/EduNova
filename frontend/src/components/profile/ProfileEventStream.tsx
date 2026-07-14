import { Brain, CaretRight, CheckCircle, ClockCounterClockwise, Sparkle, WarningCircle } from "@phosphor-icons/react";
import { useEffect, useMemo, useRef } from "react";

import type { ProfileEventResponse } from "../../api/profiles";
import {
  buildProfileEventView,
  profileDimensionMeta,
  type ProfileDimensionKey,
  type ProfileDimensionView,
  type ProfileUpdateReceipt
} from "../../features/profile/profileViewModel";

export type ProfileLocalInteraction = {
  message: string;
  reply: string;
  eventId: string;
  receipt: ProfileUpdateReceipt;
};

type ProfileEventStreamProps = {
  events: ProfileEventResponse[];
  selectedDimension: ProfileDimensionView | null;
  localInteraction: ProfileLocalInteraction | null;
  isLoading: boolean;
  isUpdating: boolean;
  error: string;
  onOpenDimension: (key: ProfileDimensionKey) => void;
  onOpenEvent: (eventId: string) => void;
};

function formatEventTime(value: string) {
  if (!value) return "时间未记录";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function DimensionLabels({ keys }: { keys: ProfileDimensionKey[] }) {
  if (keys.length === 0) return <span className="profile-event-dimension">画像证据</span>;
  return <>{keys.map((key) => <span className="profile-event-dimension" key={key}>{profileDimensionMeta(key).label}</span>)}</>;
}

export function ProfileEventStream({
  events,
  selectedDimension,
  localInteraction,
  isLoading,
  isUpdating,
  error,
  onOpenDimension,
  onOpenEvent
}: ProfileEventStreamProps) {
  const streamRef = useRef<HTMLDivElement | null>(null);
  const visibleEvents = useMemo(
    () => [...events]
      .filter((event) => event.id !== localInteraction?.eventId)
      .sort((left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime()),
    [events, localInteraction?.eventId]
  );

  useEffect(() => {
    const stream = streamRef.current;
    if (stream) stream.scrollTop = stream.scrollHeight;
  }, [isUpdating, localInteraction, visibleEvents.length]);

  return (
    <main className="profile-evolution-main" aria-label="画像动态">
      <header className="profile-evolution-heading">
        {selectedDimension ? (
          <>
            <div>
              <h2>{selectedDimension.label}</h2>
              <p>{selectedDimension.value}</p>
            </div>
            <button type="button" onClick={() => onOpenDimension(selectedDimension.key)}>
              维度详情<CaretRight size={16} weight="bold" aria-hidden="true" />
            </button>
          </>
        ) : (
          <div>
            <h2>更新记录</h2>
          </div>
        )}
      </header>

      <div ref={streamRef} className="profile-event-scroll" role="feed" aria-busy={isLoading || isUpdating}>
        {error ? <p className="form-error profile-stream-error">{error}</p> : null}
        {isLoading ? <div className="profile-stream-loading" role="status">正在读取画像证据</div> : null}
        {!isLoading && visibleEvents.length === 0 && !localInteraction ? (
          <div className="profile-stream-empty">
            <Brain size={34} weight="duotone" aria-hidden="true" />
            <h3>画像从一次真实回答开始</h3>
            <p>回答下方问题后，系统会记录经过审核的画像变化。</p>
          </div>
        ) : null}

        {visibleEvents.map((event) => {
          const view = buildProfileEventView(event);
          return (
            <article className="profile-event-entry" key={event.id} data-status={view.status}>
              <span className="profile-event-marker" aria-hidden="true">
                {view.status === "applied" ? <CheckCircle size={19} weight="duotone" /> : <WarningCircle size={19} weight="duotone" />}
              </span>
              <button type="button" onClick={() => onOpenEvent(event.id)}>
                <span className="profile-event-meta">
                  <strong>{view.sourceLabel}</strong>
                  <small><ClockCounterClockwise size={13} aria-hidden="true" />{formatEventTime(event.created_at)}</small>
                </span>
                <b>{event.change_summary}</b>
                <span className="profile-event-dimensions"><DimensionLabels keys={view.dimensions} /></span>
                <span className="profile-event-status">
                  {view.statusLabel}{view.confidencePercent !== null ? ` · ${view.confidencePercent}%` : ""}
                  <CaretRight size={15} weight="bold" aria-hidden="true" />
                </span>
              </button>
            </article>
          );
        })}

        {localInteraction ? (
          <section className="profile-interaction-receipt" aria-label="本次画像更新">
            <p className="profile-local-message">{localInteraction.message}</p>
            <div className="profile-receipt-body">
              <Sparkle size={21} weight="duotone" aria-hidden="true" />
              <div>
                <strong>{localInteraction.reply}</strong>
                {localInteraction.receipt.appliedDimensions.length > 0 ? (
                  <p><span>已应用</span><DimensionLabels keys={localInteraction.receipt.appliedDimensions} /></p>
                ) : null}
                {localInteraction.receipt.candidateDimensions.length > 0 ? (
                  <p><span>候选证据</span><DimensionLabels keys={localInteraction.receipt.candidateDimensions} /></p>
                ) : null}
              </div>
              <button type="button" onClick={() => onOpenEvent(localInteraction.eventId)}>查看依据</button>
            </div>
          </section>
        ) : null}

        {isUpdating ? (
          <div className="profile-updating-state" role="status">
            <span aria-hidden="true" /><p>正在更新画像</p>
          </div>
        ) : null}
      </div>
    </main>
  );
}
