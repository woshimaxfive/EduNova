import { Database, GearSix, Key, ShieldCheck, UserCircle } from "@phosphor-icons/react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { PageFrame } from "./PageFrame";

export function SettingsPage() {
  const { notice, showNotice } = useActionNotice();

  return (
    <PageFrame title="轻量系统设置" description="模型 Key、个人资料和数据导出入口会保持最小化，不扩展成后台。">
      <div className="settings-workspace">
        <section className="student-panel settings-section" role="region" aria-label="模型设置">
          <div className="settings-section-icon" aria-hidden="true">
            <GearSix size={22} weight="duotone" />
          </div>
          <div>
            <p className="section-kicker">模型</p>
            <h2>模型供应商配置</h2>
            <p>可切换默认模型、深度思考开关和联网搜索策略。真实 API Key 只保存到服务端安全配置。</p>
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
            <p className="section-kicker">隐私</p>
            <h2>隐私与数据边界</h2>
            <p>日志不能记录完整 API Key、密码、JWT、系统提示词或用户上传资料原文。</p>
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
            <p className="section-kicker">账号</p>
            <h2>学生账号</h2>
            <p>第一版只保留学生端身份、昵称和学习偏好，不加入教师端、支付或运营后台。</p>
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
