import { LGU_NAME } from "@/config";
import { useSite } from "@/site/useSite";

/**
 * Data Privacy Notice (RA 10173). Two versions: research prototype (controller = the college) and
 * official City portal (controller = the LGU). DRAFT: the Data Protection Officer must review before go-live.
 */
export function PrivacyPage() {
  const site = useSite();
  const proto = site.isPrototype;
  const controller = proto ? site.org_name : LGU_NAME;

  return (
    <div className="container py-5 prose">
      <h1 className="section-title">Data Privacy Notice</h1>
      {proto && (
        <p className="lead">
          Ang portal na ito ay <strong>prototype para sa pananaliksik</strong>. Hindi ipinapadala sa Pamahalaang Lungsod
          ng Lucena ang mga report dito.
        </p>
      )}

      <h2 className="h5 fw-bold">Sino ang nangangalaga ng iyong datos</h2>
      <p>
        {controller} ang personal information controller.
        {site.contact_email && <> Para sa tanong o kahilingan, sumulat sa <a href={`mailto:${site.contact_email}`}>{site.contact_email}</a>.</>}
      </p>

      <h2 className="h5 fw-bold">Anong datos ang kinokolekta</h2>
      <ul>
        <li>Ang paglalarawan ng problema, lokasyon (barangay, purok, pin sa mapa) at mga larawan na ini-upload mo</li>
        <li>Pangalan, mobile number at email, kung ilalagay mo. Puwede kang mag-report nang anonymous.</li>
        <li>Teknikal na datos para sa seguridad (hal. oras ng pagsumite), hindi para kilalanin ka</li>
      </ul>

      <h2 className="h5 fw-bold">Para saan ito ginagamit</h2>
      {proto ? (
        <ul>
          <li>Para subukan at suriin ang sistema bilang bahagi ng isang capstone na pananaliksik</li>
          <li>Para sa mga pinagsama-samang istatistika na walang nakikilalang tao</li>
          <li>Kung pumayag ka, para padalhan ka ng update tungkol sa report na ito lamang</li>
        </ul>
      ) : (
        <ul>
          <li>Para tanggapin, ipasa sa tamang opisina, aksyunan at i-update ka tungkol sa iyong concern</li>
          <li>Para sa mga pinagsama-samang istatistika para sa pagpaplano ng lungsod, na walang nakikilalang tao</li>
        </ul>
      )}
      <p>
        Batayan: ang iyong pahintulot{proto ? "" : " at ang tungkulin ng lungsod na maghatid ng serbisyo publiko"}, ayon sa
        Republic Act No. 10173 (Data Privacy Act of 2012). Hindi ginagamit ang iyong datos para sa marketing.
      </p>

      <h2 className="h5 fw-bold">Sino ang nakakakita</h2>
      <p>
        {proto
          ? "Ang mga mananaliksik at awtorisadong tagasuri lamang."
          : "Ang mga awtorisadong kawani lamang na humahawak ng iyong concern."}{" "}
        Hindi kailanman ipinapakita sa publiko ang iyong pangalan, numero, email o ang mga larawang ini-upload mo. Sa
        tracking page, ang larawan lang ng opisina (bago at pagkatapos ayusin) ang ipinapakita.
      </p>

      <h2 className="h5 fw-bold">Mga serbisyong ginagamit sa pag-iimbak at pagpapadala</h2>
      <p>
        Ang portal ay naka-host sa mga cloud service (application server, database at file storage) na maaaring nasa
        labas ng Pilipinas, at maaaring gumamit ng SMS provider para sa mga update. May kasunduan sa pagproseso ng datos
        at naka-encrypt ang koneksyon (HTTPS). Hindi nakikita ng publiko ang mga larawan: may expiry ang bawat link.
      </p>

      <h2 className="h5 fw-bold">Gaano katagal itinatago</h2>
      <p>
        {proto
          ? "Hanggang matapos ang pananaliksik, saka buburahin o gagawing anonymous. "
          : "Ayon sa records retention ng lungsod. "}
        Binubura ang mobile number at email sa talaan ng mga ipinadalang SMS/email pagkalipas ng isang taon.
      </p>

      <h2 className="h5 fw-bold">Ang iyong mga karapatan</h2>
      <p>
        May karapatan kang malaman, ma-access, maitama, ipabura o tumutol sa pagproseso ng iyong datos, at magreklamo sa
        National Privacy Commission (<a href="https://privacy.gov.ph" target="_blank" rel="noreferrer">privacy.gov.ph</a>).
        Puwede mong itigil ang SMS anumang oras sa tracking page ng iyong report.
      </p>
      <p className="small text-secondary">Huling binago: Oktubre 2026 (draft, para suriin ng DPO).</p>
    </div>
  );
}
