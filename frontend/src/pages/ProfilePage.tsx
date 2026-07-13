import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  getMyProfile,
  listProfileEvents,
  updateProfileByChat,
  type ProfileEventResponse,
  type StudentProfileResponse
} from "../api/profiles";
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
import {
  buildProfileDimensions,
  buildProfileUpdateReceipt,
  profileEventsForDimension,
  type ProfileDimensionKey
} from "../features/profile/profileViewModel";
import { type ApiEnvelope } from "../types/api";
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
  dimension_confidence: {},
  evidence_summary: {},
  updated_reason: null,
  updated_at: null,
  next_question: "接下来你最想学会、完成或解决什么？",
  next_question_dimension: "learning_goal"
};

export function ProfilePage() {
  const queryClient = useQueryClient();
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const highlightTimerRef = useRef<number | null>(null);
  const [selectedKey, setSelectedKey] = useState<ProfileDimensionKey | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [drawerMode, setDrawerMode] = useState<ProfileDrawerMode>(null);
  const [profileAnswer, setProfileAnswer] = useState("");
  const [profileFeedback, setProfileFeedback] = useState("");
  const [highlightedKeys, setHighlightedKeys] = useState<ProfileDimensionKey[]>([]);
  const [localInteraction, setLocalInteraction] = useState<ProfileLocalInteraction | null>(null);

  useEffect(() => () => {
    if (highlightTimerRef.current !== null) window.clearTimeout(highlightTimerRef.current);
  }, []);

  const profileQuery = useQuery({
    queryKey: ["profiles", "me"],
    queryFn: getMyProfile,
    staleTime: 30_000
  });
  const eventsQuery = useQuery({
    queryKey: ["profiles", "events"],
    queryFn: listProfileEvents,
    staleTime: 30_000
  });
  const profile = profileQuery.data?.data ?? EMPTY_PROFILE;
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

  return (
    <>
      <PageFrame title="学习画像" titleMode="sr-only" variant="wide-workspace">
        <section className="profile-workspace" aria-label="动态学习画像工作台">
          <ProfileWorkspaceToolbar
            confidence={profile.confidence_score}
            version={profile.version}
            appliedCount={appliedCount}
            candidateCount={candidateCount}
            updatedAt={profile.updated_at}
            onFocusComposer={() => composerRef.current?.focus()}
          />
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
