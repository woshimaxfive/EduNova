import { Database, GearSix, Key, ShieldCheck, UserCircle } from "@phosphor-icons/react";
import { useState } from "react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { PageFrame } from "./PageFrame";

export function SettingsPage() {
  const [modelProvider, setModelProvider] = useState("OpenAI 兼容");
  const [deepThinking, setDeepThinking] = useState(true);
  const [webSearch, setWebSearch] = useState(false);
  const [nickname, setNickname] = useState("演示学生");
  const { notice, showNotice } = useActionNotice();

  function saveSettings() {
    showNotice(`${nickname || "学生"} 的设置已保存。`, "success");
  }

  return (
    <PageFrame title="设置">
      <div className="settings-workspace">
        <section className="student-panel settings-section" role="region" aria-label="模型设置">
          <div className="settings-section-icon" aria-hidden="true">
            <GearSix size={22} weight="duotone" />
          </div>
          <div>
            <h2>模型供应商配置</h2>
            <p>默认模型、深度思考和联网策略。</p>
            <div className="settings-form-row">
              <label>
                <span>供应商</span>
                <select value={modelProvider} onChange={(event) => setModelProvider(event.target.value)}>
                  <option>OpenAI 兼容</option>
                  <option>DeepSeek</option>
                  <option>本地模型</option>
                </select>
              </label>
              <label className="settings-toggle">
                <input type="checkbox" checked={deepThinking} onChange={(event) => setDeepThinking(event.target.checked)} />
                <span>深度思考</span>
              </label>
              <label className="settings-toggle">
                <input type="checkbox" checked={webSearch} onChange={(event) => setWebSearch(event.target.checked)} />
                <span>联网搜索</span>
              </label>
            </div>
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
            <label className="settings-inline-input">
              <span>昵称</span>
              <input value={nickname} onChange={(event) => setNickname(event.target.value)} />
            </label>
          </div>
          <div className="settings-action-stack">
            <button className="primary-action" type="button" onClick={saveSettings}>
              保存设置
            </button>
            <ActionNotice notice={notice} />
          </div>
        </section>
      </div>
    </PageFrame>
  );
}
