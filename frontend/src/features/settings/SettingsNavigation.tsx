import { ChartBar, Database, Robot, UserCircle } from "@phosphor-icons/react";

export type SettingsSection = "model" | "usage" | "account" | "privacy";

type SettingsNavigationProps = {
  activeSection: SettingsSection;
  onSelect: (section: SettingsSection) => void;
};

const ITEMS = [
  {
    id: "model" as const,
    label: "AI 服务",
    description: "回答、检索与排序",
    icon: Robot
  },
  {
    id: "usage" as const,
    label: "模型用量",
    description: "调用、缓存与估算费用",
    icon: ChartBar
  },
  {
    id: "account" as const,
    label: "账号安全",
    description: "昵称与登录密码",
    icon: UserCircle
  },
  {
    id: "privacy" as const,
    label: "数据隐私",
    description: "资料与轨迹边界",
    icon: Database
  }
] as const;

export function SettingsNavigation({ activeSection, onSelect }: SettingsNavigationProps) {
  return (
    <nav className="settings-navigation" aria-label="设置分类">
      <div className="settings-navigation-heading">
        <span>设置中心</span>
        <strong>按需管理</strong>
      </div>
      {ITEMS.map((item) => {
        const Icon = item.icon;
        const active = activeSection === item.id;
        return (
          <button
            key={item.id}
            type="button"
            aria-current={active ? "page" : undefined}
            onClick={() => onSelect(item.id)}
          >
            <Icon size={19} weight={active ? "fill" : "duotone"} aria-hidden="true" />
            <span>
              <strong>{item.label}</strong>
              <small>{item.description}</small>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
