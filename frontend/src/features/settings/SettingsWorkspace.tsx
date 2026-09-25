import { Robot } from "@phosphor-icons/react";

import { ToastStack } from "../../components/feedback/ToastStack";
import { PageFrame } from "../../pages/PageFrame";
import "../../styles/settings.css";
import { AccountSettingsSection } from "./AccountSettingsSection";
import { PersonalAnswerModelSettings } from "./PersonalAnswerModelSettings";
import { PrivacySettingsSection } from "./PrivacySettingsSection";
import { SettingsNavigation } from "./SettingsNavigation";
import { ModelUsageSettings } from "./ModelUsageSettings";
import type { SettingsController } from "./useSettingsController";

export function SettingsWorkspace(controller: SettingsController) {
  const {
    activeSection,
    dismissToast,
    effectiveChatReady,
    effectiveEmbeddingReady,
    effectiveGenerationReady,
    effectiveRerankReady,
    effectiveVisionReady,
    selectSection,
    toast
  } = controller;

  return (
    <PageFrame title="设置" titleMode="sr-only" variant="wide-workspace">
      <div className="settings-workspace">
        <header className="settings-toolbar">
          <div className="settings-toolbar-identity">
            <span aria-hidden="true"><Robot size={20} weight="duotone" /></span>
            <div><strong>系统设置</strong><small>学习账号与 AI 服务</small></div>
          </div>
          <div className="settings-effective-state" aria-label="当前 AI 服务状态">
            <span className={effectiveChatReady ? "ready" : "inactive"}>回答{effectiveChatReady ? "正常" : "未连接"}</span>
            <span className={effectiveGenerationReady ? "ready" : "inactive"}>生成{effectiveGenerationReady ? "正常" : "未连接"}</span>
            <span className={effectiveEmbeddingReady ? "ready" : "inactive"}>向量{effectiveEmbeddingReady ? "正常" : "未连接"}</span>
            <span className="ready">{effectiveRerankReady ? "重排序正常" : "融合排序"}</span>
            <span className={effectiveVisionReady ? "ready" : "inactive"}>图片理解{effectiveVisionReady ? "正常" : "未连接"}</span>
          </div>
        </header>

        <div className="settings-workspace-body">
          <SettingsNavigation activeSection={activeSection} onSelect={selectSection} />
          <main className="settings-content" aria-label="设置内容">
            {activeSection === "model" ? <PersonalAnswerModelSettings /> : null}
            {activeSection === "usage" ? <ModelUsageSettings /> : null}
            {activeSection === "account" ? <AccountSettingsSection {...controller} /> : null}
            {activeSection === "privacy" ? <PrivacySettingsSection /> : null}
          </main>
        </div>
        <ToastStack toast={toast} onDismiss={dismissToast} />
      </div>
    </PageFrame>
  );
}
