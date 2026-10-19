import { useState } from "react";
import { Alert, Button, Card, Container, Form } from "react-bootstrap";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { apiErrorMessage } from "@/api/client";
import { homeFor, useAuth } from "@/auth/AuthContext";

type FormValues = { username: string; password: string };

export function LoginPage() {
  const { login, status, user } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<FormValues>();

  const next = params.get("next");
  const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : null;

  if (status === "authenticated" && user) return <Navigate to={safeNext ?? homeFor(user)} replace />;

  const onSubmit = handleSubmit(async ({ username, password }) => {
    setError(null);
    try {
      const me = await login(username, password);
      navigate(safeNext ?? homeFor(me), { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "Invalid username or password."));
    }
  });

  return (
    <Container className="py-5" style={{ maxWidth: 420 }}>
      <Card>
        <Card.Body className="p-4">
          <h1 className="h4 fw-bold mb-1">Staff Login</h1>
          <p className="small text-secondary mb-4">For LGU, barangay, and department personnel.</p>
          {error && <Alert variant="danger">{error}</Alert>}
          <Form onSubmit={onSubmit} noValidate>
            <Form.Group className="mb-3" controlId="username">
              <Form.Label>Username</Form.Label>
              <Form.Control
                autoComplete="username"
                isInvalid={!!formState.errors.username}
                {...register("username", { required: "Username is required" })}
              />
              <Form.Control.Feedback type="invalid">{formState.errors.username?.message}</Form.Control.Feedback>
            </Form.Group>
            <Form.Group className="mb-4" controlId="password">
              <Form.Label>Password</Form.Label>
              <Form.Control
                type="password"
                autoComplete="current-password"
                isInvalid={!!formState.errors.password}
                {...register("password", { required: "Password is required" })}
              />
              <Form.Control.Feedback type="invalid">{formState.errors.password?.message}</Form.Control.Feedback>
            </Form.Group>
            <Button type="submit" className="w-100" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
          </Form>
        </Card.Body>
      </Card>
    </Container>
  );
}
