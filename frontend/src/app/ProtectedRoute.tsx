import { Navigate, useLocation } from "react-router-dom";
import { type PropsWithChildren } from "react";

import { useAuthStore } from "../features/auth/authStore";
import { PATHS } from "./routePaths";

export function ProtectedRoute({ children }: PropsWithChildren) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to={PATHS.login} replace state={{ from: location }} />;
  }

  return children;
}
