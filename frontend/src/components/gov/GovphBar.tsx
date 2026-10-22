import { useEffect, useState } from "react";

const PST = new Intl.DateTimeFormat("en-PH", {
  timeZone: "Asia/Manila",
  weekday: "long",
  month: "long",
  day: "numeric",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
});

type TextSize = "md" | "lg" | "xl";
const SIZES: TextSize[] = ["md", "lg", "xl"];

function read(key: string) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function write(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* storage blocked: setting lasts this visit only */ }
}

/** Applies saved reader settings before first paint of the layout. */
export function useReaderSettings() {
  const [size, setSize] = useState<TextSize>(() => (SIZES.includes(read("ccadss.text") as TextSize) ? (read("ccadss.text") as TextSize) : "md"));
  const [contrast, setContrast] = useState(() => read("ccadss.contrast") === "high");
  useEffect(() => {
    const el = document.documentElement;
    if (size === "md") el.removeAttribute("data-text"); else el.setAttribute("data-text", size);
    write("ccadss.text", size);
  }, [size]);
  useEffect(() => {
    const el = document.documentElement;
    if (contrast) el.setAttribute("data-contrast", "high"); else el.removeAttribute("data-contrast");
    write("ccadss.contrast", contrast ? "high" : "normal");
  }, [contrast]);
  return { size, setSize, contrast, setContrast };
}

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(t);
  }, []);
  return (
    <span className="d-none d-md-inline">
      Philippine Standard Time: <time dateTime={now.toISOString()}>{PST.format(now)}</time>
    </span>
  );
}

/** The thin GOVPH bar that tops Philippine government sites (GWT), plus reader tools. */
export function GovphBar({ official = true }: { official?: boolean }) {
  const { size, setSize, contrast, setContrast } = useReaderSettings();
  const idx = SIZES.indexOf(size);
  return (
    <div className="govph-bar">
      <div className="container d-flex align-items-center justify-content-between gap-3 py-1">
        <div className="d-flex align-items-center gap-3">
          {official ? (
            <>
              <a href="https://www.gov.ph" className="govph-mark" target="_blank" rel="noreferrer">GOVPH</a>
              <Clock />
            </>
          ) : (
            <span className="govph-mark">CCADSS</span>
          )}
        </div>
        <div className="a11y-tools d-flex align-items-center gap-1" role="group" aria-label="Reader settings">
          <span className="d-none d-sm-inline me-1">Laki ng teksto</span>
          <button type="button" className="btn" disabled={idx === 0} onClick={() => setSize(SIZES[idx - 1])} aria-label="Paliitin ang teksto">A−</button>
          <button type="button" className="btn" aria-pressed={size === "md"} onClick={() => setSize("md")} aria-label="Karaniwang laki ng teksto">A</button>
          <button type="button" className="btn" disabled={idx === SIZES.length - 1} onClick={() => setSize(SIZES[idx + 1])} aria-label="Palakihin ang teksto">A+</button>
          <button type="button" className="btn ms-1" aria-pressed={contrast} onClick={() => setContrast(!contrast)}>
            <i className="bi bi-circle-half me-1" aria-hidden />Contrast
          </button>
        </div>
      </div>
    </div>
  );
}
