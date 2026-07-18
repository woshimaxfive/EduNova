import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  getMyProfile,
  listProfileEvents,
  updateProfileByChat,
  type ProfileEventResponse,
  type StudentProfileResponse
} from "../api/profiles";
import { getCourseLearnerProfile, listCourses, updateCourseLearnerProfile } from "../api/courses";
import { ProfileComposer } from "../components/profile/ProfileComposer";
import { ProfileDimensionRail } from "../components/profile/ProfileDimensionRail";
import {
  ProfileDrawer,
  type ProfileDrawerMode
} from "../components/profile/ProfileDrawer";
import {
  ProfileEventStream,
  type ProfileLocalInteraction
} from "../components/profile/ProfileEventStream";
import { ProfileWorkspaceToolbar } from "../components/profile/ProfileWorkspaceToolbar";
import { NextLearningAction } from "../components/learning/NextLearningAction";
import {
  buildProfileDimensions,
  buildProfileUpdateReceipt,
  calculateProfileCompleteness,
  profileEventsForDimension,
  type ProfileDimensionKey
} from "../features/profile/profileViewModel";
import { type ApiEnvelope } from "../types/api";
import { invalidateLearningNextActions, useLearningNextAction } from "../features/learning-actions/learningActions";
import { PageFrame } from "./PageFrame";
import "../styles/profile.css";

const EMPTY_PROFILE: StudentProfileResponse = {
  id: null,
  version: 0,
  has_profile: false,
  profile_json: {
    major_background: "",
    knowledge_foundation: "",
    learning_goal: "",
    cognitive_style: "",
    learning_preference: "",
    weak_points: [],
    learning_pace: "",
    motivation_interest: ""
  },
  confidence_score: 0,
  completeness_score: 0,
  evidence_confidence_score: 0,
  applied_version: 0,
  dimension_confidence: {},
  dimension_evidence_summary: {},
  evidence_summary: {},
  updated_reason: null,
  updated_at: null,
  next_question: "接下来你最想学会、完成或解决什么？",
  next_question_dimension: "learning_goal"
};

