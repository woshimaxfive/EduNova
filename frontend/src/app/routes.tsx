import { lazy, Suspense, type ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "./ProtectedRoute";
import { PublicOnlyRoute } from "./PublicOnlyRoute";
import { PATHS } from "./routePaths";
import { useAuthStore } from "../features/auth/authStore";
import { LibraryPage } from "../pages/LibraryPage";
import { LearningPathPage } from "../pages/LearningPathPage";
import { LearningSpacePage } from "../pages/LearningSpacePage";
import { LoginPage } from "../pages/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PracticePage } from "../pages/PracticePage";
import { ProfilePage } from "../pages/ProfilePage";
import { RegisterPage } from "../pages/RegisterPage";
import { ReportsPage } from "../pages/ReportsPage";
import { SettingsPage } from "../pages/SettingsPage";
import { StudioPage } from "../pages/StudioPage";

const CourseSpacePage = lazy(() =>
  import("../pages/CourseSpacePage").then((module) => ({ default: module.CourseSpacePage }))
);

function RootRedirect() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  return <Navigate to={isAuthenticated ? PATHS.app : PATHS.login} replace />;
}

function protectedPage(element: ReactElement) {
  return <ProtectedRoute>{element}</ProtectedRoute>;
}

function publicPage(element: ReactElement) {
  return <PublicOnlyRoute>{element}</PublicOnlyRoute>;
}

function lazyPage(element: ReactElement) {
  return <Suspense fallback={<div className="route-loading" role="status">正在打开学习空间</div>}>{element}</Suspense>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path={PATHS.root} element={<RootRedirect />} />
      <Route path={PATHS.login} element={publicPage(<LoginPage />)} />
      <Route path={PATHS.register} element={publicPage(<RegisterPage />)} />
      <Route path={PATHS.app} element={protectedPage(<LearningSpacePage />)} />
      <Route path={PATHS.library} element={protectedPage(<LibraryPage />)} />
      <Route path={PATHS.path} element={protectedPage(<LearningPathPage />)} />
      <Route path={PATHS.courseDetail} element={protectedPage(lazyPage(<CourseSpacePage />))} />
      <Route path={PATHS.studio} element={protectedPage(<StudioPage />)} />
      <Route path={PATHS.profile} element={protectedPage(<ProfilePage />)} />
      <Route path="/app/tutor" element={protectedPage(<Navigate to={PATHS.app} replace />)} />
      <Route path={PATHS.practice} element={protectedPage(<PracticePage />)} />
      <Route path={PATHS.reports} element={protectedPage(<ReportsPage />)} />
      <Route path={PATHS.settings} element={protectedPage(<SettingsPage />)} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
