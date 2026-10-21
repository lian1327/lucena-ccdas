import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";

import { FullPageSpinner } from "@/components/FullPageSpinner";

import { STAFF_ROLES } from "@/api/types";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import { PublicLayout } from "@/layouts/PublicLayout";
import { StaffLayout } from "@/layouts/StaffLayout";
import { LoginPage } from "@/pages/auth/LoginPage";
import { ForbiddenPage, NotFoundPage } from "@/pages/ErrorPages";
import { HomePage } from "@/pages/public/HomePage";
import { AboutPage } from "@/pages/public/AboutPage";
import { AccessibilityPage } from "@/pages/public/AccessibilityPage";
import { PrivacyPage } from "@/pages/public/PrivacyPage";
import { ReportPage } from "@/pages/public/ReportPage";
import { TrackPage } from "@/pages/public/TrackPage";
import { CaseDetailPage } from "@/pages/staff/CaseDetailPage";
import { CasesPage } from "@/pages/staff/CasesPage";
import { DashboardPage } from "@/pages/staff/DashboardPage";
import { EncodePage } from "@/pages/staff/EncodePage";

const MapPage = lazy(() => import("@/pages/staff/MapPage"));
const AnalyticsHome = lazy(() => import("@/pages/staff/AnalyticsHome"));
const OfficePerformance = lazy(() =>
  import("@/pages/staff/OfficePerformancePage").then((m) => ({ default: m.OfficePerformancePage })),
);
const AccountabilityPage = lazy(() => import("@/pages/staff/AccountabilityPage"));
const OfficePeoplePage = lazy(() => import("@/pages/staff/OfficePeoplePage"));
const LedgerPage = lazy(() => import("@/pages/staff/LedgerPage"));
const ExecutivePage = lazy(() => import("@/pages/staff/ExecutivePage"));
const ExecutiveReportPage = lazy(() => import("@/pages/staff/ExecutiveReportPage"));
const ClassifierPage = lazy(() => import("@/pages/staff/ClassifierPage"));
const NotificationsPage = lazy(() => import("@/pages/staff/NotificationsPage"));
const AccomplishmentPrintPage = lazy(() => import("@/pages/staff/AccomplishmentPrintPage"));
function AccountabilityHome() {
  const { user } = useAuth();
  if (user?.role === "division_chief" && user.department_id) return <Navigate to={`/staff/accountability/${user.department_id}`} replace />;
  return <AccountabilityPage />;
}
function ExecOnly({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  return user?.role === "city_admin" || user?.role === "mayor" ? <>{children}</> : <Navigate to="/staff" replace />;
}
const lazyEl = (el: React.ReactNode) => <Suspense fallback={<FullPageSpinner />}>{el}</Suspense>;

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/report", element: <ReportPage /> },
      { path: "/track", element: <TrackPage /> },
      { path: "/track/:ref", element: <TrackPage /> },
      { path: "/t/:ref", element: <TrackPage /> }, // short link used in SMS
      { path: "/privacy", element: <PrivacyPage /> },
      { path: "/about", element: <AboutPage /> },
      { path: "/accessibility", element: <AccessibilityPage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/forbidden", element: <ForbiddenPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
  {
    element: <ProtectedRoute roles={STAFF_ROLES} />,
    children: [
      {
        path: "/staff",
        element: <StaffLayout />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: "cases", element: <CasesPage /> },
          { path: "cases/:id", element: <CaseDetailPage /> },
          { path: "encode", element: <EncodePage /> },
          { path: "analytics", element: lazyEl(<AnalyticsHome />) },
          { path: "analytics/:id", element: lazyEl(<OfficePerformance />) },
          { path: "ml", element: lazyEl(<ClassifierPage />) },
          { path: "notifications", element: lazyEl(<NotificationsPage />) },
          { path: "executive", element: lazyEl(<ExecOnly><ExecutivePage /></ExecOnly>) },
          { path: "executive/report", element: lazyEl(<ExecOnly><ExecutiveReportPage /></ExecOnly>) },
          { path: "accountability", element: lazyEl(<AccountabilityHome />) },
          { path: "accountability/:id", element: lazyEl(<OfficePeoplePage />) },
          { path: "people/:id", element: lazyEl(<LedgerPage />) },
          { path: "cases/:id/accomplishment", element: lazyEl(<AccomplishmentPrintPage />) },
          { path: "map", element: <Suspense fallback={<FullPageSpinner label="Nilo-load ang mapa…" />}><MapPage /></Suspense> },
        ],
      },
    ],
  },
]);
