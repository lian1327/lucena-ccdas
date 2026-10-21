import { useState } from "react";

/**
 * Shows an official seal if the file exists in /public, otherwise a dashed placeholder.
 * We never draw a seal ourselves: the LGU supplies the real file, with permission.
 */
export function Seal({ src, alt, size = "md" }: { src: string; alt: string; size?: "sm" | "md" }) {
  const [missing, setMissing] = useState(false);
  const cls = `seal ${size === "sm" ? "seal-sm" : ""}`;
  if (missing)
    return (
      <span className={`${cls} seal-fallback`} role="img" aria-label={`${alt} (placeholder)`} title="Add the official seal file to frontend/public/">
        <i className="bi bi-bank2" aria-hidden />
      </span>
    );
  return <img src={src} alt={alt} className={cls} onError={() => setMissing(true)} />;
}
