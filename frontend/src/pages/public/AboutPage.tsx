import { Link } from "react-router-dom";

import { HOTLINES, LGU_NAME } from "@/config";
import { FAQ } from "@/pages/public/HomePage";
import { useSite } from "@/site/useSite";

/**
 * Citizen's Charter entry for this service, in the ARTA (RA 11032) format, plus the full FAQ.
 * Draft: the LGU's ARTA focal person must review the wording and offices before go-live.
 */
const META: [string, string][] = [
  ["Opisina", "Public Assistance and Complaints Desk (PACD), kasama ang mga tanggapang may hawak ng concern"],
  ["Klasipikasyon", "Simple, Complex o Highly Technical, ayon sa uri ng problema"],
  ["Uri ng transaksyon", "G2C – Government to Citizen"],
  ["Sino ang puwedeng mag-avail", "Lahat ng residente at bisita ng lungsod"],
];

const STEPS: { client: string; agency: string; fee: string; time: string; who: string }[] = [
  { client: "Isumite ang report sa portal, sa barangay, o sa PACD (walk-in).", agency: "Bigyan ng reference number at itala ang report.", fee: "Wala", time: "Agad", who: "Sistema / PACD" },
  { client: "", agency: "Suriin kung kumpleto, pagsamahin sa kaparehong report, at ipasa sa tamang opisina.", fee: "Wala", time: "1 working day", who: "PACD Officer" },
  { client: "", agency: "Tanggapin o ibalik ang concern na hindi sakop ng opisina.", fee: "Wala", time: "1 working day", who: "Office desk / Department head" },
  { client: "", agency: "Inspeksyunin, ayusin, at mag-upload ng larawan bago at pagkatapos bilang patunay.", fee: "Wala", time: "3 / 7 / 20 working days", who: "Itinalagang kawani" },
  { client: "", agency: "Beripikahin ng ibang kawani ang patunay bago isara.", fee: "Wala", time: "Kasama sa itaas", who: "Department head / Division chief" },
  { client: "Kumpirmahin kung naayos, o sabihing hindi pa.", agency: "Buksang muli kung hindi naayos.", fee: "Wala", time: "Hanggang 30 araw matapos isara", who: "Mamamayan / PACD" },
];

export function AboutPage() {
  const h8888 = HOTLINES.find((h) => h.number === "8888");
  const site = useSite();
  return (
    <div className="container py-5">
      <div className="prose mb-4">
        <h1 className="section-title">Citizen's Charter</h1>
        <p className="lead">Pagtanggap at pag-aksyon sa mga concern ng mamamayan tungkol sa komunidad.</p>
        {site.isPrototype && (
          <div className="alert alert-warning small">
            Panukalang Citizen's Charter ito para sa pananaliksik: ganito ang magiging serbisyo kapag ginamit ng lungsod
            ang sistema. Hindi pa ito opisyal na charter ng Pamahalaang Lungsod ng Lucena.
          </div>
        )}
        <p className="text-secondary">
          Ang serbisyong ito ay walang bayad. Ang takdang oras ay binibilang sa working days mula nang maipasa ang
          concern sa opisina, ayon sa RA 11032. Puwedeng i-extend nang isang beses lamang, at aabisuhan ka.
        </p>
      </div>

      <dl className="row border-top border-bottom py-3 mx-0 mb-4">
        {META.map(([k, v]) => (
          <div className="col-md-6 col-xl-3 py-2" key={k}>
            <dt className="small text-secondary fw-normal">{k}</dt>
            <dd className="fw-bold mb-0">{v}</dd>
          </div>
        ))}
      </dl>

      <h2 className="h5 fw-bold">Mga kailangan</h2>
      <ul className="mb-4">
        <li>Paglalarawan ng problema at lokasyon (barangay, at kung maaari, pin sa mapa)</li>
        <li>Larawan, kung mayroon (hindi sapilitan)</li>
        <li>Mobile number, kung gusto mong makatanggap ng update (hindi sapilitan)</li>
      </ul>

      <div className="table-responsive mb-5">
        <table className="table align-top">
          <caption className="small">Mga hakbang. Ang takdang oras ay pinakamatagal na pinapayagan; mas maikli ito para sa mataas na priority.</caption>
          <thead>
            <tr>
              <th scope="col">Hakbang ng kliyente</th>
              <th scope="col">Aksyon ng tanggapan</th>
              <th scope="col">Bayad</th>
              <th scope="col">Takdang oras</th>
              <th scope="col">Responsable</th>
            </tr>
          </thead>
          <tbody>
            {STEPS.map((s, i) => (
              <tr key={i}>
                <td>{s.client}</td>
                <td>{s.agency}</td>
                <td>{s.fee}</td>
                <td className="text-nowrap">{s.time}</td>
                <td>{s.who}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="row g-4 g-lg-5">
        <div className="col-lg-7 faq" id="faq">
          <h2 className="section-title mb-2">Mga madalas itanong</h2>
          {FAQ.map(([q, a]) => (
            <details key={q}>
              <summary>{q}</summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
        <div className="col-lg-5">
          <h2 className="h5 fw-bold">Puna at reklamo sa serbisyo</h2>
          <p>
            Kung hindi nasunod ang takdang oras o hindi ka nasiyahan sa serbisyo, isulat ito sa pahina ng iyong report,
            o lumapit sa PACD ng {LGU_NAME}.
          </p>
          {h8888 && (
            <p>
              Maaari ka ring tumawag sa <a href="tel:8888" className="fw-bold">8888</a> ({h8888.label}) o makipag-ugnayan sa{" "}
              <a href="https://arta.gov.ph" target="_blank" rel="noreferrer">Anti-Red Tape Authority</a>.
            </p>
          )}
          <Link to="/report" className="btn btn-primary">Mag-report ng problema</Link>
        </div>
      </div>
    </div>
  );
}
