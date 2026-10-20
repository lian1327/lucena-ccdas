import { Navigate, useSearchParams } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";

import { AnalyticsPage } from "./AnalyticsPage";

/** City Admin / Mayor see all offices; a Department Head or receiving desk goes straight to their office. */
export default function AnalyticsHome() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  if (user && (user.role === "dept_head" || user.role === "office_desk") && user.department_id) {
    return <Navigate to={`/staff/analytics/${user.department_id}?${params}`} replace />;
  }
  return <AnalyticsPage />;
}
