import { useState } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { AppSidebar, type SidebarConversation } from "./AppSidebar";

function installCompactViewport(initialMatches = true) {
  const changeListeners = new Set<(event: MediaQueryListEvent) => void>();
  const mediaQueryList = {
    matches: initialMatches,
    media: "(max-width: 900px)",
    onchange: null,
    addEventListener: vi.fn((type: string, listener: (event: MediaQueryListEvent) => void) => {
      if (type === "change") {
        changeListeners.add(listener);
      }
    }),
    removeEventListener: vi.fn((type: string, listener: (event: MediaQueryListEvent) => void) => {
      if (type === "change") {
        changeListeners.delete(listener);
      }
    }),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn()
  } as unknown as MediaQueryList;
  const matchMedia = vi.fn(() => mediaQueryList);

  vi.stubGlobal("matchMedia", matchMedia);
  return {
    matchMedia,
    setCompactViewport(matches: boolean) {
      act(() => {
        (mediaQueryList as { matches: boolean }).matches = matches;
        changeListeners.forEach((listener) => listener({ matches } as MediaQueryListEvent));
      });
    }
  };
}

type StatefulSidebarProps = {
  conversations?: SidebarConversation[];
  onToggle?: () => void;
};

function StatefulSidebar({ conversations, onToggle }: StatefulSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <MemoryRouter>
      <AppSidebar
        isCollapsed={isCollapsed}
        conversations={conversations}
        onToggleCollapsed={() => {
          onToggle?.();
          setIsCollapsed((current) => !current);
        }}
      />
    </MemoryRouter>
  );
}

afterEach(() => {
  document.body.style.overflow = "";
  vi.unstubAllGlobals();
});

it("在紧凑视口点击侧栏导航后请求收起抽屉", async () => {
  const viewport = installCompactViewport();
  const onToggleCollapsed = vi.fn();

  render(
    <MemoryRouter>
      <AppSidebar isCollapsed={false} onToggleCollapsed={onToggleCollapsed} />
    </MemoryRouter>
  );

  await userEvent.click(screen.getByRole("link", { name: "资料库" }));

  expect(viewport.matchMedia).toHaveBeenCalledWith("(max-width: 900px)");
  expect(onToggleCollapsed).toHaveBeenCalledTimes(1);
});

it("在紧凑视口完成新建对话和历史选择后请求收起抽屉", async () => {
  installCompactViewport();
  const onToggleCollapsed = vi.fn();
  const onNewChat = vi.fn();
  const onSelectConversation = vi.fn();

  render(
    <MemoryRouter>
      <AppSidebar
        isCollapsed={false}
        conversations={[{ id: "thread-1", title: "复习计划", meta: "刚刚" }]}
        onToggleCollapsed={onToggleCollapsed}
        onNewChat={onNewChat}
        onSelectConversation={onSelectConversation}
      />
    </MemoryRouter>
  );

  await userEvent.click(screen.getByRole("button", { name: "新建对话" }));
  await userEvent.click(screen.getByRole("button", { name: /复习计划/ }));

  expect(onNewChat).toHaveBeenCalledTimes(1);
  expect(onSelectConversation).toHaveBeenCalledWith({ id: "thread-1", title: "复习计划", meta: "刚刚" });
  expect(onToggleCollapsed).toHaveBeenCalledTimes(2);
});

it("历史搜索会真实收起紧凑抽屉并保持完整模态行为", async () => {
  installCompactViewport();
  const onToggle = vi.fn();
  render(<StatefulSidebar onToggle={onToggle} />);

  await userEvent.click(screen.getByRole("button", { name: "搜索历史" }));

  expect(onToggle).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("dialog", { name: "工作区导航" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "关闭工作区导航" })).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "搜索历史" })).toBeInTheDocument();
  const searchInput = screen.getByRole("searchbox", { name: "搜索历史关键词" });
  expect(searchInput).toHaveFocus();
  expect(document.body.style.overflow).toBe("hidden");

  screen.getByRole("button", { name: "关闭搜索历史" }).focus();
  await userEvent.tab();
  expect(searchInput).toHaveFocus();

  await userEvent.keyboard("{Escape}");
  await waitFor(() => {
    expect(screen.queryByRole("dialog", { name: "搜索历史" })).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
    expect(screen.getByRole("button", { name: "展开侧栏" })).toHaveFocus();
  });
});

it("紧凑抽屉锁定滚动、约束焦点并在 Escape 后恢复触发点", async () => {
  installCompactViewport();
  const onToggle = vi.fn();
  render(<StatefulSidebar onToggle={onToggle} />);

  expect(document.body.style.overflow).toBe("hidden");
  expect(screen.getByRole("dialog", { name: "工作区导航" })).toBeInTheDocument();

  screen.getByRole("button", { name: "退出登录" }).focus();
  await userEvent.tab();
  expect(screen.getByRole("link", { name: "EduNova 首页" })).toHaveFocus();

  await userEvent.keyboard("{Escape}");
  await waitFor(() => {
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog", { name: "工作区导航" })).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
    expect(screen.getByRole("button", { name: "展开侧栏" })).toHaveFocus();
  });
});

it("点击紧凑抽屉遮罩后关闭抽屉并恢复滚动", async () => {
  installCompactViewport();
  const onToggle = vi.fn();
  render(<StatefulSidebar onToggle={onToggle} />);

  await userEvent.click(screen.getByRole("button", { name: "关闭工作区导航" }));

  await waitFor(() => {
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog", { name: "工作区导航" })).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
  });
});

it("抽屉打开后切换到桌面视口会清理移动模态副作用", async () => {
  const viewport = installCompactViewport();
  render(
    <MemoryRouter>
      <AppSidebar isCollapsed={false} onToggleCollapsed={vi.fn()} />
    </MemoryRouter>
  );

  expect(screen.getByRole("dialog", { name: "工作区导航" })).toBeInTheDocument();
  expect(document.body.style.overflow).toBe("hidden");

  viewport.setCompactViewport(false);

  await waitFor(() => {
    expect(screen.queryByRole("dialog", { name: "工作区导航" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "关闭工作区导航" })).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
  });
});

it("重命名输入框消费 Escape 时不会连带关闭紧凑抽屉", async () => {
  installCompactViewport();
  const onToggleCollapsed = vi.fn();
  render(
    <MemoryRouter>
      <AppSidebar
        isCollapsed={false}
        conversations={[{ id: "thread-1", title: "复习计划", meta: "刚刚" }]}
        onToggleCollapsed={onToggleCollapsed}
        onRenameConversation={vi.fn()}
      />
    </MemoryRouter>
  );

  await userEvent.click(screen.getByRole("button", { name: "打开会话操作菜单 thread-1" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "重命名" }));
  expect(screen.getByRole("textbox", { name: "会话名称" })).toHaveFocus();

  await userEvent.keyboard("{Escape}");

  expect(screen.queryByRole("textbox", { name: "会话名称" })).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "工作区导航" })).toBeInTheDocument();
  expect(onToggleCollapsed).not.toHaveBeenCalled();
});
