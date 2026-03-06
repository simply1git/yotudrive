'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { clearToken, authApi } from '@/lib/api'
import {
    FolderOpen, Upload, Download, Activity,
    Settings, ShieldAlert, LogOut, Zap,
} from 'lucide-react'

const NAV = [
    { href: '/library', icon: FolderOpen, label: 'Library' },
    { href: '/encoder', icon: Upload, label: 'Encoder' },
    { href: '/decoder', icon: Download, label: 'Decoder' },
    { href: '/transfers', icon: Activity, label: 'Transfers' },
    { href: '/settings', icon: Settings, label: 'Settings' },
    { href: '/admin', icon: ShieldAlert, label: 'Admin Panel' },
]

export default function Sidebar() {
    const pathname = usePathname()
    const router = useRouter()

    async function handleLogout() {
        try { await authApi.logout() } catch (_) { }
        clearToken()
        router.push('/')
    }

    return (
        <aside className="sidebar">
            {/* Branding */}
            <div style={{ padding: '1.5rem 1rem 1rem', borderBottom: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                    <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <Zap size={16} color="white" />
                    </div>
                    <span className="logo">YotuDrive</span>
                </div>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.375rem', marginLeft: '0.25rem' }}>
                    Infinite YouTube Storage
                </p>
            </div>

            {/* Nav */}
            <nav style={{ flex: 1, padding: '0.75rem 0', overflowY: 'auto' }}>
                {NAV.map(({ href, icon: Icon, label }) => {
                    const active = pathname.startsWith(href)
                    return (
                        <Link key={href} href={href} className={`nav-item ${active ? 'active' : ''}`}>
                            <Icon size={16} className="nav-icon" />
                            {label}
                            {active && (
                                <motion.span
                                    layoutId="sidebar-indicator"
                                    style={{
                                        position: 'absolute', left: 0,
                                        width: 3, height: '60%',
                                        background: 'var(--accent-primary)',
                                        borderRadius: '0 4px 4px 0',
                                    }}
                                />
                            )}
                        </Link>
                    )
                })}
            </nav>

            {/* Logout */}
            <div style={{ padding: '0.75rem', borderTop: '1px solid var(--border-subtle)' }}>
                <button
                    className="nav-item"
                    style={{ width: '100%', background: 'none', border: 'none', position: 'relative' }}
                    onClick={handleLogout}
                >
                    <LogOut size={16} />
                    Sign Out
                </button>
            </div>
        </aside>
    )
}
