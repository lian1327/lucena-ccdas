import { createBrowserRouter } from "react-router-dom";

import { STAFF_ROLES } from "@/api/types";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import { PublicLayout } from "@/layouts/PublicLayout";
import { StaffLayout } from "@/layouts/StaffLayout";
import { LoginPage } from "@/pages/auth/LoginPage";
import { ForbiddenPage, NotFoundPage } from "@/pages/ErrorPages";
import { HomePage } from "@/pages/public/HomePage";
import { PrivacyPage } from "@/pages/public/PrivacyPage";
import { ReportPage } from "@/pages/public/ReportPage";
import { TrackPage } from "@/pages/public/TrackPage";
import { DashboardPage } from "@/pages/staff/DashboardPage";

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/report", element: <ReportPage /> },
      { path: "/track", element: <TrackPage /> },
      { path: "/track/:ref", element: <TrackPage /> },
      { path: "/privacy", element: <PrivacyPage /> },
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
        children: [{ index: true, element: <DashboardPage /> }],
      },
    ],
  },
]);
