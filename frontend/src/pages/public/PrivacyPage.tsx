import { Container } from "react-bootstrap";

import { LGU_NAME } from "@/config";

/** Draft notice — have the LGU's Data Protection Officer review before go-live. */
export function PrivacyPage() {
  return (
    <Container className="py-5" style={{ maxWidth: 760 }}>
      <h1 className="h3 fw-bold">Data Privacy Notice</h1>
      <p>
        {LGU_NAME} collects the information you provide in this portal (name, contact details, location, photos, and
        the description of your concern) solely to receive, act on, and update you about your concern, and to produce
        aggregated statistics for planning. This is done under Republic Act No. 10173 (Data Privacy Act of 2012).
      </p>
      <p>
        You may report anonymously. Personal information is accessible only to authorized LGU personnel handling your
        concern, and public statistics never identify individuals.
      </p>
    </Container>
  );
}
