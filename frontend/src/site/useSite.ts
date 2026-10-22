import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";

export type SiteMode = "official" | "prototype";
export type SiteInfo = { mode: SiteMode; org_name: string; contact_email: string; sample_data: boolean };

/** Build-time guess (no flash of the wrong branding); the server's answer wins once it arrives. */
const BUILD_MODE: SiteMode = import.meta.env.VITE_SITE_MODE === "official" ? "official" : "prototype";
const FALLBACK: SiteInfo = {
  mode: BUILD_MODE,
  org_name: import.meta.env.VITE_ORG_NAME ?? "Dalubhasaan ng Lungsod ng Lucena",
  contact_email: "",
  sample_data: true,
};

export function useSite(): SiteInfo & { isPrototype: boolean } {
  const q = useQuery({
    queryKey: ["public", "site"],
    queryFn: async () => (await api.get<SiteInfo>("/public/site/")).data,
    staleTime: 60 * 60 * 1000,
    retry: 2,
  });
  const s = q.data ?? FALLBACK;
  return { ...s, isPrototype: s.mode !== "official" };
}
