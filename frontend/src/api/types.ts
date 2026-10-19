/** Friendly aliases over the generated OpenAPI types. Regenerate with `npm run gen:api`. */
import type { components } from "./schema";

type S = components["schemas"];

export type Category = S["PublicCategory"];
export type Barangay = S["PublicBarangay"];
export type PublicStats = S["PublicStats"];
export type TrackResult = S["PublicTrack"];
export type TimelineEntry = S["PublicTimeline"];
export type ConcernCreateRequest = S["PublicConcernCreateRequest"];
export type ConcernCreateResponse = S["PublicConcernCreate"];
export type Me = S["Me"];
export type Role = S["RoleEnum"];
export type ConcernStatus = S["StatusEnum"];

export type JwtClaims = {
  user_id: string | number;
  username: string;
  full_name: string;
  role: Role;
  barangay_id: number | null;
  department_id: number | null;
  exp: number;
};

export const STAFF_ROLES: Role[] = ["barangay", "dept_staff", "city_admin", "mayor"];
export const EXECUTIVE_ROLES: Role[] = ["city_admin", "mayor"];
