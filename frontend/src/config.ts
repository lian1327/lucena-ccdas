export const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";
export const LGU_NAME = import.meta.env.VITE_LGU_NAME ?? "Local Government Unit";
export const APP_NAME = "CCADSS";
/** Map fallback center when a barangay has no coordinates yet (Lucena City proper). */
export const LGU_CENTER: [number, number] = [13.9373, 121.617];

/* ---- Public-site identity (all optional; set in .env.local) ---------------------------- */
const env = import.meta.env;
/** Short name used in the masthead, e.g. "Lungsod ng Lucena". */
export const LGU_SHORT = env.VITE_LGU_SHORT ?? "Lungsod ng Lucena";
export const LGU_PROVINCE = env.VITE_LGU_PROVINCE ?? "Lalawigan ng Quezon";
export const LGU_ADDRESS = env.VITE_LGU_ADDRESS ?? "";
export const LGU_EMAIL = env.VITE_LGU_EMAIL ?? "";
export const LGU_PHONE = env.VITE_LGU_PHONE ?? "";
export const LGU_WEBSITE = env.VITE_LGU_WEBSITE ?? "";
export const LGU_FACEBOOK = env.VITE_LGU_FACEBOOK ?? "";
/** Official seal, served from frontend/public/. Add the file only with the LGU's permission. */
export const LGU_SEAL_SRC = env.VITE_LGU_SEAL ?? "/seal.png";
export const GOVPH_SEAL_SRC = env.VITE_GOVPH_SEAL ?? "/govph-seal.png";

export type Hotline = { label: string; number: string; note?: string; emergency?: boolean };

/**
 * Only numbers we could verify are built in. Add office numbers through VITE_LGU_HOTLINES as JSON:
 * [{"label":"CDRRMO","number":"(042) 000-0000"}] — confirm each with the office before publishing.
 */
export const HOTLINES: Hotline[] = [
  { label: "Lucena Emergency 911", number: "911", note: "Sunog, aksidente, krimen, medikal", emergency: true },
  { label: "Citizens' Complaint Hotline", number: "8888", note: "Reklamo sa serbisyo ng gobyerno" },
  ...(() => {
    try { return JSON.parse(env.VITE_LGU_HOTLINES ?? "[]") as Hotline[]; } catch { return []; }
  })(),
];
