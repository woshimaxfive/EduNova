import { useEffect, useState } from "react";

const compactWorkspaceQuery = "(max-width: 900px)";

export function isCompactWorkspaceViewport() {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(compactWorkspaceQuery).matches
  );
}

export function useCompactWorkspaceViewport() {
  const [isCompactViewport, setIsCompactViewport] = useState(isCompactWorkspaceViewport);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return undefined;
    }

    const mediaQuery = window.matchMedia(compactWorkspaceQuery);
    const handleViewportChange = (event: MediaQueryListEvent) => setIsCompactViewport(event.matches);

    mediaQuery.addEventListener("change", handleViewportChange);
    return () => mediaQuery.removeEventListener("change", handleViewportChange);
  }, []);

  return isCompactViewport;
}

export function useResponsiveSidebarState() {
  const [isCollapsed, setIsCollapsed] = useState(isCompactWorkspaceViewport);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return undefined;
    }

    const mediaQuery = window.matchMedia(compactWorkspaceQuery);
    const handleViewportChange = (event: MediaQueryListEvent) => {
      if (event.matches) {
        setIsCollapsed(true);
      }
    };

    mediaQuery.addEventListener("change", handleViewportChange);
    return () => mediaQuery.removeEventListener("change", handleViewportChange);
  }, []);

  return [isCollapsed, setIsCollapsed] as const;
}
