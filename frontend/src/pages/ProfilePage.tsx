import { Brain, ChatCircleText, Compass, PencilSimpleLine, TrendUp } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import {
  getMyProfile,
  listProfileEvents,
  updateProfileByChat,
  type ProfileEventResponse,
  type StudentProfileResponse
} from "../api/profiles";
import { type ApiEnvelope } from "../types/api";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { AgentTraceDisclosure } from "../components/evidence/AgentTraceDisclosure";
import { PageFrame } from "./PageFrame";

type ProfileDimension = {
  key: keyof StudentProfileResponse["profile_json"];
  label: string;
  value: string;
  tone: string;
  confidence: number;
};

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
  next_question: "这门课你最想先解决什么问题？"
};

function buildDimensions(profile: StudentProfileResponse): ProfileDimension[] {
  const profileJson = profile.profile_json;
  return [
    { key: "learning_goal", label: "目标", value: profileJson.learning_goal || "待补充", tone: "focus", confidence: profile.dimension_confidence?.learning_goal ?? 0 },
    { key: "knowledge_foundation", label: "基础", value: profileJson.knowledge_foundation || "未填写", tone: "ready", confidence: profile.dimension_confidence?.knowledge_foundation ?? 0 },
    {
      key: "weak_points",
      label: "薄弱点",
      value: profileJson.weak_points.length > 0 ? profileJson.weak_points.join("、") : "未填写",
      tone: "warning",
      confidence: profile.dimension_confidence?.weak_points ?? 0
    },
    { key: "learning_pace", label: "节奏", value: profileJson.learning_pace || "未填写", tone: "steady", confidence: profile.dimension_confidence?.learning_pace ?? 0 },
    { key: "major_background", label: "背景", value: profileJson.major_background || "未填写", tone: "ready", confidence: profile.dimension_confidence?.major_background ?? 0 },
    { key: "learning_preference", label: "方式", value: profileJson.learning_preference || "未填写", tone: "focus", confidence: profile.dimension_confidence?.learning_preference ?? 0 },
    { key: "cognitive_style", label: "风格", value: profileJson.cognitive_style || "未填写", tone: "steady", confidence: profile.dimension_confidence?.cognitive_style ?? 0 },
    { key: "motivation_interest", label: "动机", value: profileJson.motivation_interest || "未填写", tone: "ready", confidence: profile.dimension_confidence?.motivation_interest ?? 0 }
  ];
}

function profileSourceLabel(sourceType?: string) {
  if (sourceType === "profile_chat") return "主动回答";
  if (sourceType === "practice_assessment") return "练习诊断";
  if (sourceType === "course_question") return "课程问答";
  return "学习证据";
}

