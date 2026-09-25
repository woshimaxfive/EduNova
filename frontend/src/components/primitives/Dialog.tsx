import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { type MouseEvent, type ReactNode, useEffect, useRef } from "react";
import "../../styles/dialog.css";

let modalLockCount = 0;
let bodyOverflowBeforeModal = "";

type ModalFrameProps = {
  title: string;
  layerClassName: string;
  children: ReactNode;
  onClose: () => void;
  dismissible?: boolean;
  testId?: string;
  preventEscapeClose?: boolean;
};

export function ModalFrame({
  title,
  layerClassName,
  children,
  onClose,
  dismissible = true,
  testId,
  preventEscapeClose = false
}: ModalFrameProps) {
  const restoreFocusRef = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null);

  useEffect(() => {
    const restoreFocus = restoreFocusRef.current;
    if (modalLockCount === 0) {
      bodyOverflowBeforeModal = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    modalLockCount += 1;
    return () => {
      modalLockCount = Math.max(0, modalLockCount - 1);
      if (modalLockCount === 0) document.body.style.overflow = bodyOverflowBeforeModal;
      if (restoreFocus?.isConnected) restoreFocus.focus();
    };
  }, []);

  function closeFromBackdrop(event: MouseEvent<HTMLDivElement>) {
    if (dismissible && event.target === event.currentTarget) onClose();
  }

  return (
    <DialogPrimitive.Root open onOpenChange={(open) => { if (!open && dismissible) onClose(); }}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Content
          className={layerClassName}
          data-testid={testId}
          aria-label={title}
          onMouseDown={closeFromBackdrop}
          onEscapeKeyDown={(event) => { if (!dismissible || preventEscapeClose) event.preventDefault(); }}
        >
          <DialogPrimitive.Title className="radix-visually-hidden">{title}</DialogPrimitive.Title>
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  layerClassName?: string;
  children?: ReactNode;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = "取消",
  layerClassName = "confirm-dialog-layer",
  children,
  onOpenChange,
  onConfirm
}: ConfirmDialogProps) {
  return (
    <AlertDialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialogPrimitive.Portal>
        <AlertDialogPrimitive.Content className={layerClassName}>
          <AlertDialogPrimitive.Title className="radix-visually-hidden">{title}</AlertDialogPrimitive.Title>
          <AlertDialogPrimitive.Description className="radix-visually-hidden">{description}</AlertDialogPrimitive.Description>
          {children ?? (
            <section>
              <h2>{title}</h2>
              <p>{description}</p>
              <div>
                <AlertDialogPrimitive.Cancel asChild><button type="button">{cancelLabel}</button></AlertDialogPrimitive.Cancel>
                <AlertDialogPrimitive.Action asChild><button type="button" onClick={onConfirm}>{confirmLabel}</button></AlertDialogPrimitive.Action>
              </div>
            </section>
          )}
        </AlertDialogPrimitive.Content>
      </AlertDialogPrimitive.Portal>
    </AlertDialogPrimitive.Root>
  );
}
