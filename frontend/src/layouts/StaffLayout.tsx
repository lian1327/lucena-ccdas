import { Container, Dropdown, Nav, Navbar } from "react-bootstrap";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";
import { APP_NAME } from "@/config";

type NavItem = { to: string; icon: string; label: string; ready: boolean; executiveOnly?: boolean };

const NAV: NavItem[] = [
  { to: "/staff", icon: "speedometer2", label: "Dashboard", ready: true },
  { to: "/staff/cases", icon: "inboxes", label: "Mga Kaso", ready: true },
  { to: "/staff/encode", icon: "pencil-square", label: "I-encode", ready: true },
  { to: "/staff/map", icon: "geo-alt", label: "GIS Map", ready: true },
  { to: "/staff/analytics", icon: "bar-chart", label: "Analytics", ready: false },
  { to: "/staff/executive", icon: "briefcase", label: "Executive", ready: false, executiveOnly: true },
];

export function StaffLayout() {
  const { user, logout, hasRole } = useAuth();
  const navigate = useNavigate();
  const isExec = hasRole("city_admin", "mayor");

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="d-flex flex-column min-vh-100 bg-body-tertiary">
      <Navbar bg="dark" data-bs-theme="dark" className="px-2">
        <Container fluid>
          <Navbar.Brand as={Link} to="/staff" className="fw-semibold">
            <i className="bi bi-megaphone-fill me-2" aria-hidden />
            {APP_NAME} <span className="fw-normal text-secondary small">Staff</span>
          </Navbar.Brand>
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
        </Container>
      </Navbar>

      <div className="d-flex flex-grow-1">
        <aside className="bg-white border-end p-2 d-none d-md-block" style={{ width: 220, flexShrink: 0 }}>
          <Nav className="flex-column gap-1">
            {NAV.filter((n) => !n.executiveOnly || isExec).map((n) =>
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
        <main className="flex-grow-1 p-3 p-md-4" style={{ minWidth: 0 }}>
          <Nav className="d-md-none mb-3 gap-1 flex-nowrap overflow-auto">
            {NAV.filter((n) => n.ready && (!n.executiveOnly || isExec)).map((n) => (
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
