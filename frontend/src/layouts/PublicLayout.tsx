import { Container, Nav, Navbar } from "react-bootstrap";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";

import { useAuth } from "@/auth/AuthContext";
import { GovphBar } from "@/components/gov/GovphBar";
import { Seal } from "@/components/gov/Seal";
import { SiteFooter } from "@/components/gov/SiteFooter";
import { LGU_PROVINCE, LGU_SEAL_SRC, LGU_SHORT } from "@/config";

function ScrollToHash() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView();
    else window.scrollTo(0, 0);
  }, [pathname, hash]);
  return null;
}

export function PublicLayout() {
  const { status, isStaff } = useAuth();

  return (
    <div className="d-flex flex-column min-vh-100">
      <a href="#main" className="skip-link">Lumaktaw sa nilalaman</a>
      <ScrollToHash />
      <GovphBar />

      <header className="masthead">
        <Container className="d-flex align-items-center gap-3 py-3">
          <Link to="/" className="d-flex align-items-center gap-3">
            <Seal src={LGU_SEAL_SRC} alt={`Opisyal na selyo ng ${LGU_SHORT}`} />
            <span>
              <span className="lgu-line d-block">Republika ng Pilipinas · {LGU_PROVINCE}</span>
              <span className="lgu-name d-block">{LGU_SHORT}</span>
              <span className="portal-name d-block">Citizen Concern Portal</span>
            </span>
          </Link>
        </Container>
      </header>

      <Navbar expand="md" className="site-nav sticky-top p-0" collapseOnSelect>
        <Container>
          <Navbar.Toggle aria-controls="public-nav" className="my-2">
            <i className="bi bi-list me-1" aria-hidden />Menu
          </Navbar.Toggle>
          <Navbar.Collapse id="public-nav">
            <Nav className="me-auto">
              <Nav.Link as={NavLink} to="/" end eventKey="home">Home</Nav.Link>
              <Nav.Link as={NavLink} to="/report" eventKey="report">Mag-report</Nav.Link>
              <Nav.Link as={NavLink} to="/track" eventKey="track">Subaybayan</Nav.Link>
              <Nav.Link as={NavLink} to="/about" eventKey="about">Citizen's Charter</Nav.Link>
            </Nav>
            <Nav className="pb-2 pb-md-0">
              {status === "authenticated" && isStaff ? (
                <Nav.Link as={NavLink} to="/staff" eventKey="staff"><i className="bi bi-person-badge me-1" aria-hidden />Staff Portal</Nav.Link>
              ) : (
                <Nav.Link as={NavLink} to="/login" eventKey="login"><i className="bi bi-box-arrow-in-right me-1" aria-hidden />Staff login</Nav.Link>
              )}
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>

      <main id="main" tabIndex={-1} className="flex-grow-1">
        <Outlet />
      </main>

      <SiteFooter />
    </div>
  );
}
