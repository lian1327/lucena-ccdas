import "leaflet";

declare module "leaflet" {
  type HeatLatLngTuple = [number, number, number];
  interface HeatLayerOptions {
    minOpacity?: number;
    maxZoom?: number;
    max?: number;
    radius?: number;
    blur?: number;
    gradient?: Record<number, string>;
  }
  interface HeatLayer extends Layer {
    setLatLngs(latlngs: HeatLatLngTuple[]): this;
    setOptions(options: HeatLayerOptions): this;
  }
  function heatLayer(latlngs: HeatLatLngTuple[], options?: HeatLayerOptions): HeatLayer;
}
