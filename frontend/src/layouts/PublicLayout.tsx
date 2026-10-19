import { Container, Nav, Navbar } from "react-bootstrap";
import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";
import { APP_NAME, LGU_NAME } from "@/config";

export function PublicLayout() {
  const { status, isStaff } = useAuth();

  return (
    <div className="d-flex flex-column min-vh-100">
      <Navbar expand="md" bg="white" className="border-bottom sticky-top" collapseOnSelect>
        <Container>
          <Navbar.Brand as={Link} to="/" className="d-flex align-items-center gap-2">
            <i className="bi bi-megaphone-fill text-primary" aria-hidden />
            <span className="fw-semibold">{APP_NAME}</span>
            <span className="d-none d-lg-inline text-secondary small border-start ps-2">{LGU_NAME}</span>
          </Navbar.Brand>
          <Navbar.Toggle aria-controls="public-nav" />
          <Navbar.Collapse id="public-nav">
            <Nav className="ms-auto align-items-md-center gap-md-1">
              <Nav.Link as={NavLink} to="/" end eventKey="home">Home</Nav.Link>
              <Nav.Link as={NavLink} to="/track" eventKey="track">Track a Concern</Nav.Link>
              {status === "authenticated" && isStaff ? (
                <Nav.Link as={NavLink} to="/staff" eventKey="staff">Staff Portal</Nav.Link>
              ) : (
                <Nav.Link as={NavLink} to="/login" eventKey="login">Staff Login</Nav.Link>
              )}
              <Link to="/report" className="btn btn-primary ms-md-2 mt-2 mt-md-0">
                <i className="bi bi-plus-circle me-1" aria-hidden />
                Report a Concern
              </Link>
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>

      <main className="flex-grow-1">
        <Outlet />
      </main>

      <footer className="border-top bg-light py-4 mt-5">
        <Container className="d-flex flex-column flex-md-row justify-content-between gap-2 small text-secondary">
          <span>© {new Date().getFullYear()} {LGU_NAME}</span>
          <span>
            <Link to="/privacy" className="link-secondary">Data Privacy Notice</Link>
          </span>
        </Container>
      </footer>
    </div>
  );
}