export function ProfilePage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const requestedCourseId = Number(searchParams.get("course_id"));
  const courseId = Number.isFinite(requestedCourseId) && requestedCourseId > 0 ? requestedCourseId : null;
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const highlightTimerRef = useRef<number | null>(null);
  const [selectedKey, setSelectedKey] = useState<ProfileDimensionKey | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [drawerMode, setDrawerMode] = useState<ProfileDrawerMode>(null);
  const [profileAnswer, setProfileAnswer] = useState("");
  const [profileFeedback, setProfileFeedback] = useState("");
  const [highlightedKeys, setHighlightedKeys] = useState<ProfileDimensionKey[]>([]);
  const [localInteraction, setLocalInteraction] = useState<ProfileLocalInteraction | null>(null);
  const [courseProfileFeedback, setCourseProfileFeedback] = useState("");

  useEffect(() => () => {
    if (highlightTimerRef.current !== null) window.clearTimeout(highlightTimerRef.current);
  }, []);

  const profileQuery = useQuery({
    queryKey: ["profiles", "me"],
    queryFn: getMyProfile,
    staleTime: 30_000
  });
  const coursesQuery = useQuery({ queryKey: ["courses", "profile"], queryFn: () => listCourses(), staleTime: 30_000 });
  const courseProfileQuery = useQuery({
    queryKey: ["courses", "learner-profile", courseId],
    queryFn: () => getCourseLearnerProfile(courseId ?? 0),
    enabled: courseId !== null,
    staleTime: 30_000
  });
  const profileCourses = Array.isArray(coursesQuery.data?.data) ? coursesQuery.data.data : [];
  const selectedCourse = profileCourses.find((course) => Number(course.id) === courseId) ?? null;
  const eventsQuery = useQuery({
    queryKey: ["profiles", "events"],
    queryFn: listProfileEvents,
    staleTime: 30_000
  });
  const profile = profileQuery.data?.data ?? EMPTY_PROFILE;
  const nextActionQuery = useLearningNextAction();
  const profileEvents = useMemo(() => eventsQuery.data?.data ?? [], [eventsQuery.data?.data]);
  const dimensions = useMemo(() => buildProfileDimensions(profile, profileEvents), [profile, profileEvents]);
  const selectedDimension = selectedKey ? dimensions.find((item) => item.key === selectedKey) ?? null : null;
  const filteredEvents = useMemo(
    () => profileEventsForDimension(profileEvents, selectedKey),
    [profileEvents, selectedKey]
  );
  const visibleLocalInteraction = useMemo(() => {
    if (!localInteraction || !selectedKey) return localInteraction;
    const dimensions = [
      ...localInteraction.receipt.appliedDimensions,
      ...localInteraction.receipt.candidateDimensions
    ];
    return dimensions.includes(selectedKey) ? localInteraction : null;
  }, [localInteraction, selectedKey]);
  const selectedEvent = selectedEventId ? profileEvents.find((event) => event.id === selectedEventId) ?? null : null;
  const relatedEvents = selectedKey ? profileEventsForDimension(profileEvents, selectedKey) : [];
  const appliedCount = profile.evidence_summary?.applied_count
    ?? profileEvents.filter((event) => event.status !== "candidate").length;
  const candidateCount = profile.evidence_summary?.candidate_count
    ?? profileEvents.filter((event) => event.status === "candidate").length;

  const updateProfileMutation = useMutation({
    mutationFn: updateProfileByChat,
    onMutate: () => setProfileFeedback(""),
    onSuccess: (response, variables) => {
      const receipt = buildProfileUpdateReceipt(profile, response.data.profile, response.data.event);
      queryClient.setQueryData<ApiEnvelope<StudentProfileResponse>>(["profiles", "me"], {
        data: response.data.profile,
        trace_id: response.trace_id
      });
      queryClient.setQueryData<ApiEnvelope<ProfileEventResponse[]> | undefined>(["profiles", "events"], (current) => ({
        data: [response.data.event, ...(current?.data ?? []).filter((event) => event.id !== response.data.event.id)],
        trace_id: response.trace_id
      }));
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["courses", "learning-state"] });
      void queryClient.invalidateQueries({ queryKey: ["resources", "course"] });
      void queryClient.invalidateQueries({ queryKey: ["paths", "current"] });
      void queryClient.invalidateQueries({ queryKey: ["reports", "latest"] });
      void invalidateLearningNextActions(queryClient);
      setLocalInteraction({
        message: variables.message,
        reply: response.data.reply,
        eventId: response.data.event.id,
        receipt
      });
      const affectedKeys = Array.from(new Set([
        ...receipt.changedDimensions,
        ...receipt.appliedDimensions,
        ...receipt.candidateDimensions
      ]));
      setHighlightedKeys(affectedKeys);
      if (affectedKeys[0]) setSelectedKey(affectedKeys[0]);
      if (highlightTimerRef.current !== null) window.clearTimeout(highlightTimerRef.current);
      highlightTimerRef.current = window.setTimeout(() => setHighlightedKeys([]), 760);
      setProfileAnswer("");
    },
    onError: () => setProfileFeedback("画像更新失败，请稍后重试。")
  });
  const updateCourseProfileMutation = useMutation({
    mutationFn: (payload: { learning_goal: string; knowledge_foundation: string; weak_points: string[] }) =>
      updateCourseLearnerProfile(courseId ?? 0, payload),
    onSuccess: () => {
      setCourseProfileFeedback("课程画像已保存，后续路径、资源、练习和报告会使用这门课自己的目标与基础。");
      void queryClient.invalidateQueries({ queryKey: ["courses"] });
      void queryClient.invalidateQueries({ queryKey: ["courses", "learner-profile", courseId] });
      void queryClient.invalidateQueries({ queryKey: ["courses", "learning-state", courseId] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      void invalidateLearningNextActions(queryClient);
    },
    onError: () => setCourseProfileFeedback("课程画像保存失败，请稍后重试。")
  });

  function submitProfileAnswer() {
    const answer = profileAnswer.trim();
    if (!answer || updateProfileMutation.isPending) return;
    updateProfileMutation.mutate({ message: answer });
  }

  function openEvent(eventId: string) {
    setSelectedEventId(eventId);
    setDrawerMode("event");
  }

  function openDimension(key: ProfileDimensionKey) {
    setSelectedKey(key);
    setSelectedEventId(null);
    setDrawerMode("dimension");
  }

  const streamError = profileQuery.isError
    ? "画像读取失败，请稍后重试。"
    : eventsQuery.isError
      ? "部分画像证据暂时无法读取。"
      : profileFeedback;
  const courseProfile = courseProfileQuery.data?.data;
  const initialCourseGoal = courseProfile?.learning_goal || String(courseProfile?.legacy_suggestions.learning_goal ?? "");
  const initialCourseFoundation = courseProfile?.knowledge_foundation || String(courseProfile?.legacy_suggestions.knowledge_foundation ?? "");
  const initialCourseWeakPoints = courseProfile?.weak_points.length
    ? courseProfile.weak_points
    : Array.isArray(courseProfile?.legacy_suggestions.weak_points)
      ? courseProfile.legacy_suggestions.weak_points.map(String)
      : [];

  return (
    <>
      <PageFrame title="学习画像" titleMode="sr-only" variant="wide-workspace" courseId={courseId}>
        <section className="profile-workspace" aria-label="动态学习画像工作台">
          <ProfileWorkspaceToolbar
            completeness={calculateProfileCompleteness(profile)}
            evidenceConfidence={profile.evidence_confidence_score ?? profile.confidence_score}
            version={profile.version}
            appliedCount={appliedCount}
            candidateCount={candidateCount}
            updatedAt={profile.updated_at}
            onFocusComposer={() => composerRef.current?.focus()}
          />
          {courseId !== null ? (
            <form
              className="course-profile-editor"
              aria-label="课程专属画像"
              key={`${courseId}-${courseProfileQuery.dataUpdatedAt}`}
              onSubmit={(event) => {
                event.preventDefault();
                const form = new FormData(event.currentTarget);
                updateCourseProfileMutation.mutate({
                  learning_goal: String(form.get("learning_goal") ?? "").trim(),
                  knowledge_foundation: String(form.get("knowledge_foundation") ?? "").trim(),
                  weak_points: String(form.get("weak_points") ?? "").split(/[,，\n]/).map((item) => item.trim()).filter(Boolean)
                });
              }}
            >
              <div>
                <strong>{selectedCourse ? `《${selectedCourse.title}》学习画像` : "课程专属画像"}</strong>
                <p>目标、基础和困难仅用于这门课程；通用偏好与学习节奏仍由下方全局画像维护。</p>
              </div>
              <label>
                <span>本课程学习目标</span>
                <textarea required name="learning_goal" rows={2} defaultValue={initialCourseGoal} placeholder="例如：期末复习并能独立完成综合题" />
              </label>
              <label>
                <span>本课程已有基础</span>
                <textarea required name="knowledge_foundation" rows={2} defaultValue={initialCourseFoundation} placeholder="例如：理解基本概念，但综合应用还不熟练" />
              </label>
              <label>
                <span>明确困难（可选，每行一项）</span>
                <textarea name="weak_points" rows={2} defaultValue={initialCourseWeakPoints.join("\n")} placeholder="不确定时可以留空，后续由练习证据形成" />
              </label>
              <div className="course-profile-editor-actions">
                <span role="status">{courseProfileFeedback}</span>
                <button
                  type="submit"
                  disabled={updateCourseProfileMutation.isPending}
                >
                  {updateCourseProfileMutation.isPending ? "保存中" : "保存课程画像"}
                </button>
              </div>
            </form>
          ) : null}
          {localInteraction ? (
            <NextLearningAction action={nextActionQuery.data?.data} isLoading={nextActionQuery.isPending} error={nextActionQuery.isError} compact />
          ) : null}
          <div className="profile-workspace-body">
            <ProfileDimensionRail
              dimensions={dimensions}
              selectedKey={selectedKey}
              highlightedKeys={highlightedKeys}
              onSelect={setSelectedKey}
            />
            <div className="profile-conversation-column">
              <ProfileEventStream
                events={filteredEvents}
                selectedDimension={selectedDimension}
                localInteraction={visibleLocalInteraction}
                isLoading={profileQuery.isPending || eventsQuery.isPending}
                isUpdating={updateProfileMutation.isPending}
                error={streamError}
                onOpenDimension={openDimension}
                onOpenEvent={openEvent}
              />
              <ProfileComposer
                inputRef={composerRef}
                value={profileAnswer}
                nextQuestion={profile.next_question}
                nextQuestionDimension={profile.next_question_dimension}
                isUpdating={updateProfileMutation.isPending}
                onChange={setProfileAnswer}
                onSubmit={submitProfileAnswer}
              />
            </div>
          </div>
        </section>
      </PageFrame>

      <ProfileDrawer
        mode={drawerMode}
        dimension={selectedDimension}
        event={selectedEvent}
        relatedEvents={relatedEvents}
        onClose={() => setDrawerMode(null)}
        onOpenEvent={openEvent}
      />
    </>
  );
}
