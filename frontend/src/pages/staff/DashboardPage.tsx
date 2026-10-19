import { Card } from "react-bootstrap";

import { useAuth } from "@/auth/AuthContext";

/** Placeholder — KPIs and charts arrive with the analytics module. */
export function DashboardPage() {
  const { user } = useAuth();
  return (
    <>
      <h1 className="h4 fw-bold">Welcome, {user?.full_name}</h1>
      <p className="text-secondary">
        {user?.role_display}
        {user?.department && ` · ${user.department}`}
        {user?.barangay && ` · ${user.barangay}`}
      </p>
      <Card body className="text-secondary">Dashboard widgets will appear here.</Card>
    </>
  );
}
