import { Database, GearSix, Key, ShieldCheck, UserCircle } from "@phosphor-icons/react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { PageFrame } from "./PageFrame";

export function SettingsPage() {
  const { notice, showNotice } = useActionNotice();

  return (
    <PageFrame title="设置" description="账号、模型和隐私边界。">
      <div className="settings-workspace">
        <section className="student-panel settings-section" role="region" aria-label="模型设置">
          <div className="settings-section-icon" aria-hidden="true">
            <GearSix size={22} weight="duotone" />
          </div>
          <div>
            <h2>模型供应商配置</h2>
            <p>默认模型、深度思考和联网策略。</p>
          </div>
          <span className="masked-value">
            <Key size={16} weight="duotone" aria-hidden="true" />
            sk-••••••••
          </span>
        </section>

        <section className="student-panel settings-section" role="region" aria-label="隐私与数据">
          <div className="settings-section-icon" aria-hidden="true">
            <ShieldCheck size={22} weight="duotone" />
          </div>
          <div>
            <h2>隐私与数据边界</h2>
            <p>不记录密钥、密码、提示词或资料原文。</p>
          </div>
          <span className="settings-status">
            <Database size={16} weight="duotone" aria-hidden="true" />
            本地演示数据
          </span>
        </section>

        <section className="student-panel settings-section" role="region" aria-label="账号设置">
          <div className="settings-section-icon" aria-hidden="true">
            <UserCircle size={22} weight="duotone" />
          </div>
          <div>
            <h2>学生账号</h2>
            <p>学生身份、昵称和学习偏好。</p>
          </div>
          <div className="settings-action-stack">
            <button className="primary-action" type="button" onClick={() => showNotice("设置已保存为本地演示态。", "success")}>
              保存设置
            </button>
            <ActionNotice notice={notice} />
          </div>
        </section>
      </div>
    </PageFrame>
  );
}
