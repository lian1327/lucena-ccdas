import { LGU_EMAIL, LGU_NAME } from "@/config";

export function AccessibilityPage() {
  return (
    <div className="container py-5 prose">
      <h1 className="section-title">Accessibility</h1>
      <p className="lead">Nais naming magamit ng lahat ang portal na ito, kasama ang mga senior citizen at may kapansanan.</p>
      <h2 className="h5 fw-bold">Ang mayroon sa portal</h2>
      <ul>
        <li>Pagpapalaki ng teksto (A−, A, A+) at mataas na contrast sa itaas ng bawat pahina. Natatandaan ito ng iyong browser.</li>
        <li>Lahat ng gawain ay magagawa gamit ang keyboard, may malinaw na dilaw na marka kung nasaan ka.</li>
        <li>"Lumaktaw sa nilalaman" na link para sa gumagamit ng screen reader o keyboard.</li>
        <li>Font na Atkinson Hyperlegible, ginawa para sa mga mahina ang paningin.</li>
        <li>Hindi kailangan ng mapa: puwedeng piliin na lang ang barangay at purok.</li>
        <li>Iginagalang ang setting na "reduce motion" ng iyong device.</li>
      </ul>
      <h2 className="h5 fw-bold">Pamantayan</h2>
      <p>
        Sinusundan namin ang Web Content Accessibility Guidelines (WCAG) 2.1 Level AA at ang Government Website
        Template ng Pilipinas. Kung may bahaging mahirap gamitin, gusto naming malaman.
      </p>
      <h2 className="h5 fw-bold">Iulat ang problema sa accessibility</h2>
      <p>
        Lumapit sa Public Assistance and Complaints Desk ng {LGU_NAME}
        {LGU_EMAIL ? <> o mag-email sa <a href={`mailto:${LGU_EMAIL}`}>{LGU_EMAIL}</a></> : null}. Puwede ring mag-report
        dito sa portal sa ilalim ng "Iba Pang Concern".
      </p>
    </div>
  );
}
