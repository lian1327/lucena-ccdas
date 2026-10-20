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
};

export type EvidencePhoto = { file: File; preview: string; meta: PhotoMeta };

async function readExif(file: File): Promise<Pick<PhotoMeta, "exif_lat" | "exif_lng" | "exif_time">> {
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
