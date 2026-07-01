import { Navigate } from "react-router-dom";
import { type PropsWithChildren } from "react";

import { useAuthStore } from "../features/auth/authStore";
import { PATHS } from "./routePaths";

export function PublicOnlyRoute({ children }: PropsWithChildren) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (isAuthenticated) {
    return <Navigate to={PATHS.app} replace />;
  }

  return children;
}
