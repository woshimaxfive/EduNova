import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "./ProtectedRoute";
import { PublicOnlyRoute } from "./PublicOnlyRoute";
import { PATHS } from "./routePaths";
import { useAuthStore } from "../features/auth/authStore";
import { DemoEntryPage } from "../pages/DemoEntryPage";
import { LibraryPage } from "../pages/LibraryPage";
import { LearningSpacePage } from "../pages/LearningSpacePage";
import { LoginPage } from "../pages/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PracticePage } from "../pages/PracticePage";
import { ProfilePage } from "../pages/ProfilePage";
import { RegisterPage } from "../pages/RegisterPage";
import { ReportsPage } from "../pages/ReportsPage";
import { SettingsPage } from "../pages/SettingsPage";
import { StudioPage } from "../pages/StudioPage";
import { TutorPage } from "../pages/TutorPage";

function RootRedirect() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  return <Navigate to={isAuthenticated ? PATHS.app : PATHS.login} replace />;
}

function protectedPage(element: React.ReactElement) {
  return <ProtectedRoute>{element}</ProtectedRoute>;
}

function publicPage(element: React.ReactElement) {
  return <PublicOnlyRoute>{element}</PublicOnlyRoute>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path={PATHS.root} element={<RootRedirect />} />
      <Route path={PATHS.login} element={publicPage(<LoginPage />)} />
      <Route path={PATHS.register} element={publicPage(<RegisterPage />)} />
      <Route path={PATHS.demo} element={publicPage(<DemoEntryPage />)} />
      <Route path={PATHS.app} element={protectedPage(<LearningSpacePage />)} />
      <Route path={PATHS.library} element={protectedPage(<LibraryPage />)} />
      <Route path={PATHS.studio} element={protectedPage(<StudioPage />)} />
      <Route path={PATHS.profile} element={protectedPage(<ProfilePage />)} />
      <Route path={PATHS.tutor} element={protectedPage(<TutorPage />)} />
      <Route path={PATHS.practice} element={protectedPage(<PracticePage />)} />
      <Route path={PATHS.reports} element={protectedPage(<ReportsPage />)} />
      <Route path={PATHS.settings} element={protectedPage(<SettingsPage />)} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
