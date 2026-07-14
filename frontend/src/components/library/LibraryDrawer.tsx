import { X } from "@phosphor-icons/react";
import { type ReactNode, useEffect } from "react";

type LibraryDrawerProps = {
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  workspaceInteractive?: boolean;
  onClose: () => void;
};

export function LibraryDrawer({
  title,
  children,
  footer,
  workspaceInteractive = false,
  onClose,
}: LibraryDrawerProps) {
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className={`library-drawer-layer${workspaceInteractive ? " workspace-interactive" : ""}`} role="presentation" data-testid="library-drawer-layer" onMouseDown={(event) => {
      if (!workspaceInteractive && event.target === event.currentTarget) onClose();
    }}>
      <aside className="library-drawer" role="dialog" aria-modal={workspaceInteractive ? undefined : "true"} aria-label={title}>
        <header className="library-drawer-header">
          <h2>{title}</h2>
          <button type="button" aria-label={`关闭${title}`} onClick={onClose}>
            <X size={19} weight="bold" aria-hidden="true" />
          </button>
        </header>
        <div className="library-drawer-scroll">{children}</div>
        {footer ? <footer className="library-drawer-footer">{footer}</footer> : null}
      </aside>
    </div>
  );
}
