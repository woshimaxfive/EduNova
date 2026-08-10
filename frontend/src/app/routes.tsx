import { lazy, Suspense, type ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "./ProtectedRoute";
import { PublicOnlyRoute } from "./PublicOnlyRoute";
import { PATHS } from "./routePaths";
import { useAuthStore } from "../features/auth/authStore";
import { LearningSpacePage } from "../pages/LearningSpacePage";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { NotFoundPage } from "../pages/NotFoundPage";

const LibraryPage = lazy(() => import("../pages/LibraryPage").then((module) => ({ default: module.LibraryPage })));
const LearningPathPage = lazy(() => import("../pages/LearningPathPage").then((module) => ({ default: module.LearningPathPage })));
const PracticePage = lazy(() => import("../pages/PracticePage").then((module) => ({ default: module.PracticePage })));
const ProfilePage = lazy(() => import("../pages/ProfilePage").then((module) => ({ default: module.ProfilePage })));
const ReportsPage = lazy(() => import("../pages/ReportsPage").then((module) => ({ default: module.ReportsPage })));
const SettingsPage = lazy(() => import("../pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));
const StudioPage = lazy(() => import("../pages/StudioPage").then((module) => ({ default: module.StudioPage })));

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
      <Route path={PATHS.library} element={protectedPage(lazyPage(<LibraryPage />))} />
      <Route path={PATHS.path} element={protectedPage(lazyPage(<LearningPathPage />))} />
      <Route path={PATHS.coursePath} element={protectedPage(lazyPage(<LearningPathPage />))} />
      <Route path={PATHS.coursePractice} element={protectedPage(lazyPage(<PracticePage />))} />
      <Route path={PATHS.courseReports} element={protectedPage(lazyPage(<ReportsPage />))} />
      <Route path={PATHS.courseDetail} element={protectedPage(lazyPage(<CourseSpacePage />))} />
      <Route path={PATHS.studio} element={protectedPage(lazyPage(<StudioPage />))} />
      <Route path={PATHS.profile} element={protectedPage(lazyPage(<ProfilePage />))} />
      <Route path="/app/tutor" element={protectedPage(<Navigate to={PATHS.app} replace />)} />
      <Route path={PATHS.practice} element={protectedPage(lazyPage(<PracticePage />))} />
      <Route path={PATHS.reports} element={protectedPage(lazyPage(<ReportsPage />))} />
      <Route path={PATHS.settings} element={protectedPage(lazyPage(<SettingsPage />))} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
