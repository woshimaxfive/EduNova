import { GearSix, ShieldCheck } from "@phosphor-icons/react";

import { PageFrame } from "./PageFrame";

export function SettingsPage() {
  return (
    <PageFrame kicker="设置" title="轻量系统设置" description="模型 Key、个人资料和数据导出入口会保持最小化，不扩展成后台。">
      <div className="settings-panel">
        <GearSix size={24} weight="duotone" aria-hidden="true" />
        <div>
          <strong>模型供应商配置</strong>
          <p>真实 API Key 不会写入仓库，界面和日志只展示脱敏信息。</p>
        </div>
        <ShieldCheck size={22} weight="duotone" aria-hidden="true" />
      </div>
    </PageFrame>
  );
}
