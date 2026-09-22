import { MapContainer, Marker, useMapEvents } from 'react-leaflet'
import MapTiles from './MapTiles'

import { DEMO_CITY_CENTER, pinMarker } from './mapIcons'

type LatLng = { lat: number; lng: number }

function ClickHandler({ onPick }: { onPick: (p: LatLng) => void }) {
  useMapEvents({
    click(e) {
      onPick({ lat: e.latlng.lat, lng: e.latlng.lng })
    },
  })
  return null
}

export default function LocationPicker({
  value,
  onChange,
}: {
  value: LatLng | null
  onChange: (p: LatLng) => void
}) {
  return (
    <div>
      <div className="h-64 overflow-hidden rounded-md border border-slate-300">
        <MapContainer center={DEMO_CITY_CENTER} zoom={13} scrollWheelZoom={false}>
          <MapTiles />
          <ClickHandler onPick={onChange} />
          {value && <Marker position={[value.lat, value.lng]} icon={pinMarker} />}
        </MapContainer>
      </div>

      {/* Keyboard/screen-reader accessible equivalent to clicking the map (WCAG AA). */}
      <fieldset className="mt-2 grid grid-cols-2 gap-2">
        <legend className="sr-only">Coordinates</legend>
        <div>
          <label htmlFor="lat-input" className="field-label">
            Latitude
          </label>
          <input
            id="lat-input"
            type="number"
            step="0.000001"
            className="field-input"
            value={value?.lat ?? ''}
            onChange={(e) => onChange({ lat: Number(e.target.value), lng: value?.lng ?? DEMO_CITY_CENTER[1] })}
          />
        </div>
        <div>
          <label htmlFor="lng-input" className="field-label">
            Longitude
          </label>
          <input
            id="lng-input"
            type="number"
            step="0.000001"
            className="field-input"
            value={value?.lng ?? ''}
            onChange={(e) => onChange({ lat: value?.lat ?? DEMO_CITY_CENTER[0], lng: Number(e.target.value) })}
          />
        </div>
      </fieldset>
    </div>
  )
}
