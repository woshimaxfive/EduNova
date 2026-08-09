import { LockKey, UserCircle } from "@phosphor-icons/react";

import { InlineFeedback } from "../../components/feedback/InlineFeedback";
import type { SettingsController } from "./useSettingsController";

type AccountSettingsSectionProps = Pick<
  SettingsController,
  | "accountFeedback"
  | "authUser"
  | "changePasswordMutation"
  | "confirmPassword"
  | "currentPassword"
  | "newPassword"
  | "nickname"
  | "passwordFeedback"
  | "saveNickname"
  | "setAccountFeedback"
  | "setConfirmPassword"
  | "setCurrentPassword"
  | "setNewPassword"
  | "setNickname"
  | "starterModeLabel"
  | "submitPasswordChange"
  | "updateAccountMutation"
>;

export function AccountSettingsSection(props: AccountSettingsSectionProps) {
  const {
    accountFeedback,
    authUser,
    changePasswordMutation,
    confirmPassword,
    currentPassword,
    newPassword,
    nickname,
    passwordFeedback,
    saveNickname,
    setAccountFeedback,
    setConfirmPassword,
    setCurrentPassword,
    setNewPassword,
    setNickname,
    starterModeLabel,
    submitPasswordChange,
    updateAccountMutation
  } = props;

  return (
    <section className="settings-panel settings-account-panel" role="region" aria-label="账号设置">
      <header className="settings-panel-heading">
        <div><h2>账号安全</h2></div>
      </header>
      <div className="settings-account-grid">
        <section>
          <header>
            <UserCircle size={20} weight="duotone" />
            <div><strong>基本信息</strong><span>登录账号创建后不可修改</span></div>
          </header>
          <dl className="settings-account-meta">
            <div><dt>账号</dt><dd>{authUser?.account ?? "当前登录账号"}</dd></div>
            <div><dt>身份</dt><dd>{authUser?.role === "admin" ? "管理员" : "学生"}</dd></div>
            <div><dt>初始方式</dt><dd>{starterModeLabel}</dd></div>
          </dl>
          <label className="settings-account-field">
            <span>昵称</span>
            <input
              aria-label="昵称"
              value={nickname}
              onChange={(event) => {
                setNickname(event.target.value);
                setAccountFeedback(null);
              }}
            />
          </label>
          <InlineFeedback message={accountFeedback} tone="warning" className="settings-inline-feedback" />
          <button type="button" className="primary-action" onClick={saveNickname} disabled={updateAccountMutation.isPending}>
            {updateAccountMutation.isPending ? "保存中" : "保存昵称"}
          </button>
        </section>

        <section>
          <header>
            <LockKey size={20} weight="duotone" />
            <div><strong>修改密码</strong><span>修改后会退出所有已有登录状态</span></div>
          </header>
          <div className="settings-password-form">
            <label>
              <span>当前密码</span>
              <input aria-label="当前密码" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
            </label>
            <label>
              <span>新密码</span>
              <input aria-label="新密码" type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
            </label>
            <label>
              <span>确认新密码</span>
              <input aria-label="确认新密码" type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
            </label>
            <small>至少 8 位，并同时包含字母和数字。</small>
          </div>
          <InlineFeedback message={passwordFeedback} tone="warning" className="settings-inline-feedback" />
          <button type="button" className="primary-action" onClick={submitPasswordChange} disabled={changePasswordMutation.isPending}>
            {changePasswordMutation.isPending ? "更新中" : "更新密码并退出登录"}
          </button>
        </section>
      </div>
    </section>
  );
}
