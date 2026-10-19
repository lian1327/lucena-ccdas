import { Container } from "react-bootstrap";
import { Link } from "react-router-dom";

function ErrorBlock({ code, title, text }: { code: string; title: string; text: string }) {
  return (
    <Container className="py-5 text-center">
      <div className="display-4 fw-bold text-secondary">{code}</div>
      <h1 className="h4">{title}</h1>
      <p className="text-secondary">{text}</p>
      <Link to="/" className="btn btn-primary">Back to home</Link>
    </Container>
  );
}

export const NotFoundPage = () => (
  <ErrorBlock code="404" title="Page not found" text="The page you're looking for doesn't exist." />
);

export const ForbiddenPage = () => (
  <ErrorBlock code="403" title="Not allowed" text="Your account doesn't have access to this page." />
);
