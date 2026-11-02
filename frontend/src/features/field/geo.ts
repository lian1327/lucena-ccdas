export function haversineM(lat1: number, lng1: number, lat2: number, lng2: number) {
  const r = 6_371_000;
  const rad = Math.PI / 180;
  const dp = (lat2 - lat1) * rad;
  const dl = (lng2 - lng1) * rad;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}

/** Opens Google Maps (app or web) with directions to the site. */
export function directionsUrl(lat: number | string, lng: number | string) {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
}
