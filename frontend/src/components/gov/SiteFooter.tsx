import { Link } from "react-router-dom";

import {
  GOVPH_SEAL_SRC, HOTLINES, LGU_ADDRESS, LGU_EMAIL, LGU_FACEBOOK, LGU_NAME, LGU_PHONE, LGU_PROVINCE,
  LGU_SEAL_SRC, LGU_SHORT, LGU_WEBSITE,
} from "@/config";

import { Seal } from "./Seal";

/** Set VITE_MAP_CREDIT to name the barangay/purok boundary source alongside OpenStreetMap. */
const MAP_CREDIT = import.meta.env.VITE_MAP_CREDIT ?? "Map data © OpenStreetMap contributors.";

const ABOUT_GOVPH = [
  ["GOV.PH", "https://www.gov.ph"],
  ["Open Data Portal", "https://data.gov.ph"],
  ["Official Gazette", "https://www.officialgazette.gov.ph"],
];
const GOV_LINKS = [
  ["Office of the President", "https://www.president.gov.ph"],
  ["Office of the Vice President", "https://www.ovp.gov.ph"],
  ["Senate of the Philippines", "https://www.senate.gov.ph"],
  ["House of Representatives", "https://www.congress.gov.ph"],
  ["Supreme Court", "https://sc.judiciary.gov.ph"],
  ["Court of Appeals", "https://ca.judiciary.gov.ph"],
  ["Sandiganbayan", "https://sb.judiciary.gov.ph"],
];

const ext = { target: "_blank", rel: "noreferrer" } as const;

/** LGU contact block on top, then the standard Government Website Template footer. */
export function SiteFooter() {
  return (
    <footer>
      <div className="lgu-footer py-5">
        <div className="container">
          <div className="row g-4">
            <div className="col-lg-5">
              <div className="d-flex align-items-center gap-3 mb-3">
                <Seal src={LGU_SEAL_SRC} alt={`Opisyal na selyo ng ${LGU_SHORT}`} size="sm" />
                <div>
                  <div className="fw-bold text-white">{LGU_NAME}</div>
                  <div className="small">{LGU_PROVINCE}</div>
                </div>
              </div>
              <p className="mb-2">
                Citizen Concern Portal: iulat ang mga problema sa komunidad at subaybayan ang aksyon ng
                lungsod hanggang maayos.
              </p>
              <ul className="small">
                {LGU_ADDRESS && <li><i className="bi bi-geo-alt me-2" aria-hidden />{LGU_ADDRESS}</li>}
                {LGU_PHONE && <li><i className="bi bi-telephone me-2" aria-hidden /><a href={`tel:${LGU_PHONE.replace(/[^\d+]/g, "")}`}>{LGU_PHONE}</a></li>}
                {LGU_EMAIL && <li><i className="bi bi-envelope me-2" aria-hidden /><a href={`mailto:${LGU_EMAIL}`}>{LGU_EMAIL}</a></li>}
                {LGU_WEBSITE && <li><i className="bi bi-globe me-2" aria-hidden /><a href={LGU_WEBSITE} {...ext}>Opisyal na website</a></li>}
                {LGU_FACEBOOK && <li><i className="bi bi-facebook me-2" aria-hidden /><a href={LGU_FACEBOOK} {...ext}>Facebook page</a></li>}
              </ul>
            </div>
            <div className="col-6 col-lg-2">
              <h2>Portal</h2>
              <ul>
                <li><Link to="/report">Mag-report</Link></li>
                <li><Link to="/track">Subaybayan</Link></li>
                <li><Link to="/about">Citizen's Charter</Link></li>
                <li><Link to="/about#faq">Mga tanong (FAQ)</Link></li>
                <li><Link to="/login">Staff login</Link></li>
              </ul>
            </div>
            <div className="col-6 col-lg-2">
              <h2>Patakaran</h2>
              <ul>
                <li><Link to="/privacy">Data Privacy Notice</Link></li>
                <li><Link to="/accessibility">Accessibility</Link></li>
                <li><a href="https://www.foi.gov.ph" {...ext}>Freedom of Information</a></li>
                <li><a href="https://arta.gov.ph" {...ext}>ARTA</a></li>
                <li><a href="https://privacy.gov.ph" {...ext}>National Privacy Commission</a></li>
              </ul>
            </div>
            <div className="col-lg-3">
              <h2>Hotlines</h2>
              <ul>
                {HOTLINES.map((h) => (
                  <li key={h.number + h.label}>
                    <a href={`tel:${h.number.replace(/[^\d+]/g, "")}`} className="fw-bold">{h.number}</a>
                    <span className="ms-2">{h.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div className="gwt-footer py-4">
        <div className="container">
          <div className="row g-4">
            <div className="col-md-4 d-flex gap-3">
              <Seal src={GOVPH_SEAL_SRC} alt="Republic of the Philippines seal" size="sm" />
              <div>
                <h2>Republic of the Philippines</h2>
                <p className="mb-0">All content is in the public domain unless otherwise stated.</p>
              </div>
            </div>
            <div className="col-md-4">
              <h2>About GOVPH</h2>
              <p>Learn more about the Philippine government, its structure, how government works and the people behind it.</p>
              <ul>{ABOUT_GOVPH.map(([l, u]) => <li key={u}><a href={u} {...ext}>{l}</a></li>)}</ul>
            </div>
            <div className="col-md-4">
              <h2>Government Links</h2>
              <ul>{GOV_LINKS.map(([l, u]) => <li key={u}><a href={u} {...ext}>{l}</a></li>)}</ul>
            </div>
          </div>
          <div className="border-top border-secondary-subtle mt-4 pt-3 small d-flex flex-column flex-md-row justify-content-between gap-1">
            <span>© {new Date().getFullYear()} {LGU_NAME}</span>
            <span>{MAP_CREDIT}</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
