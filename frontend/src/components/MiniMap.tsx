'use client'

import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { HospitalRecommendation, NetworkProvider } from '@/lib/types'

interface Props {
  hospitals: HospitalRecommendation[]
  userLocation?: { lat: number; lon: number }
  networkProviders?: NetworkProvider[]
}

function fmt(km: number | null) {
  if (km === null || km === undefined) return null
  return `${km.toFixed(1)} km`
}

function notInRecommended(provName: string, recommended: HospitalRecommendation[]) {
  const norm = (s: string) => s.toLowerCase().replace(/\s+/g, ' ').trim()
  const recSet = new Set(recommended.map(h => norm(h.nombre)))
  return !recSet.has(norm(provName))
}

// ── Custom markers ──────────────────────────────────────────────
function createNumberMarker(number: number, isBest: boolean) {
  const color = isBest ? '#059669' : '#1E40AF'
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="
      width:36px;height:36px;border-radius:50%;background:${color};
      border:3px solid #fff;color:#fff;font-weight:800;font-size:14px;
      display:flex;align-items:center;justify-content:center;
      box-shadow:0 4px 14px rgba(15,23,42,.32);
    ">${number}</div>`,
    iconSize: [36, 36],
    iconAnchor: [18, 36],
    popupAnchor: [0, -36],
  })
}

function createNetworkMarker() {
  return L.divIcon({
    className: 'custom-marker-net',
    html: `<div style="
      width:10px;height:10px;border-radius:50%;background:#94A3B8;
      border:2px solid #fff;box-shadow:0 1px 3px rgba(15,23,42,.25);
    "></div>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
  })
}

function createUserMarker() {
  return L.divIcon({
    className: 'custom-marker-user',
    html: `<div style="
      width:14px;height:14px;border-radius:50%;background:#EF4444;
      border:2px solid #fff;box-shadow:0 0 0 6px rgba(239,68,68,.25);
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })
}

// ── Auto-fit map bounds ─────────────────────────────────────────
function MapFitter({
  points,
  networkPoints,
  userLocation,
}: {
  points: HospitalRecommendation[]
  networkPoints: NetworkProvider[]
  userLocation?: { lat: number; lon: number }
}) {
  const map = useMap()

  useEffect(() => {
    const focus = points.length > 0 ? points : networkPoints
    if (focus.length === 0) return

    const lats = focus.map(h => (h as any).lat as number)
    const lons = focus.map(h => (h as any).lon as number)
    if (userLocation) {
      lats.push(userLocation.lat)
      lons.push(userLocation.lon)
    }

    const bounds = L.latLngBounds(
      lats.map((lat, i) => [lat, lons[i]]) as [number, number][]
    )
    map.fitBounds(bounds, {
      padding: [40, 40],
      maxZoom: points.length > 0 ? 14 : 12,
    })
  }, [map, points, networkPoints, userLocation])

  return null
}

