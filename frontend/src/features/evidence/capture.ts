/**
 * Proof-of-work capture. Reads where/when a photo was taken BEFORE compression (canvas re-encoding strips EXIF),
 * and asks the phone for its current location once per batch as a fallback. The server re-checks everything:
 * distance from the reported pin, photo age, reused photos (apps/cases/evidence.py).
 *
 * Phone location needs a secure page (HTTPS, or localhost during development).
 */
import { compressImage } from "@/utils/compressImage";

export type PhotoMeta = {
  exif_lat?: number | null;
  exif_lng?: number | null;
  exif_time?: string | null;
  device_lat?: number | null;
  device_lng?: number | null;
  device_accuracy?: number | null;
  /** Taken with "Kunan ngayon" (camera opened from the form), not picked from the gallery. */
  live?: boolean;
  /** AI-source / Content Credentials marker found in the ORIGINAL file (compression removes it). */
  ai_marker?: AiMarker;
};

export type AiMarker = "ai_generated" | "ai_edited" | "credentials" | null;

// Same terms the server looks for (apps/cases/credentials.py). Finding one is strong evidence; not finding one
// proves nothing, because screenshots and chat apps remove metadata.
const AI_GENERATED = ["/trainedAlgorithmicMedia", '"trainedAlgorithmicMedia', ">trainedAlgorithmicMedia",
  "digitalsourcetype/algorithmicMedia"];
const AI_EDITED = ["compositeWithTrainedAlgorithmicMedia", "compositeSynthetic"];

export async function readAiMarker(file: File): Promise<AiMarker> {
  try {
    const bytes = new Uint8Array(await file.slice(0, 16 * 1024 * 1024).arrayBuffer());
    const text = new TextDecoder("latin1").decode(bytes);
    if (AI_GENERATED.some((m) => text.includes(m))) return "ai_generated";
    if (AI_EDITED.some((m) => text.includes(m))) return "ai_edited";
    if (text.includes("jumb") && text.includes("c2pa")) return "credentials";
    return null;
  } catch {
    return null;
  }
}

export type EvidencePhoto = { file: File; preview: string; meta: PhotoMeta };

/** Camera data read from the original file, plus the AI-source marker check. */
export async function readExif(file: File): Promise<Pick<PhotoMeta, "exif_lat" | "exif_lng" | "exif_time" | "ai_marker">> {
  const ai_marker = await readAiMarker(file);
  return { ...(await readCamera(file)), ...(ai_marker ? { ai_marker } : {}) };
}

async function readCamera(file: File): Promise<Pick<PhotoMeta, "exif_lat" | "exif_lng" | "exif_time">> {
  try {
    const exifr = (await import("exifr")).default;
    const data = await exifr.parse(file, { gps: true, pick: ["DateTimeOriginal", "CreateDate", "latitude", "longitude"] });
    if (!data) return {};
    const t: Date | undefined = data.DateTimeOriginal ?? data.CreateDate;
    return {
      exif_lat: typeof data.latitude === "number" ? data.latitude : null,
      exif_lng: typeof data.longitude === "number" ? data.longitude : null,
      exif_time: t instanceof Date && !isNaN(t.getTime()) ? t.toISOString() : null,
    };
  } catch {
    return {};
  }
}

export function currentPosition(timeoutMs = 10000): Promise<GeolocationPosition | null> {
  if (!("geolocation" in navigator) || !window.isSecureContext) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(resolve, () => resolve(null), {
      enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60000,
    });
  });
}

export async function preparePhotos(files: File[]): Promise<EvidencePhoto[]> {
  const [pos, ...exifs] = await Promise.all([currentPosition(), ...files.map(readExif)]);
  return Promise.all(files.map(async (f, i) => {
    const file = await compressImage(f);
    return {
      file,
      preview: URL.createObjectURL(file),
      meta: {
        ...exifs[i],
        device_lat: pos?.coords.latitude ?? null,
        device_lng: pos?.coords.longitude ?? null,
        device_accuracy: pos ? Math.round(pos.coords.accuracy) : null,
      },
    };
  }));
}

export function locationSource(m: PhotoMeta): "exif" | "device" | "none" {
  if (m.exif_lat != null && m.exif_lng != null) return "exif";
  if (m.device_lat != null && m.device_lng != null) return "device";
  return "none";
}

/** Fields for FormData: files + aligned JSON metadata. */
export function evidenceFields(photos: EvidencePhoto[], fileKey: string, metaKey: string) {
  return { [fileKey]: photos.map((p) => p.file), [metaKey]: JSON.stringify(photos.map((p) => p.meta)) };
}
