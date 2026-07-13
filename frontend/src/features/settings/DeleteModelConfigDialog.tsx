import * as Dialog from "@radix-ui/react-dialog";
import { Trash, X } from "@phosphor-icons/react";

type DeleteModelConfigDialogProps = {
  open: boolean;
  configName: string;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
};

export function DeleteModelConfigDialog({
  open,
  configName,
  pending,
  onOpenChange,
  onConfirm
}: DeleteModelConfigDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="settings-dialog-overlay" />
        <Dialog.Content className="settings-dialog" aria-describedby="settings-delete-description">
          <header>
            <span aria-hidden="true"><Trash size={20} weight="duotone" /></span>
            <div>
              <Dialog.Title>删除模型配置</Dialog.Title>
              <Dialog.Description id="settings-delete-description">
                删除“{configName}”后无法恢复；如果它是默认配置，系统会切换到下一套个人配置或系统默认服务。
              </Dialog.Description>
            </div>
            <Dialog.Close className="settings-dialog-close" aria-label="关闭删除确认">
              <X size={18} weight="bold" />
            </Dialog.Close>
          </header>
          <footer>
            <Dialog.Close className="secondary-action" disabled={pending}>取消</Dialog.Close>
            <button className="settings-danger-button" type="button" onClick={onConfirm} disabled={pending}>
              {pending ? "删除中" : "确认删除"}
            </button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
