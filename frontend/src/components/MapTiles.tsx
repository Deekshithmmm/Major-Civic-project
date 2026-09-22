import { TileLayer } from 'react-leaflet'

/**
 * One tile layer for every map in the app, so the basemap can be changed in one place.
 *
 * Carto's Positron rather than standard OSM tiles: the markers here carry the meaning (status,
 * station, dropped pin) and a quieter basemap lets them read. Both are OpenStreetMap data and
 * need no API key.
 */
export default function MapTiles() {
  return (
    <TileLayer
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
      maxZoom={20}
    />
  )
}
