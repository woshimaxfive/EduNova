import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type PropsWithChildren, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { cancelAiJob, listAiJobs, retryAiJob, streamAiJob, type AiJob } from "../../api/aiJobs";
import { useAuthStore } from "../auth/authStore";
import { invalidateCourseLearningLoop } from "../course-space/courseLoopQueries";
import { invalidateLearningNextActions } from "../learning-actions/learningActions";

type AiJobContextValue = {
  jobs: AiJob[];
  trackJob: (job: AiJob) => void;
  getJob: (jobId: string | null | undefined) => AiJob | undefined;
  cancelJob: (jobId: string) => Promise<AiJob>;
  retryJob: (jobId: string) => Promise<AiJob>;
  dismissJob: (jobId: string) => void;
};

const AiJobContext = createContext<AiJobContextValue | null>(null);
const terminalStatuses = new Set(["completed", "failed", "cancelled"]);

export function AiJobProvider({ children }: PropsWithChildren) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const queryClient = useQueryClient();
  const [jobMap, setJobMap] = useState<Record<string, AiJob>>({});
  const streams = useRef(new Map<string, AbortController>());
  const hiddenJobIds = useRef(new Set<string>());
  const invalidatedTerminalJobIds = useRef(new Set<string>());

  const mergeJob = useCallback((job: AiJob) => {
    setJobMap((current) => ({ ...current, [job.job_id]: job }));
  }, []);

  const subscribe = useCallback((job: AiJob) => {
    if (hiddenJobIds.current.has(job.job_id)) return;
    mergeJob(job);
    if (terminalStatuses.has(job.status) || streams.current.has(job.job_id)) return;
    const controller = new AbortController();
    streams.current.set(job.job_id, controller);
    void streamAiJob(
      job.job_id,
      (_event, snapshot) => {
        mergeJob(snapshot);
        if (terminalStatuses.has(snapshot.status)) {
          streams.current.delete(snapshot.job_id);
          void queryClient.invalidateQueries({ queryKey: ["ai-jobs"] });
          void invalidateLearningNextActions(queryClient);
          if (snapshot.status === "completed" && snapshot.workflow === "course_builder") {
            void queryClient.invalidateQueries({ queryKey: ["courses"] });
            void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
          }
          if (
            snapshot.status === "completed"
            && snapshot.workflow === "path_planning"
            && !invalidatedTerminalJobIds.current.has(snapshot.job_id)
          ) {
            invalidatedTerminalJobIds.current.add(snapshot.job_id);
            const courseId = Number(snapshot.request.course_id ?? snapshot.course_id);
            if (Number.isFinite(courseId) && courseId > 0) {
              void invalidateCourseLearningLoop(queryClient, courseId);
            }
          }
          if (
            snapshot.status === "completed"
            && snapshot.workflow === "resource_generation"
            && !invalidatedTerminalJobIds.current.has(snapshot.job_id)
          ) {
            const courseId = Number(snapshot.request.course_id);
            if (Number.isFinite(courseId) && courseId > 0) {
              invalidatedTerminalJobIds.current.add(snapshot.job_id);
              void invalidateCourseLearningLoop(queryClient, courseId);
            }
          }
          if (
            snapshot.status === "completed"
            && (snapshot.workflow === "practice_generation" || snapshot.workflow === "report_generation")
            && !invalidatedTerminalJobIds.current.has(snapshot.job_id)
          ) {
            const courseId = Number(snapshot.result.course_id ?? snapshot.request.course_id ?? snapshot.course_id);
            if (Number.isFinite(courseId) && courseId > 0) {
              invalidatedTerminalJobIds.current.add(snapshot.job_id);
              void invalidateCourseLearningLoop(queryClient, courseId);
            }
          }
          if (
            snapshot.status === "completed"
            && snapshot.workflow === "material_ingestion"
            && !invalidatedTerminalJobIds.current.has(snapshot.job_id)
          ) {
            invalidatedTerminalJobIds.current.add(snapshot.job_id);
            const materialId = Number(snapshot.request.material_id);
            void Promise.all([
              queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
              queryClient.invalidateQueries({ queryKey: ["materials", "detail", materialId] }),
              queryClient.invalidateQueries({ queryKey: ["materials", "outline", materialId] }),
              queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] })
            ]);
          }
        }
      },
      controller.signal
    ).catch(() => {
      streams.current.delete(job.job_id);
      if (!controller.signal.aborted) {
        window.setTimeout(() => void queryClient.invalidateQueries({ queryKey: ["ai-jobs", "active"] }), 1000);
      }
    });
  }, [mergeJob, queryClient]);

  const activeQuery = useQuery({
    queryKey: ["ai-jobs", "active"],
    queryFn: listAiJobs,
    enabled: isAuthenticated,
    refetchInterval: (query) => {
      const jobs = query.state.data?.data ?? [];
      const needsPolling = jobs.some((job) => !terminalStatuses.has(job.status) && !streams.current.has(job.job_id));
      return needsPolling ? 1000 : 10_000;
    },
    retry: false
  });

  useEffect(() => {
    // Server snapshots are the external source of truth for durable jobs.
    for (const job of activeQuery.data?.data ?? []) subscribe(job);
  }, [activeQuery.data, subscribe]);

  useEffect(() => {
    if (isAuthenticated) return;
    for (const controller of streams.current.values()) controller.abort();
    streams.current.clear();
    hiddenJobIds.current.clear();
    invalidatedTerminalJobIds.current.clear();
    // Authentication changes invalidate every user-scoped job snapshot.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setJobMap({});
  }, [isAuthenticated]);

  useEffect(() => () => {
    for (const controller of streams.current.values()) controller.abort();
    streams.current.clear();
  }, []);

  const cancelJob = useCallback(async (jobId: string) => {
    const job = await cancelAiJob(jobId);
    mergeJob(job);
    return job;
  }, [mergeJob]);

  const retryJob = useCallback(async (jobId: string) => {
    const job = await retryAiJob(jobId);
    hiddenJobIds.current.add(jobId);
    setJobMap((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    });
    subscribe(job);
    return job;
  }, [subscribe]);
  const dismissJob = useCallback((jobId: string) => {
    hiddenJobIds.current.add(jobId);
    setJobMap((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    });
  }, []);

  const value = useMemo<AiJobContextValue>(() => ({
    jobs: Object.values(jobMap).sort((left, right) => right.updated_at.localeCompare(left.updated_at)),
    trackJob: subscribe,
    getJob: (jobId) => (jobId ? jobMap[jobId] : undefined),
    cancelJob,
    retryJob,
    dismissJob
  }), [cancelJob, dismissJob, jobMap, retryJob, subscribe]);

  return <AiJobContext.Provider value={value}>{children}</AiJobContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAiJobs() {
  const context = useContext(AiJobContext);
  const [localJobMap, setLocalJobMap] = useState<Record<string, AiJob>>({});
  const localTrackJob = useCallback((job: AiJob) => {
    setLocalJobMap((current) => ({ ...current, [job.job_id]: job }));
  }, []);
  const localCancelJob = useCallback(async (jobId: string) => {
    const job = await cancelAiJob(jobId);
    localTrackJob(job);
    return job;
  }, [localTrackJob]);
  const localRetryJob = useCallback(async (jobId: string) => {
    const job = await retryAiJob(jobId);
    setLocalJobMap((current) => {
      const next = { ...current };
      delete next[jobId];
      next[job.job_id] = job;
      return next;
    });
    return job;
  }, []);
  const fallback = useMemo<AiJobContextValue>(() => ({
    jobs: Object.values(localJobMap),
    trackJob: localTrackJob,
    getJob: (jobId) => (jobId ? localJobMap[jobId] : undefined),
    cancelJob: localCancelJob,
    retryJob: localRetryJob,
    dismissJob: (jobId) => setLocalJobMap((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    })
  }), [localCancelJob, localJobMap, localRetryJob, localTrackJob]);
  return context ?? fallback;
}
