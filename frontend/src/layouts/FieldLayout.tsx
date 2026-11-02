import { Badge, Button, Offcanvas } from "react-bootstrap";
import { useEffect, useState } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";
import { useSite } from "@/site/useSite";
import { useOutbox } from "@/features/field/useOutbox";
import { fmtDateTime } from "@/utils/format";

/** Phone-first shell for field crews: big targets, connection status, and the outbox of unsent work. */
export function FieldLayout() {
  const { user, logout } = useAuth();
  const site = useSite();
  const navigate = useNavigate();
  const { items, pending, online, sending, flush, discard } = useOutbox({ autoFlush: true });
  const [show, setShow] = useState(false);
  const mine = items.filter((i) => i.userId === user?.id);
  useInstallable();

  const onLogout = async () => {
    if (pending && !window.confirm(`May ${pending} na hindi pa naipapadala. Hindi ito maipapadala hangga't hindi ka nag-login ulit. Mag-logout pa rin?`)) return;
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="field-app">
      <header className="field-bar">
        <Link to="/field" className="field-brand">
          <i className="bi bi-cone-striped me-2" aria-hidden />
          Field
          {site.isPrototype && <Badge bg="warning" text="dark" className="ms-2 fw-normal">PROTOTYPE</Badge>}
        </Link>
        <div className="d-flex align-items-center gap-2">
          <button type="button" className={`field-net ${online ? "on" : "off"}`} onClick={() => setShow(true)}
            aria-label={`${online ? "May signal" : "Walang signal"}. ${pending} hindi pa naipapadala.`}>
            <i className={`bi bi-${online ? "wifi" : "wifi-off"}`} aria-hidden />
            {pending > 0 && <span className="field-net-count">{pending}</span>}
          </button>
          <Button variant="link" className="text-white p-1" onClick={onLogout} aria-label="Mag-logout">
            <i className="bi bi-box-arrow-right fs-5" aria-hidden />
          </Button>
        </div>
      </header>
      {!online && (
        <div className="field-offline" role="status">
          Walang signal. Puwede pa ring mag-check in, kumuha ng litrato at mag-report; ipapadala ito pagbalik ng signal.
        </div>
      )}
      <main className="field-main">
        <Outlet />
      </main>
      <footer className="field-foot">
        {user && <span>{user.first_name || user.username}</span>}
        <Link to="/staff">Buong staff site</Link>
      </footer>

      <Offcanvas show={show} onHide={() => setShow(false)} placement="bottom" className="field-sheet">
        <Offcanvas.Header closeButton>
          <Offcanvas.Title className="h6 mb-0">Hindi pa naipapadala</Offcanvas.Title>
        </Offcanvas.Header>
        <Offcanvas.Body>
          {mine.length === 0 && <p className="text-secondary mb-0">Naipadala na lahat.</p>}
          <ul className="list-unstyled mb-3">
            {mine.map((i) => (
              <li key={i.id} className="border-bottom py-2">
                <div className="fw-semibold">{i.label} · {i.ref}</div>
                <div className="small text-secondary">Na-save {fmtDateTime(i.createdAt)}</div>
                {i.error && (
                  <div className="small text-danger mt-1">
                    Hindi tinanggap ng server: {i.error}{" "}
                    <Button variant="link" size="sm" className="p-0 text-danger" onClick={() => void discard(i.id)}>Alisin</Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
          {pending > 0 && (
            <Button className="w-100" size="lg" disabled={!online || sending} onClick={() => void flush()}>
              {sending ? "Ipinapadala…" : online ? "Ipadala ngayon" : "Hinihintay ang signal"}
            </Button>
          )}
        </Offcanvas.Body>
      </Offcanvas>
    </div>
  );
}

/**
 * Makes the field view installable ("Add to Home Screen") and able to open without signal.
 * Only here, so the citizen portal is not offered as an app. The service worker runs only in production builds.
 */
function useInstallable() {
  useEffect(() => {
    if (!document.querySelector('link[rel="manifest"]')) {
      const link = document.createElement("link");
      link.rel = "manifest";
      link.href = "/manifest.webmanifest";
      document.head.appendChild(link);
    }
    if (import.meta.env.PROD && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    }
  }, []);
}
