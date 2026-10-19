export const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";
export const LGU_NAME = import.meta.env.VITE_LGU_NAME ?? "Local Government Unit";
export const APP_NAME = "CCADSS";
/** Map fallback center when a barangay has no coordinates yet (Lucena City proper). */
export const LGU_CENTER: [number, number] = [13.9373, 121.617];
