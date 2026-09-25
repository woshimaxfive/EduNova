import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { changePassword, updateCurrentUser } from "../../api/auth";
import { getApiErrorMessage } from "../../api/errors";
import {
  clearConversationMemory,
  getPrivacySettings,
  listModelConfigs,
  getModelSettings,
  updatePrivacySettings
} from "../../api/settings";
import { PATHS } from "../../app/routePaths";
import { useToastQueue } from "../../components/feedback/useToastQueue";
import { mapApiUserToStudentUser } from "../auth/authMappers";
import { useAuthStore } from "../auth/authStore";
import type { SettingsSection } from "./SettingsNavigation";

const VALID_SECTIONS = new Set<SettingsSection>(["model", "usage", "account", "privacy"]);

export function useSettingsController() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const authUser = useAuthStore((state) => state.user);
  const authToken = useAuthStore((state) => state.token);
  const setSession = useAuthStore((state) => state.setSession);
  const clearSession = useAuthStore((state) => state.clearSession);
  const { toast, showToast, dismissToast } = useToastQueue();

  const requestedSection = searchParams.get("section") as SettingsSection | null;
  const activeSection = requestedSection && VALID_SECTIONS.has(requestedSection) ? requestedSection : "model";
  const [nickname, setNickname] = useState(authUser?.displayName ?? "");
  const [accountFeedback, setAccountFeedback] = useState<string | null>(null);
  const [passwordFeedback, setPasswordFeedback] = useState<string | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const modelConfigsQuery = useQuery({
    queryKey: ["settings", "model-configs"],
    queryFn: listModelConfigs,
    staleTime: 30_000
  });
  const modelSummaryQuery = useQuery({ queryKey: ["settings", "model"], queryFn: getModelSettings });
  const privacyQuery = useQuery({
    queryKey: ["settings", "privacy", authUser?.id],
    queryFn: getPrivacySettings,
    enabled: activeSection === "privacy"
  });

  const settingsList = modelConfigsQuery.data?.data ?? null;
  const configs = settingsList?.configs ?? [];
  const defaultChatConfigId = settingsList?.default_chat_config_id ?? settingsList?.default_config_id ?? null;
  const defaultGenerationConfigId = settingsList?.default_generation_config_id ?? null;
  const defaultEmbeddingConfigId = settingsList?.default_embedding_config_id ?? null;
  const defaultRerankConfigId = settingsList?.default_rerank_config_id ?? null;
  const defaultChatConfig = configs.find((config) => config.id === defaultChatConfigId) ?? null;
  const defaultGenerationConfig = configs.find((config) => config.id === defaultGenerationConfigId) ?? null;
  const defaultEmbeddingConfig = configs.find((config) => config.id === defaultEmbeddingConfigId) ?? null;
  const defaultRerankConfig = configs.find((config) => config.id === defaultRerankConfigId) ?? null;
  const systemSummary = settingsList?.system_summary ?? null;
  const effectiveChatReady = defaultChatConfig?.can_use_model ?? systemSummary?.can_use_model ?? false;
  const effectiveGenerationReady = defaultGenerationConfig?.can_use_model ?? effectiveChatReady;
  const effectiveEmbeddingReady = defaultEmbeddingConfig?.can_use_embedding_model
    ?? systemSummary?.can_use_embedding_model
    ?? false;
  const effectiveRerankReady = defaultRerankConfig?.can_use_rerank_model
    ?? systemSummary?.can_use_rerank_model
    ?? false;
  const effectiveVisionReady = Boolean(modelSummaryQuery.data?.data?.can_use_vision_model);
  const starterModeLabel = authUser?.starterMode === "data_structures" ? "数据结构与算法开始" : "空白开始";

  function selectSection(section: SettingsSection) {
    const next = new URLSearchParams(searchParams);
    if (section === "model") next.delete("section");
    else next.set("section", section);
    setSearchParams(next, { replace: true });
  }

  const updateAccountMutation = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: (response) => {
      if (authToken) {
        setSession({ token: authToken, user: mapApiUserToStudentUser(response.data) });
      }
      setNickname(response.data.display_name);
      setAccountFeedback(null);
      showToast("昵称已更新。", "success");
    },
    onError: (error) => setAccountFeedback(getApiErrorMessage(error, "昵称保存失败，请稍后重试。"))
  });

  const changePasswordMutation = useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      queryClient.clear();
      clearSession();
      navigate(PATHS.login, {
        replace: true,
        state: { notice: "密码已更新，请使用新密码重新登录。" }
      });
    },
    onError: (error) => setPasswordFeedback(getApiErrorMessage(error, "密码修改失败，请稍后重试。"))
  });

  const privacyMutation = useMutation({
    mutationFn: updatePrivacySettings,
    onSuccess: (response) => {
      queryClient.setQueryData(["settings", "privacy", authUser?.id], response);
      showToast(
        response.data.conversation_memory_enabled ? "跨会话记忆已开启。" : "跨会话记忆已暂停，已有记忆保留。",
        "success"
      );
    },
    onError: (error) => showToast(getApiErrorMessage(error, "隐私设置更新失败，请稍后重试。"), "warning")
  });

  const clearMemoryMutation = useMutation({
    mutationFn: clearConversationMemory,
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "privacy"] });
      showToast(`已清除 ${response.data.deleted_count} 条记忆，聊天记录仍保留。`, "success");
    },
    onError: (error) => showToast(getApiErrorMessage(error, "派生记忆清除失败，请稍后重试。"), "warning")
  });

  function saveNickname() {
    const value = nickname.trim();
    if (!value) {
      setAccountFeedback("昵称不能为空。");
      return;
    }
    updateAccountMutation.mutate({ display_name: value });
  }

  function submitPasswordChange() {
    setPasswordFeedback(null);
    if (!currentPassword || !newPassword || !confirmPassword) {
      setPasswordFeedback("请完整填写当前密码、新密码和确认密码。");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordFeedback("两次输入的新密码不一致。");
      return;
    }
    if (newPassword.length < 8 || !/[A-Za-z]/.test(newPassword) || !/\d/.test(newPassword)) {
      setPasswordFeedback("新密码至少 8 位，并同时包含字母和数字。");
      return;
    }
    changePasswordMutation.mutate({ current_password: currentPassword, new_password: newPassword });
  }

  return {
    accountFeedback,
    activeSection,
    authUser,
    changePasswordMutation,
    clearMemoryMutation,
    confirmPassword,
    currentPassword,
    dismissToast,
    effectiveChatReady,
    effectiveEmbeddingReady,
    effectiveGenerationReady,
    effectiveRerankReady,
    effectiveVisionReady,
    newPassword,
    nickname,
    passwordFeedback,
    privacyMutation,
    privacyQuery,
    saveNickname,
    selectSection,
    setAccountFeedback,
    setConfirmPassword,
    setCurrentPassword,
    setNewPassword,
    setNickname,
    starterModeLabel,
    submitPasswordChange,
    toast,
    updateAccountMutation
  };
}

export type SettingsController = ReturnType<typeof useSettingsController>;
