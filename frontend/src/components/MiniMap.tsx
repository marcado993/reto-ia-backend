'use client'

import { useState } from 'react'
import Map, { Marker, NavigationControl } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { HospitalRecommendation } from '@/lib/types'

interface Props {
  hospitals: HospitalRecommendation[]
  userLocation?: { lat: number; lon: number }
}

const COLORS = ['#059669', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6']

// MapLibre usa estilos libres (open source). Aquí usamos el estilo Positron de CartoDB que es gratuito y limpio.
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

export default function MiniMap({ hospitals, userLocation }: Props) {
  const firstH = hospitals.find(h => h.lat !== null && h.lon !== null)

  const [viewState, setViewState] = useState({
    longitude: firstH?.lon ?? -78.4813,
    latitude:  firstH?.lat ?? -0.1807,
    zoom:      14,
    pitch:     45,
    bearing:   -15,
  })

  return (
    <div style={{ width: '100%', height: '100%', borderRadius: 10, overflow: 'hidden', position: 'relative' }}>
      <Map
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        mapStyle={MAP_STYLE}
        antialias
        style={{ width: '100%', height: '100%' }}
      >
        {/* Hospital markers */}
        {hospitals.map((h, i) => {
          if (h.lat === null || h.lon === null) return null
          const color = COLORS[i % COLORS.length]
          return (
            <Marker key={i} longitude={h.lon} latitude={h.lat} anchor="bottom">
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', cursor: 'pointer' }}>
                {/* Tooltip */}
                <div style={{
                  position: 'absolute', bottom: '110%', left: '50%', transform: 'translateX(-50%)',
                  background: '#fff', padding: '5px 9px', borderRadius: 7,
                  boxShadow: '0 4px 16px rgba(0,0,0,.18)', fontSize: 11, fontWeight: 700,
                  color: '#0F172A', whiteSpace: 'nowrap', border: `1.5px solid ${color}`,
                  fontFamily: 'Plus Jakarta Sans, system-ui, sans-serif',
                }}>
                  {h.nombre}
                  <br />
                  <span style={{ color, fontWeight: 700 }}>${h.copago_paciente.toFixed(2)}</span>
                </div>
                {/* Pin */}
                <div style={{
                  width: 30, height: 30, borderRadius: '50%',
                  background: color, border: '2.5px solid #fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontWeight: 800, fontSize: 13,
                  boxShadow: '0 4px 14px rgba(0,0,0,.3)',
                  fontFamily: 'Plus Jakarta Sans, system-ui, sans-serif',
                }}>
                  {i + 1}
                </div>
                <div style={{ width: 2, height: 8, background: color, borderRadius: 1 }} />
                <div style={{ width: 10, height: 3, borderRadius: '50%', background: 'rgba(0,0,0,.2)', filter: 'blur(2px)' }} />
              </div>
            </Marker>
          )
        })}

        {/* User location dot */}
        {userLocation && (
          <Marker longitude={userLocation.lon} latitude={userLocation.lat} anchor="center">
            <div style={{
              width: 14, height: 14, borderRadius: '50%', background: '#EF4444',
              border: '2px solid #fff', boxShadow: '0 0 0 4px rgba(239,68,68,.3)',
            }} />
          </Marker>
        )}

        <NavigationControl position="bottom-right" />
      </Map>
    </div>
  )
}