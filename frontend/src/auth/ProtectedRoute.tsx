import { Navigate, Outlet, useLocation } from "react-router-dom";

import type { Role } from "@/api/types";
import { FullPageSpinner } from "@/components/FullPageSpinner";

import { useAuth } from "./AuthContext";

export function ProtectedRoute({ roles }: { roles?: Role[] }) {
  const { status, hasRole } = useAuth();
  const location = useLocation();

  if (status === "loading") return <FullPageSpinner />;
  if (status === "anonymous") {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (roles && !hasRole(...roles)) return <Navigate to="/forbidden" replace />;
  return <Outlet />;
}
