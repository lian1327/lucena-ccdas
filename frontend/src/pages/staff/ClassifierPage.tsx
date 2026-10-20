import { Alert, Badge, Button, Card, Col, Row, Table } from "react-bootstrap";

import { apiErrorMessage } from "@/api/client";
import { useActivate, useMLOverview, useRetrain } from "@/api/ml";
import { useAuth } from "@/auth/AuthContext";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { KpiTile, pct } from "@/features/analytics/ui";
import { fmtDateTime } from "@/utils/format";

type Rep = { accuracy: number; macro_f1: number; n: number; per_class: { code: string; name: string; precision: number; recall: number; f1: number; support: number }[];
  confusion?: { labels: string[]; matrix: number[][] }; coverage?: { threshold: number; coverage: number; accuracy: number | null }[];
  errors?: { text: string; expected: string; predicted: string; confidence: number }[]; subcategory_accuracy?: number };
type Metrics = { algorithm: string; comparison: { algorithm: string; cv_macro_f1: number | null; cv_std?: number; test_accuracy: number; test_macro_f1: number }[];
  category: Rep; subcategory: { accuracy: number; macro_f1: number }; coverage: Rep["coverage"]; features: string; seconds?: number };

const RAMP = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];

function Confusion({ c, names }: { c: NonNullable<Rep["confusion"]>; names: Record<string, string> }) {
  const max = Math.max(1, ...c.matrix.flat());
  return (
    <Table size="sm" className="small mb-0 text-center" style={{ fontVariantNumeric: "tabular-nums" }}>
      <thead><tr><th className="text-start">Totoo ↓ / Hula →</th>{c.labels.map((l) => <th key={l} title={names[l]}>{(names[l] ?? l).split(" ")[0]}</th>)}</tr></thead>
      <tbody>
        {c.matrix.map((row, i) => (
          <tr key={c.labels[i]}>
            <th className="text-start fw-normal">{names[c.labels[i]] ?? c.labels[i]}</th>
            {row.map((v, j) => {
              const bg = v ? RAMP[Math.min(RAMP.length - 1, 1 + Math.floor((v / max) * (RAMP.length - 2)))] : "#fff";
              const off = i !== j && v > 0;
              return <td key={j} style={{ background: off ? "#fbe4e4" : bg, color: !off && RAMP.indexOf(bg) >= 4 ? "#fff" : off ? "#9b1c1c" : undefined,
                border: "2px solid #fff" }}>{v || "·"}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** Module 3 dashboard: how good is the AI, measured three honest ways. */
export default function ClassifierPage() {
  const { user } = useAuth();
  const q = useMLOverview();
  const retrain = useRetrain();
  const activate = useActivate();
  if (q.isLoading) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const d = q.data!;
  const admin = user?.role === "city_admin";
  if (!d.active) return (
    <Alert variant="info">Wala pang trained na model. Patakbuhin ang <code>python manage.py train_classifier</code>
      {admin && <> o <Button size="sm" onClick={() => retrain.mutate({})}>I-train ngayon</Button></>}.</Alert>
  );
  const a = d.active;
  const m = a.metrics as unknown as Metrics;
  const ch = a.challenge_metrics as unknown as Rep;
  const names = Object.fromEntries(m.category.per_class.map((c) => [c.code, c.name]));
  const live = d.live;
  const chCov = ch?.coverage?.find((r) => Math.abs(r.threshold - d.auto_threshold) < 0.001);

  return (
    <div className="analytics-report">
      <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
        <div className="me-auto">
          <h1 className="h4 fw-bold mb-0">AI Classifier <Badge bg="primary" className="align-middle">v{a.version} · aktibo</Badge></h1>
          <div className="small text-secondary">
            {m.algorithm} · {m.features} · trained {fmtDateTime(a.created_at)}{a.trained_by ? ` ni ${a.trained_by}` : ""} ·
            data: {Object.entries(a.data_sources as Record<string, number>).map(([k, v]) => `${v} ${k}`).join(", ")}
          </div>
        </div>
        {admin && (
          <Button size="sm" disabled={retrain.isPending} onClick={() => retrain.mutate({})}>
            <i className="bi bi-arrow-repeat me-1" aria-hidden />{retrain.isPending ? "Nagte-train… (≈1 min)" : "I-retrain"}
          </Button>
        )}
      </div>
      {retrain.isError && <Alert variant="danger" className="small">{apiErrorMessage(retrain.error)}</Alert>}
      {retrain.data && <Alert variant={retrain.data.is_active ? "success" : "warning"} className="small">
        Na-train ang v{retrain.data.version}. {retrain.data.is_active ? "Ito na ang aktibong model." : "Hindi in-activate: mas mababa ang macro-F1 kaysa sa kasalukuyan."}</Alert>}

      <Alert variant="secondary" className="small">
        Tatlong paraan ng pagsukat, mula sa pinaka-optimistic hanggang pinaka-totoo: (1) held-out na synthetic reports,
        (2) hand-written challenge set na hindi galing sa generator, at (3) live: gaano kadalas sumang-ayon ang PACD sa mungkahi ng AI.
        Sa synthetic na datos, ang (3) ay optimistic din; sa totoong reports ng LGU ito ang dapat iulat.
      </Alert>

      <Row className="g-3 mb-3">
        <Col xs={6} lg={3}><KpiTile label="1 · Held-out test (synthetic)" value={pct(m.category.accuracy)} sub={`macro-F1 ${m.category.macro_f1.toFixed(3)} · n=${m.category.n}`}
          tip="Optimistic: same generator as the training data." /></Col>
        <Col xs={6} lg={3}><KpiTile label="2 · Challenge set (hand-written)" value={ch?.accuracy != null ? pct(ch.accuracy) : "—"}
          sub={ch?.n ? `macro-F1 ${ch.macro_f1.toFixed(3)} · n=${ch.n} · sub-type ${pct(ch.subcategory_accuracy)}` : "walang challenge set"} /></Col>
        <Col xs={6} lg={3}><KpiTile label="3 · Live agreement with PACD" value={pct(live.agreement)} sub={`${live.n} na-verify · sub-type ${pct(live.sub_agreement)}`} /></Col>
        <Col xs={6} lg={3}><KpiTile label={`Auto-assign ≥${Math.round(d.auto_threshold * 100)}%`}
          value={chCov ? pct(chCov.coverage) : "—"} sub={chCov ? `ng reports · ${pct(chCov.accuracy)} tama (challenge set)` : ""}
          tip="Kapag hindi pumili ang citizen at ganito kataas ang kumpiyansa, ang AI ang maglalagay ng kategorya. Bine-verify pa rin ng PACD." /></Col>
      </Row>

      <Row className="g-3 mb-3">
        <Col lg={6}>
          <Card className="border-0 shadow-sm h-100"><Card.Body className="p-0">
            <div className="fw-semibold p-3 pb-2">Paghahambing ng mga model (category)</div>
            <Table size="sm" className="small mb-0" style={{ fontVariantNumeric: "tabular-nums" }}>
              <thead className="table-light"><tr><th>Model</th><th className="text-end">CV macro-F1</th><th className="text-end">Test acc.</th><th className="text-end">Test macro-F1</th></tr></thead>
              <tbody>{m.comparison.map((r) => (
                <tr key={r.algorithm} className={r.algorithm === m.algorithm ? "table-primary" : ""}>
                  <td>{r.algorithm.replace(/_/g, " ")}{r.algorithm === m.algorithm && " ✓"}</td>
                  <td className="text-end">{r.cv_macro_f1 == null ? "—" : `${r.cv_macro_f1.toFixed(3)} ± ${(r.cv_std ?? 0).toFixed(3)}`}</td>
                  <td className="text-end">{pct(r.test_accuracy)}</td><td className="text-end">{r.test_macro_f1.toFixed(3)}</td>
                </tr>
              ))}</tbody>
            </Table>
            <div className="small text-secondary p-3">Pinili ang may pinakamataas na 5-fold cross-validated macro-F1. Ang majority baseline ang "hula na laging pinakamaraming kategorya".</div>
          </Card.Body></Card>
        </Col>
        <Col lg={6}>
          <Card className="border-0 shadow-sm h-100"><Card.Body className="p-0">
            <div className="fw-semibold p-3 pb-2">Kumpiyansa vs. dami ng auto-assign (challenge set)</div>
            <Table size="sm" className="small mb-0" style={{ fontVariantNumeric: "tabular-nums" }}>
              <thead className="table-light"><tr><th>Threshold</th><th className="text-end">Na-auto-assign</th><th className="text-end">Tama sa mga iyon</th></tr></thead>
              <tbody>{(ch?.coverage ?? m.coverage ?? []).map((r) => (
                <tr key={r.threshold} className={Math.abs(r.threshold - d.auto_threshold) < 0.001 ? "table-primary" : ""}>
                  <td>≥ {Math.round(r.threshold * 100)}%</td><td className="text-end">{pct(r.coverage)}</td><td className="text-end">{pct(r.accuracy)}</td>
                </tr>
              ))}</tbody>
            </Table>
            <div className="small text-secondary p-3">Mas mataas na threshold = mas kaunting na-auto-assign pero mas tama. Ang iba ay iniiwan sa PACD.</div>
          </Card.Body></Card>
        </Col>
      </Row>

      {ch?.per_class && (
        <Row className="g-3 mb-3">
          <Col lg={5}>
            <Card className="border-0 shadow-sm h-100"><Card.Body className="p-0">
              <div className="fw-semibold p-3 pb-2">Bawat kategorya (challenge set)</div>
              <Table size="sm" className="small mb-0" style={{ fontVariantNumeric: "tabular-nums" }}>
                <thead className="table-light"><tr><th>Kategorya</th><th className="text-end">Precision</th><th className="text-end">Recall</th><th className="text-end">F1</th><th className="text-end">n</th></tr></thead>
                <tbody>{ch.per_class.map((c) => (
                  <tr key={c.code}><td>{c.name}</td><td className="text-end">{c.precision.toFixed(2)}</td><td className="text-end">{c.recall.toFixed(2)}</td>
                    <td className={`text-end ${c.f1 < 0.85 ? "text-danger fw-semibold" : ""}`}>{c.f1.toFixed(2)}</td><td className="text-end">{c.support}</td></tr>
                ))}</tbody>
              </Table>
            </Card.Body></Card>
          </Col>
          <Col lg={7}>
            <Card className="border-0 shadow-sm h-100"><Card.Body>
              <div className="fw-semibold mb-2">Confusion matrix (challenge set) <span className="small text-secondary fw-normal">· pula = mali</span></div>
              {ch.confusion && <Confusion c={ch.confusion} names={names} />}
            </Card.Body></Card>
          </Col>
        </Row>
      )}

      <Row className="g-3 mb-3">
        <Col lg={7}>
          <Card className="border-0 shadow-sm h-100"><Card.Body className="small">
            <div className="fw-semibold mb-2">Mga maling hula (challenge set)</div>
            {(ch?.errors ?? []).slice(0, 10).map((e, i) => (
              <div key={i} className="border-bottom py-1">
                “{e.text}” <span className="text-secondary">→</span> <span className="text-danger">{names[e.predicted] ?? e.predicted}</span>
                <span className="text-secondary"> (dapat {names[e.expected] ?? e.expected}, {Math.round(e.confidence * 100)}%)</span>
              </div>
            ))}
          </Card.Body></Card>
        </Col>
        <Col lg={5}>
          <Card className="border-0 shadow-sm h-100"><Card.Body className="p-0">
            <div className="fw-semibold p-3 pb-2">Live: pagsang-ayon ng PACD bawat buwan</div>
            <Table size="sm" className="small mb-0" style={{ fontVariantNumeric: "tabular-nums" }}>
              <thead className="table-light"><tr><th>Buwan</th><th className="text-end">Na-verify</th><th className="text-end">Sang-ayon</th></tr></thead>
              <tbody>{live.by_month.map((r) => <tr key={r.month}><td>{r.month}</td><td className="text-end">{r.n}</td><td className="text-end">{pct(r.agreement)}</td></tr>)}</tbody>
            </Table>
            {live.top_confusions.length > 0 && <div className="small text-secondary p-3">Madalas itama ng PACD: {live.top_confusions.slice(0, 3)
              .map((x) => `${names[x.predicted] ?? x.predicted} → ${names[x.actual] ?? x.actual} (${x.count})`).join(" · ")}</div>}
          </Card.Body></Card>
        </Col>
      </Row>

      <Card className="border-0 shadow-sm"><Card.Body className="p-0">
        <div className="fw-semibold p-3 pb-2">Mga bersyon</div>
        <Table size="sm" className="small mb-0" style={{ fontVariantNumeric: "tabular-nums" }}>
          <thead className="table-light"><tr><th>Bersyon</th><th>Na-train</th><th>Algorithm</th><th className="text-end">Train/test</th><th className="text-end">Test macro-F1</th><th className="text-end">Challenge acc.</th><th>Tala</th><th /></tr></thead>
          <tbody>{d.versions.map((v) => {
            const vm = v.metrics as unknown as Metrics; const vc = v.challenge_metrics as unknown as Rep;
            return (
              <tr key={v.id}>
                <td>v{v.version} {v.is_active && <Badge bg="primary">aktibo</Badge>}</td><td>{fmtDateTime(v.created_at)}</td><td>{v.algorithm}</td>
                <td className="text-end">{v.n_train}/{v.n_test}</td><td className="text-end">{vm.category?.macro_f1?.toFixed(3)}</td>
                <td className="text-end">{vc?.accuracy != null ? pct(vc.accuracy) : "—"}</td><td className="text-secondary">{v.notes}</td>
                <td>{admin && !v.is_active && <Button size="sm" variant="outline-primary" className="py-0" disabled={activate.isPending} onClick={() => activate.mutate(v.id)}>I-activate</Button>}</td>
              </tr>
            );
          })}</tbody>
        </Table>
      </Card.Body></Card>
    </div>
  );
}
