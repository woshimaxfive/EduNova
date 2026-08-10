import { useEffect, useState } from "react";

import type { CourseMasteryPoint } from "../../api/courses";
import type { RagSearchResultItem } from "../../api/rag";
import type { CourseAnswerPanelKind } from "../../components/course-space/CourseClosedLoopActions";
import type { CourseContentMode } from "../../components/course-space/CourseContentView";
import type { CourseWorkspaceMode } from "../../components/course-space/CourseWorkspaceHeader";
import {
  normalizeCourseWorkspaceParams,
  parseCourseWorkspaceUrl,
  sameSearchParams,
  selectCourseWorkspacePoint,
  type GraphScope
} from "./courseWorkspaceState";

type SearchParamsSetter = (next: URLSearchParams, options?: { replace?: boolean }) => void;

export type CourseTurnDetailState = {
  messageId: string;
  panel: CourseAnswerPanelKind;
} | null;

export type CourseStudyTarget =
  | {
      type: "knowledge";
      id: string;
    }
  | {
      type: "citation";
      citation: RagSearchResultItem;
    };

type CourseWorkspaceUrlStateParams = {
  enabled: boolean;
  masteryPoints: CourseMasteryPoint[];
  recommendedPointId: string | null;
  activeWeaknessPointIds: string[];
  searchParams: URLSearchParams;
  setSearchParams: SearchParamsSetter;
};

export function useCourseWorkspaceUrlState({
  enabled,
  masteryPoints,
  recommendedPointId,
  activeWeaknessPointIds,
  searchParams,
  setSearchParams
}: CourseWorkspaceUrlStateParams) {
  const initialState = parseCourseWorkspaceUrl(searchParams);
  const [activeTurnDetail, setActiveTurnDetail] = useState<CourseTurnDetailState>(
    initialState.courseMessageId && initialState.panel
      ? { messageId: initialState.courseMessageId, panel: initialState.panel }
      : null
  );
  const [courseMode, setCourseMode] = useState<CourseWorkspaceMode>(enabled ? initialState.mode : "chat");
  const [courseContentView, setCourseContentView] = useState<CourseContentMode>(enabled ? initialState.view : "overview");
  const [graphScope, setGraphScope] = useState<GraphScope>(initialState.graphScope);
  const [graphChapter, setGraphChapter] = useState(initialState.graphChapter);
  const [isKnowledgeDetailOpen, setIsKnowledgeDetailOpen] = useState(initialState.detailKnowledge);
  const [isStudyAssistantOpen, setIsStudyAssistantOpen] = useState(initialState.mentorOpen);
  const [studyTarget, setStudyTarget] = useState<CourseStudyTarget | null>(
    initialState.knowledgePointId ? { type: "knowledge", id: initialState.knowledgePointId } : null
  );
  const searchSignature = searchParams.toString();
  const weaknessSignature = activeWeaknessPointIds.join(",");

  useEffect(() => {
    if (!enabled || masteryPoints.length === 0) return;
    const currentParams = new URLSearchParams(searchSignature);
    const requested = parseCourseWorkspaceUrl(currentParams);
    const selectedPointId = selectCourseWorkspacePoint(
      masteryPoints,
      requested.knowledgePointId,
      recommendedPointId,
      weaknessSignature ? weaknessSignature.split(",") : []
    );
    const chapters = new Set(
      masteryPoints.map((point) => point.chapter?.trim()).filter((value): value is string => Boolean(value))
    );
    const normalized = normalizeCourseWorkspaceParams(currentParams, requested, selectedPointId, chapters);

    // URL 是课程工作区可恢复状态的唯一来源，同时响应刷新和浏览器前进、后退。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCourseMode(requested.mode);
    setCourseContentView(requested.view);
    setGraphScope(requested.graphScope);
    setGraphChapter(requested.graphChapter && chapters.has(requested.graphChapter) ? requested.graphChapter : "");
    setIsKnowledgeDetailOpen(requested.detailKnowledge && Boolean(selectedPointId));
    setIsStudyAssistantOpen(requested.mode === "study" && requested.mentorOpen);
    if (selectedPointId) setStudyTarget({ type: "knowledge", id: selectedPointId });
    setActiveTurnDetail(
      requested.courseMessageId && requested.panel
        ? { messageId: requested.courseMessageId, panel: requested.panel }
        : null
    );
    if (!sameSearchParams(currentParams, normalized)) {
      setSearchParams(normalized, { replace: true });
    }
  }, [enabled, masteryPoints, recommendedPointId, searchSignature, setSearchParams, weaknessSignature]);

  function openKnowledgeStudy(pointId: string, view: CourseContentMode = "overview") {
    setCourseMode("study");
    setStudyTarget({ type: "knowledge", id: pointId });
    setCourseContentView(view);
    setIsKnowledgeDetailOpen(view === "graph");
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", "study");
    nextParams.set("view", view);
    nextParams.set("knowledge_point_id", pointId);
    if (view === "graph") nextParams.set("detail", "knowledge");
    else nextParams.delete("detail");
    setSearchParams(nextParams, { replace: true });
  }

  function openCitationStudy(citation: RagSearchResultItem) {
    setCourseMode("study");
    setStudyTarget({ type: "citation", citation });
    setCourseContentView("overview");
    if (!citation.knowledge_point_id) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", "study");
    nextParams.set("view", "overview");
    nextParams.set("knowledge_point_id", String(citation.knowledge_point_id));
    nextParams.delete("detail");
    setSearchParams(nextParams, { replace: true });
  }

  function changeCourseMode(mode: CourseWorkspaceMode) {
    setCourseMode(mode);
    if (mode === "chat") setIsStudyAssistantOpen(false);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", mode);
    if (mode === "chat") nextParams.delete("mentor");
    if (mode === "study" && !nextParams.has("view")) nextParams.set("view", "graph");
    setSearchParams(nextParams, { replace: true });
  }

  function changeCourseContentView(view: CourseContentMode) {
    setCourseContentView(view);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", "study");
    nextParams.set("view", view);
    if (view !== "graph") nextParams.delete("detail");
    setSearchParams(nextParams, { replace: true });
  }

  function changeGraphScope(scope: GraphScope) {
    setGraphScope(scope);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("graph_scope", scope);
    if (scope === "focus") nextParams.delete("graph_chapter");
    setSearchParams(nextParams, { replace: true });
  }

  function changeGraphChapter(chapter: string) {
    setGraphChapter(chapter);
    const nextParams = new URLSearchParams(searchParams);
    if (chapter) nextParams.set("graph_chapter", chapter);
    else nextParams.delete("graph_chapter");
    setSearchParams(nextParams, { replace: true });
  }

  function changeKnowledgeDetail(open: boolean) {
    setIsKnowledgeDetailOpen(open);
    const nextParams = new URLSearchParams(searchParams);
    if (open) nextParams.set("detail", "knowledge");
    else nextParams.delete("detail");
    setSearchParams(nextParams, { replace: true });
  }

  return {
    activeTurnDetail,
    changeCourseContentView,
    changeCourseMode,
    changeGraphChapter,
    changeGraphScope,
    changeKnowledgeDetail,
    courseContentView,
    courseMode,
    graphChapter,
    graphScope,
    isKnowledgeDetailOpen,
    isStudyAssistantOpen,
    openCitationStudy,
    openKnowledgeStudy,
    setActiveTurnDetail,
    setCourseMode,
    setIsStudyAssistantOpen,
    setStudyTarget,
    studyTarget
  };
}
