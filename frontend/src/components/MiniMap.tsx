'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import Map, { Marker, NavigationControl, MapRef } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { HospitalRecommendation, NetworkProvider } from '@/lib/types'

interface Props {
  hospitals: HospitalRecommendation[]
  userLocation?: { lat: number; lon: number }
  networkProviders?: NetworkProvider[]
}

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

function fmt(km: number | null) {
  if (km === null || km === undefined) return null
  return `${km.toFixed(1)} km`
}

// Excluye providers que coincidan en nombre con un hospital recomendado
// (case-insensitive, normalizando espacios) para evitar pintar dos pines encima.
function notInRecommended(provName: string, recommended: HospitalRecommendation[]) {
  const norm = (s: string) => s.toLowerCase().replace(/\s+/g, ' ').trim()
  const recSet = new Set(recommended.map(h => norm(h.nombre)))
  return !recSet.has(norm(provName))
}

export default function MiniMap({ hospitals, userLocation, networkProviders = [] }: Props) {
  const mapRef = useRef<MapRef>(null)
  const [activeIdx, setActiveIdx] = useState<number | null>(null)
  const [hoverProvIdx, setHoverProvIdx] = useState<number | null>(null)

  const points = useMemo(
    () => hospitals.filter(h => h.lat !== null && h.lon !== null),
    [hospitals]
  )

  // Capa de fondo: prestadores de la red con coords y que no estén en los recomendados
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

  const initialView = useMemo(() => {
    const all = [
      ...points.map(p => ({ lat: p.lat as number, lon: p.lon as number })),
      ...networkPoints.map(p => ({ lat: p.lat as number, lon: p.lon as number })),
    ]
    if (all.length === 0) {
      return { longitude: -78.4813, latitude: -0.1807, zoom: 11 }
    }
    const lats = all.map(p => p.lat)
    const lons = all.map(p => p.lon)
    return {
      longitude: (Math.min(...lons) + Math.max(...lons)) / 2,
      latitude: (Math.min(...lats) + Math.max(...lats)) / 2,
      zoom: 11,
    }
  }, [points, networkPoints])

  // Encuadre automático: si hay recomendados, encuadra los recomendados;
  // si no, encuadra TODA la red de la aseguradora.
  useEffect(() => {
    if (!mapRef.current) return
    const focus = points.length > 0 ? points : networkPoints
    if (focus.length === 0) return
    const lats = focus.map(h => h.lat as number)
    const lons = focus.map(h => h.lon as number)
    if (userLocation) {
      lats.push(userLocation.lat); lons.push(userLocation.lon)
    }
    const minLat = Math.min(...lats), maxLat = Math.max(...lats)
    const minLon = Math.min(...lons), maxLon = Math.max(...lons)
    if (minLat === maxLat && minLon === maxLon) {
      mapRef.current.flyTo({ center: [minLon, minLat], zoom: 14, duration: 600 })
      return
    }
    mapRef.current.fitBounds(
      [[minLon, minLat], [maxLon, maxLat]],
      { padding: { top: 60, bottom: 40, left: 180, right: 40 }, duration: 800, maxZoom: points.length > 0 ? 14 : 12 }
    )
  }, [points, networkPoints, userLocation])

  return (
    <div style={{ width: '100%', height: '100%', borderRadius: 10, overflow: 'hidden', position: 'relative', background: '#F8FAFC' }}>
      <Map
        ref={mapRef}
        initialViewState={{ ...initialView, pitch: 0, bearing: 0 }}
        mapStyle={MAP_STYLE}
        style={{ width: '100%', height: '100%' }}
      >
        {/* ── Capa de fondo: TODOS los prestadores en la red de la aseguradora ── */}
        {networkPoints.map((p, i) => {
          const isHover = i === hoverProvIdx
          return (
            <Marker
              key={`net-${p.nombre}-${i}`}
              longitude={p.lon as number}
              latitude={p.lat as number}
              anchor="center"
            >
              <div
                onMouseEnter={() => setHoverProvIdx(i)}
                onMouseLeave={() => setHoverProvIdx(prev => (prev === i ? null : prev))}
                style={{ position: 'relative', cursor: 'pointer' }}
              >
                {isHover && (
                  <div style={{
                    position: 'absolute', bottom: '160%', left: '50%', transform: 'translateX(-50%)',
                    background: '#fff', padding: '5px 9px', borderRadius: 6,
                    boxShadow: '0 4px 14px rgba(15,23,42,.18)', fontSize: 11, fontWeight: 700,
                    color: '#0F172A', whiteSpace: 'nowrap', border: '1px solid #94A3B8',
                    pointerEvents: 'none', zIndex: 4,
                  }}>
                    <div>{p.nombre}</div>
                    {p.categoria && <div style={{ fontWeight: 500, fontSize: 10, color: '#64748B', marginTop: 2 }}>{p.categoria}</div>}
                    {p.ciudad && <div style={{ fontWeight: 500, fontSize: 10, color: '#64748B' }}>{p.ciudad}</div>}
                  </div>
                )}
                <div style={{
                  width: isHover ? 12 : 9, height: isHover ? 12 : 9,
                  borderRadius: '50%', background: '#94A3B8',
                  border: '2px solid #fff',
                  boxShadow: '0 1px 3px rgba(15,23,42,.25)',
                  transition: 'all .12s ease',
                  opacity: .85,
                }}/>
              </div>
            </Marker>
          )
        })}

        {/* ── Hospitales recomendados (encima, grandes y numerados) ── */}
        {points.map((h, i) => {
          const isBest = i === bestIdx
          const isActive = i === activeIdx
          const color = isBest ? '#059669' : '#1E40AF'
          return (
            <Marker
              key={`${h.nombre}-${i}`}
              longitude={h.lon as number}
              latitude={h.lat as number}
              anchor="bottom"
            >
              <div
                onMouseEnter={() => setActiveIdx(i)}
                onMouseLeave={() => setActiveIdx(prev => (prev === i ? null : prev))}
                style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', cursor: 'pointer', position: 'relative' }}
              >
                {(isActive || isBest) && (
                  <div style={{
                    position: 'absolute', bottom: '120%', left: '50%', transform: 'translateX(-50%)',
                    background: '#fff', padding: '6px 10px', borderRadius: 8,
                    boxShadow: '0 6px 20px rgba(15,23,42,.18)', fontSize: 11.5, fontWeight: 700,
                    color: '#0F172A', whiteSpace: 'nowrap', border: `1.5px solid ${color}`,
                    pointerEvents: 'none', zIndex: 5,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {isBest && <span style={{ color: '#059669', fontSize: 10 }}>★ MEJOR PRECIO</span>}
                      <span>{h.nombre}</span>
                    </div>
                    <div style={{ color, marginTop: 2, fontSize: 13 }}>${h.copago_paciente.toFixed(2)} USD</div>
                  </div>
                )}

                {isBest && (
                  <span style={{
                    position: 'absolute', bottom: 28, width: 56, height: 56, borderRadius: '50%',
                    background: 'rgba(5,150,105,.18)', animation: 'mb-pulse 1.6s ease-out infinite',
                  }} />
                )}

                <div style={{
                  width: 36, height: 36, borderRadius: '50%',
                  background: color, border: '3px solid #fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontWeight: 800, fontSize: 14,
                  boxShadow: isBest ? '0 6px 20px rgba(5,150,105,.55)' : '0 4px 14px rgba(15,23,42,.32)',
                  transform: isActive ? 'scale(1.08)' : 'scale(1)',
                  transition: 'transform .15s ease',
                }}>
                  {i + 1}
                </div>
                <div style={{ width: 2, height: 8, background: color }} />
                <div style={{ width: 12, height: 4, borderRadius: '50%', background: 'rgba(0,0,0,.25)', filter: 'blur(2px)' }} />
              </div>
            </Marker>
          )
        })}

        {userLocation && (
          <Marker longitude={userLocation.lon} latitude={userLocation.lat} anchor="center">
            <div style={{
              width: 14, height: 14, borderRadius: '50%', background: '#EF4444',
              border: '2px solid #fff', boxShadow: '0 0 0 6px rgba(239,68,68,.25)',
            }} />
          </Marker>
        )}

        <NavigationControl position="bottom-right" showCompass={false} />
      </Map>

      {/* Leyenda lateral con TOP recomendados */}
      {points.length > 0 && (
        <div style={{
          position: 'absolute', top: 10, left: 10,
          background: 'rgba(255,255,255,.96)', backdropFilter: 'blur(6px)',
          borderRadius: 10, padding: 8, boxShadow: '0 6px 18px rgba(15,23,42,.12)',
          border: '1px solid #E2E8F0', maxWidth: 220,
          fontFamily: 'inherit',
        }}>
          <div style={{ fontSize: 10, fontWeight: 800, color: '#64748B', letterSpacing: .6, marginBottom: 6, textTransform: 'uppercase' }}>
            Top recomendados
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {points.map((h, i) => {
              const isBest = i === bestIdx
              const color = isBest ? '#059669' : '#1E40AF'
              return (
                <button
                  key={`legend-${i}`}
                  onClick={() => {
                    setActiveIdx(i)
                    mapRef.current?.flyTo({ center: [h.lon as number, h.lat as number], zoom: 15, duration: 500 })
                  }}
                  onMouseEnter={() => setActiveIdx(i)}
                  onMouseLeave={() => setActiveIdx(null)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '5px 6px',
                    border: 'none', background: i === activeIdx ? '#F1F5F9' : 'transparent',
                    borderRadius: 6, cursor: 'pointer', textAlign: 'left', width: '100%',
                    fontFamily: 'inherit',
                  }}
                >
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
                </button>
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

      {/* Leyenda mínima cuando solo hay providers de la red (sin recomendaciones aún) */}
      {points.length === 0 && networkPoints.length > 0 && (
        <div style={{
          position: 'absolute', top: 10, left: 10,
          background: 'rgba(255,255,255,.96)', backdropFilter: 'blur(6px)',
          borderRadius: 10, padding: '8px 10px', boxShadow: '0 6px 18px rgba(15,23,42,.12)',
          border: '1px solid #E2E8F0', fontFamily: 'inherit',
        }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: '#0F172A' }}>
            Tu red ({networkPoints.length} prestadores)
          </div>
          <div style={{ fontSize: 10.5, color: '#64748B', marginTop: 2 }}>
            Describe síntomas para ver los más recomendados
          </div>
        </div>
      )}

      <style jsx>{`
        @keyframes mb-pulse {
          0%   { transform: scale(.6); opacity: .9; }
          100% { transform: scale(1.6); opacity: 0; }
        }
      `}</style>
    </div>
  )
}
