'use client'
import type { Metadata } from 'next'
import './globals.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import Sidebar from '@/components/Sidebar'
import { usePathname } from 'next/navigation'

const NO_SIDEBAR_ROUTES = ['/']

function LayoutInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const hideSidebar = NO_SIDEBAR_ROUTES.includes(pathname)

  if (hideSidebar) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg-base)' }}>
        <div className="mesh-bg" />
        {children}
      </div>
    )
  }

  return (
    <div className="layout">
      <div className="mesh-bg" />
      <Sidebar />
      <main className="main-content">
        <div style={{ maxWidth: 1400, margin: '0 auto' }}>
          {children}
        </div>
      </main>
    </div>
  )
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } })
  )

  return (
    <html lang="en">
      <head>
        <title>YotuDrive — Infinite Cloud Storage</title>
        <meta name="description" content="Store anything on YouTube — secure, free, unlimited cloud storage powered by YotuDrive's advanced encoding engine." />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>
        <QueryClientProvider client={queryClient}>
          <LayoutInner>{children}</LayoutInner>
        </QueryClientProvider>
      </body>
    </html>
  )
}
