import { Container, Dropdown, Nav, Navbar } from "react-bootstrap";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { Seal } from "@/components/gov/Seal";
import { AlertBell } from "@/features/notifications/AlertBell";
import { useSite } from "@/site/useSite";
import { useAuth } from "@/auth/AuthContext";
import { APP_NAME, LGU_SEAL_SRC, LGU_SHORT } from "@/config";

import type { Role } from "@/api/types";

type NavItem = { to: string; icon: string; label: string; ready: boolean; executiveOnly?: boolean; roles?: Role[] };

const NAV: NavItem[] = [
  { to: "/staff", icon: "speedometer2", label: "Dashboard", ready: true },
  { to: "/staff/cases", icon: "inboxes", label: "Mga Kaso", ready: true },
  { to: "/staff/encode", icon: "pencil-square", label: "I-encode", ready: true },
  { to: "/staff/map", icon: "geo-alt", label: "GIS Map", ready: true },
  { to: "/staff/analytics", icon: "bar-chart", label: "Performance", ready: true,
    roles: ["city_admin", "mayor", "dept_head", "office_desk"] },
  { to: "/staff/accountability", icon: "shield-check", label: "Accountability", ready: true,
    roles: ["city_admin", "mayor", "dept_head", "division_chief"] },
  { to: "/staff/people/me", icon: "person-check", label: "Aking mga aksyon", ready: true,
    roles: ["pacd", "barangay", "office_desk", "dept_head", "division_chief", "dept_staff", "city_admin"] },
  { to: "/staff/notifications", icon: "chat-dots", label: "SMS / Abiso", ready: true, roles: ["city_admin", "mayor", "pacd"] },
  { to: "/staff/ml", icon: "stars", label: "AI Classifier", ready: true, roles: ["city_admin", "mayor", "pacd"] },
  { to: "/staff/executive", icon: "briefcase", label: "Executive", ready: true, executiveOnly: true },
];

export function StaffLayout() {
  const { user, logout, hasRole } = useAuth();
  const site = useSite();
  const navigate = useNavigate();
  const isExec = hasRole("city_admin", "mayor");
  const visible = (n: NavItem) => (!n.executiveOnly || isExec) && (!n.roles || hasRole(...n.roles));

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="d-flex flex-column min-vh-100 bg-body-tertiary">
      <a href="#staff-main" className="skip-link">Skip to content</a>
      <Navbar data-bs-theme="dark" className="px-2 staff-bar">
        <Container fluid>
          <Navbar.Brand as={Link} to="/staff" className="d-flex align-items-center gap-2">
            <Seal src={LGU_SEAL_SRC} alt={`${LGU_SHORT} seal`} size="sm" />
            <span className="lh-sm">
              <span className="d-block gov-head fw-bold text-white">{LGU_SHORT}</span>
              <span className="d-block small" style={{ color: "var(--sun)" }}>
                {APP_NAME} · Staff Portal{site.isPrototype && <span className="badge text-bg-warning ms-2">PROTOTYPE</span>}
              </span>
            </span>
          </Navbar.Brand>
          <div className="d-flex align-items-center">
          <AlertBell />
          <Dropdown align="end">
            <Dropdown.Toggle variant="outline-light" size="sm">
              <i className="bi bi-person-circle me-1" aria-hidden />
              {user?.full_name}
            </Dropdown.Toggle>
            <Dropdown.Menu>
              <Dropdown.Header>{user?.role_display}</Dropdown.Header>
              <Dropdown.Item as={Link} to="/">Public site</Dropdown.Item>
              <Dropdown.Divider />
              <Dropdown.Item onClick={onLogout}>Log out</Dropdown.Item>
            </Dropdown.Menu>
          </Dropdown>
          </div>
        </Container>
      </Navbar>

      <div className="d-flex flex-grow-1">
        <aside className="bg-white border-end p-2 d-none d-md-block d-print-none" style={{ width: 220, flexShrink: 0 }}>
          <Nav className="flex-column gap-1">
            {NAV.filter(visible).map((n) =>
              n.ready ? (
                <Nav.Link key={n.to} as={NavLink} to={n.to} end={n.to === "/staff"} className="rounded px-3">
                  <i className={`bi bi-${n.icon} me-2`} aria-hidden />
                  {n.label}
                </Nav.Link>
              ) : (
                <span key={n.to} className="nav-link text-secondary px-3 opacity-50" title="Coming soon">
                  <i className={`bi bi-${n.icon} me-2`} aria-hidden />
                  {n.label}
                </span>
              ),
            )}
          </Nav>
        </aside>
        <main id="staff-main" tabIndex={-1} className="flex-grow-1 p-3 p-md-4" style={{ minWidth: 0 }}>
          <Nav className="d-md-none d-print-none mb-3 gap-1 flex-nowrap overflow-auto">
            {NAV.filter((n) => n.ready && visible(n)).map((n) => (
              <Nav.Link key={n.to} as={NavLink} to={n.to} end={n.to === "/staff"} className="btn btn-sm btn-light border text-nowrap">
                <i className={`bi bi-${n.icon} me-1`} aria-hidden />
                {n.label}
              </Nav.Link>
            ))}
          </Nav>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
