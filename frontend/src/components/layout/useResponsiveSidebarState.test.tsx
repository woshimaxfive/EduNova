import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { useCompactWorkspaceViewport, useResponsiveSidebarState } from "./useResponsiveSidebarState";

function installMatchMedia(initialMatches: boolean) {
  let changeListener: ((event: MediaQueryListEvent) => void) | null = null;
  const removeEventListener = vi.fn();
  const mediaQueryList = {
    matches: initialMatches,
    media: "(max-width: 900px)",
    onchange: null,
    addEventListener: vi.fn((_type: string, listener: (event: MediaQueryListEvent) => void) => {
      changeListener = listener;
    }),
    removeEventListener,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn()
  } as unknown as MediaQueryList;

  const matchMedia = vi.fn(() => mediaQueryList);
  vi.stubGlobal("matchMedia", matchMedia);

  return {
    matchMedia,
    removeEventListener,
    enterCompactViewport() {
      act(() => {
        (mediaQueryList as { matches: boolean }).matches = true;
        changeListener?.({ matches: true } as MediaQueryListEvent);
      });
    },
    leaveCompactViewport() {
      act(() => {
        (mediaQueryList as { matches: boolean }).matches = false;
        changeListener?.({ matches: false } as MediaQueryListEvent);
      });
    }
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

it("在紧凑视口首次渲染时默认收起工作区侧栏", () => {
  const viewport = installMatchMedia(true);

  const { result, unmount } = renderHook(() => useResponsiveSidebarState());

  expect(result.current[0]).toBe(true);
  expect(viewport.matchMedia).toHaveBeenCalledWith("(max-width: 900px)");
  unmount();
  expect(viewport.removeEventListener).toHaveBeenCalledWith("change", expect.any(Function));
});

it("从桌面进入紧凑视口时自动收起工作区侧栏", () => {
  const viewport = installMatchMedia(false);
  const { result } = renderHook(() => useResponsiveSidebarState());

  expect(result.current[0]).toBe(false);
  viewport.enterCompactViewport();
  expect(result.current[0]).toBe(true);
});

it("紧凑视口状态会响应桌面与移动断点的双向变化", () => {
  const viewport = installMatchMedia(true);
  const { result } = renderHook(() => useCompactWorkspaceViewport());

  expect(result.current).toBe(true);
  viewport.leaveCompactViewport();
  expect(result.current).toBe(false);
  viewport.enterCompactViewport();
  expect(result.current).toBe(true);
});
