import { SettingsWorkspace } from "../features/settings/SettingsWorkspace";
import { useSettingsController } from "../features/settings/useSettingsController";

export function SettingsPage() {
  const controller = useSettingsController();
  return <SettingsWorkspace {...controller} />;
}
