import dynamic from 'next/dynamic'

const ChatWindow = dynamic(() => import('@/components/ChatWindow'), {
  ssr: false,
  loading: () => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 18, fontWeight: 600, color: '#0F172A' }}>Cargando MediBot...</div>
        <div style={{ fontSize: 13, color: '#64748B', marginTop: 8 }}>Preparando el asistente médico</div>
      </div>
    </div>
  ),
})

export default function Home() {
  return <ChatWindow />
}
