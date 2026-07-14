import { X } from "@phosphor-icons/react";
import { type ReactNode } from "react";
import { ModalFrame } from "../primitives/Dialog";

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
  const drawer = (
    <aside className="library-drawer" role={workspaceInteractive ? "region" : undefined} aria-label={title}>
      <header className="library-drawer-header">
        <h2>{title}</h2>
        <button type="button" aria-label={`关闭${title}`} onClick={onClose}>
          <X size={19} weight="bold" aria-hidden="true" />
        </button>
      </header>
      <div className="library-drawer-scroll">{children}</div>
      {footer ? <footer className="library-drawer-footer">{footer}</footer> : null}
    </aside>
  );

  if (!workspaceInteractive) {
    return <ModalFrame title={title} layerClassName="library-drawer-layer" testId="library-drawer-layer" onClose={onClose}>{drawer}</ModalFrame>;
  }

  return (
    <div className="library-drawer-layer workspace-interactive" data-testid="library-drawer-layer">
      {drawer}
    </div>
  );
}