export function ProfilePage() {
  const [isEditingGoal, setIsEditingGoal] = useState(false);
  const [goalDraft, setGoalDraft] = useState("");
  const [profileAnswer, setProfileAnswer] = useState("");
  const [profileFeedback, setProfileFeedback] = useState<string | null>(null);
  const queryClient = useQueryClient();
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
  const profileEvents = eventsQuery.data?.data ?? [];
  const profileDimensions = useMemo(() => buildDimensions(profile), [profile]);
  const currentGoal = profile.profile_json.learning_goal;
  const confidence = Math.round(profile.confidence_score);
  const updateProfileMutation = useMutation({
    mutationFn: updateProfileByChat,
    onSuccess: (response) => {
      queryClient.setQueryData<ApiEnvelope<StudentProfileResponse>>(["profiles", "me"], {
        data: response.data.profile,
        trace_id: response.trace_id
      });
      queryClient.setQueryData<ApiEnvelope<ProfileEventResponse[]> | undefined>(["profiles", "events"], (current) => ({
        data: [response.data.event, ...(current?.data ?? [])],
        trace_id: response.trace_id
      }));
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      setGoalDraft(response.data.profile.profile_json.learning_goal);
      setProfileAnswer("");
      setIsEditingGoal(false);
      setProfileFeedback(null);
    },
    onError: () => {
      setProfileFeedback("画像更新失败，请稍后重试。");
    }
  });

  function saveGoal() {
    const nextGoal = goalDraft.trim();

    if (!nextGoal) {
      return;
    }

    updateProfileMutation.mutate({ message: nextGoal });
  }

  function submitProfileAnswer() {
    const answer = profileAnswer.trim();

    if (!answer) {
      return;
    }

    updateProfileMutation.mutate({ message: answer });
  }

  return (
    <PageFrame title="学习画像">
      <div className="student-workspace profile-workspace">
        <section className="student-panel profile-summary" role="region" aria-label="学习画像">
          <div className="student-panel-heading">
            <div>
              <h2>当前画像</h2>
            </div>
            <span className="profile-score">
              <TrendUp size={17} weight="duotone" aria-hidden="true" />
              可信度 {confidence}%
            </span>
          </div>
          <InlineFeedback
            message={profileQuery.isError ? "画像读取失败，请稍后重试。" : profileFeedback}
            tone="warning"
          />
          <div className="profile-dimension-grid">
            {profileDimensions.map((item) => (
              <article className={`profile-dimension ${item.tone}`} key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <small>{item.confidence > 0 ? `维度可信度 ${Math.round(item.confidence)}%` : "等待有效证据"}</small>
              </article>
            ))}
          </div>
          {isEditingGoal ? (
            <div className="inline-edit-row">
              <input aria-label="学习目标" value={goalDraft} onChange={(event) => setGoalDraft(event.target.value)} />
              <button className="primary-action" type="button" onClick={saveGoal} disabled={updateProfileMutation.isPending}>
                保存目标
              </button>
            </div>
          ) : null}
          <button
            className="soft-button"
            type="button"
            onClick={() => {
              if (!isEditingGoal) {
                setGoalDraft(currentGoal);
              }
              setIsEditingGoal((editing) => !editing);
            }}
          >
            <PencilSimpleLine size={17} weight="duotone" aria-hidden="true" />
            <span>更新目标</span>
          </button>
        </section>

        <aside className="profile-side-stack">
          <section className="student-panel evidence-summary" role="region" aria-label="画像证据">
            <div className="student-panel-heading compact">
              <div>
                <h2>判断依据</h2>
              </div>
            </div>
            <ul className="evidence-list">
              {profileEvents.length === 0 && !eventsQuery.isLoading ? (
                <li>
                  <Brain size={17} weight="duotone" aria-hidden="true" />
                  <span>还没有画像证据</span>
                </li>
              ) : null}
              {profileEvents.map((item) => (
                <li key={item.id}>
                  <Brain size={17} weight="duotone" aria-hidden="true" />
                  <span>
                    <strong>{item.change_summary}</strong>
                    <small>
                      {profileSourceLabel(item.source_type)} · {item.status === "candidate" ? "候选证据" : "已应用"}
                      {item.confidence_score !== null && item.confidence_score !== undefined
                        ? ` · ${Math.round(item.confidence_score * 100)}%`
                        : ""}
                    </small>
                    <AgentTraceDisclosure traceId={item.agent_trace_id} label="查看 ProfileGraph" />
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="student-panel profile-dialog-entry" role="region" aria-label="画像对话入口">
            <ChatCircleText size={24} weight="duotone" aria-hidden="true" />
            <div>
              <strong>回答几个问题，生成初始画像。</strong>
              <p>练习和错因会持续修正画像。</p>
            </div>
            <div className="profile-prompt-strip">
              <Compass size={17} weight="duotone" aria-hidden="true" />
              <span>下一问：{profile.next_question}</span>
            </div>
            <label className="profile-answer-box">
              <span>我的回答</span>
              <textarea
                rows={3}
                value={profileAnswer}
                aria-label="画像问题回答"
                onChange={(event) => setProfileAnswer(event.target.value)}
                placeholder="比如：最担心反向传播推导。"
              />
            </label>
            <button className="primary-action" type="button" onClick={submitProfileAnswer} disabled={updateProfileMutation.isPending}>
              更新画像
            </button>
          </section>
        </aside>
      </div>
    </PageFrame>
  );
}
