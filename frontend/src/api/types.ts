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
export type ConcernStatus = S["ConcernStatusEnum"];

export type JwtClaims = {
  user_id: string | number;
  username: string;
  full_name: string;
  role: Role;
  barangay_id: number | null;
  department_id: number | null;
  exp: number;
};

export const STAFF_ROLES: Role[] = [
  "pacd", "barangay", "office_desk", "dept_head", "division_chief", "dept_staff", "city_admin", "mayor",
];
export const EXECUTIVE_ROLES: Role[] = ["city_admin", "mayor"];

export type Subcategory = S["PublicSubcategory"];
export type AffectedScale = S["AffectedScaleEnum"];

// ----- staff -----
export type StaffConcern = S["StaffConcernList"];
export type StaffConcernDetail = S["StaffConcernDetail"];
export type StaffConcernPage = S["PaginatedStaffConcernListList"];
export type StaffSummary = S["StaffSummary"];
export type Department = S["Department"];
export type Division = S["Division"];
export type PriorityLevel = S["PriorityLevel"];
export type Permissions = S["Permissions"];
export type CaseInfo = S["CaseInfo"];
export type EndorsementInfo = S["Endorsement"];
export type EndorsementStatus = S["EndorsementStatusEnum"];
export type StaffUser = S["StaffUser"];
export type Channel = S["ConcernChannelEnum"];
export type Severity = S["SeverityEnum"];
export type StaffEncodeRequest = S["StaffEncodeRequest"];

// ----- GIS -----
export type MapPoint = S["MapPoint"];
export type MapPoints = S["MapPoints"];
export type BarangayStat = S["BarangayStat"];
export type Hotspot = S["Hotspot"];
export type Hotspots = S["Hotspots"];
