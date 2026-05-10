import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'MediBot AI — Entiende tu cobertura antes de atenderte',
  description: 'Estimador agéntico de copago y cobertura médica. Conoce tu copago exacto, especialidad sugerida y el hospital más económico de tu red en Ecuador.',
  keywords: ['copago', 'seguro médico', 'cobertura', 'síntomas', 'especialidad', 'Ecuador', 'IESS', 'BMI'],
  icons: { icon: '/favicon.ico' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
      </head>
      <body>{children}</body>
    </html>
  )
}