export default function MiniMap({ hospitals, userLocation, networkProviders = [] }: Props) {
  const points = useMemo(
    () => hospitals.filter(h => h.lat !== null && h.lon !== null),
    [hospitals]
  )

  const networkPoints = useMemo(
    () =>
      networkProviders.filter(
        p =>
          p.lat !== null &&
          p.lon !== null &&
          notInRecommended(p.nombre, points)
      ),
    [networkProviders, points]
  )

  const bestIdx = useMemo(() => {
    if (points.length === 0) return -1
    const min = Math.min(...points.map(h => h.copago_paciente))
    return points.findIndex(h => h.copago_paciente === min)
  }, [points])

  const initialCenter: [number, number] = useMemo(() => {
    const all = [
      ...points.map(p => ({ lat: p.lat!, lon: p.lon! })),
      ...networkPoints.map(p => ({ lat: p.lat!, lon: p.lon! })),
    ]
    if (all.length === 0) return [-0.1807, -78.4678]
    return [
      (Math.min(...all.map(p => p.lat)) + Math.max(...all.map(p => p.lat))) / 2,
      (Math.min(...all.map(p => p.lon)) + Math.max(...all.map(p => p.lon))) / 2,
    ]
  }, [points, networkPoints])

  return (
    <div style={{ width: '100%', height: '100%', borderRadius: 10, overflow: 'hidden', position: 'relative' }}>
      <MapContainer
        center={initialCenter}
        zoom={11}
        style={{ width: '100%', height: '100%' }}
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />

        <MapFitter points={points} networkPoints={networkPoints} userLocation={userLocation} />

        {/* Network providers (gray dots) */}
        {networkPoints.map((p, i) => (
          <Marker
            key={`net-${p.nombre}-${i}`}
            position={[p.lat!, p.lon!]}
            icon={createNetworkMarker()}
          >
              <Popup>
                <div style={{ fontSize: 12, fontWeight: 700 }}>{p.nombre}</div>
              </Popup>
          </Marker>
        ))}

        {/* Recommended hospitals (numbered pins) */}
        {points.map((h, i) => {
          const isBest = i === bestIdx
          return (
            <Marker
              key={`rec-${h.nombre}-${i}`}
              position={[h.lat!, h.lon!]}
              icon={createNumberMarker(i + 1, isBest)}
            >
              <Popup>
                <div style={{ fontSize: 13 }}>
                  <div style={{ fontWeight: 700 }}>{h.nombre}</div>
                  <div style={{ color: '#64748B', fontSize: 11 }}>{h.tipo}</div>
                  <div style={{ color: isBest ? '#059669' : '#1E40AF', fontWeight: 700, marginTop: 4 }}>
                    Copago: ${h.copago_paciente.toFixed(2)} USD
                  </div>
                  {h.distancia_km !== null && (
                    <div style={{ fontSize: 11, color: '#64748B' }}>
                      📍 {h.distancia_km.toFixed(1)} km
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          )
        })}

        {/* User location */}
        {userLocation && (
          <Marker
            position={[userLocation.lat, userLocation.lon]}
            icon={createUserMarker()}
          />
        )}
      </MapContainer>

      {/* Legend */}
      {points.length > 0 && (
        <div style={{
          position: 'absolute', top: 10, left: 10,
          background: 'rgba(255,255,255,.96)', backdropFilter: 'blur(6px)',
          borderRadius: 10, padding: 8, boxShadow: '0 6px 18px rgba(15,23,42,.12)',
          border: '1px solid #E2E8F0', maxWidth: 220,
          fontFamily: 'inherit', zIndex: 1000,
        }}>
          <div style={{ fontSize: 10, fontWeight: 800, color: '#64748B', letterSpacing: .6, marginBottom: 6, textTransform: 'uppercase' }}>
            Top recomendados
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {points.map((h, i) => {
              const isBest = i === bestIdx
              const color = isBest ? '#059669' : '#1E40AF'
              return (
                <div key={`legend-${i}`} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 6px' }}>
                  <div style={{
                    width: 22, height: 22, borderRadius: '50%', background: color,
                    color: '#fff', fontWeight: 800, fontSize: 11,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                  }}>{i + 1}</div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 11.5, fontWeight: 700, color: '#0F172A', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {h.nombre}
                    </div>
                    <div style={{ fontSize: 10.5, color: '#64748B', display: 'flex', gap: 6 }}>
                      <span style={{ color, fontWeight: 700 }}>${h.copago_paciente.toFixed(2)}</span>
                      {fmt(h.distancia_km) && <span>· {fmt(h.distancia_km)}</span>}
                    </div>
                  </div>
                  {isBest && <span style={{ fontSize: 9, color: '#059669', fontWeight: 800 }}>★</span>}
                </div>
              )
            })}
          </div>
          {networkPoints.length > 0 && (
            <div style={{
              marginTop: 8, paddingTop: 6, borderTop: '1px dashed #E2E8F0',
              display: 'flex', alignItems: 'center', gap: 6, fontSize: 10.5, color: '#64748B',
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%', background: '#94A3B8',
                border: '1.5px solid #fff', boxShadow: '0 1px 3px rgba(15,23,42,.25)',
              }} />
              <span>{networkPoints.length} más en tu red</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
