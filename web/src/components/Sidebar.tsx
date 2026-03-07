'use client'
import { useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { clearToken, authApi } from '@/lib/api'
import {
    FolderOpen, Upload, Download, Activity,
    Settings, ShieldAlert, LogOut, Zap,
    ChevronRight,
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
    const [isHovered, setIsHovered] = useState(false)

    if (pathname === '/') return null

    async function handleLogout() {
        try { await authApi.logout() } catch (_) { }
        clearToken()
        router.push('/')
    }

    return (
        <motion.aside
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            animate={{ width: isHovered ? 260 : 80 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            style={{
                position: 'fixed',
                left: 16,
                top: 16,
                bottom: 16,
                zIndex: 100,
                backgroundColor: 'rgba(15, 23, 42, 0.4)',
                backdropFilter: 'blur(24px)',
                WebkitBackdropFilter: 'blur(24px)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '24px',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
                transition: 'border-color 0.3s',
            }}
            className={isHovered ? 'sidebar-expanded' : ''}
        >
            {/* Branding */}
            <div style={{ padding: '24px 24px', display: 'flex', alignItems: 'center', gap: 16 }}>
                <div style={{
                    minWidth: 32, height: 32, borderRadius: 10,
                    background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 0 15px rgba(56, 189, 248, 0.3)',
                }}>
                    <Zap size={18} color="#020617" />
                </div>
                <AnimatePresence>
                    {isHovered && (
                        <motion.span
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                            className="logo"
                            style={{ fontSize: '1.25rem', whiteSpace: 'nowrap' }}
                        >
                            YotuDrive
                        </motion.span>
                    )}
                </AnimatePresence>
            </div>

            {/* Nav */}
            <nav style={{ flex: 1, padding: '12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {NAV.map(({ href, icon: Icon, label }) => {
                    const active = pathname.startsWith(href)
                    return (
                        <Link key={href} href={href} style={{ textDecoration: 'none' }}>
                            <motion.div
                                whileHover={{ x: 4 }}
                                style={{
                                    height: 48,
                                    borderRadius: 16,
                                    display: 'flex',
                                    alignItems: 'center',
                                    padding: '0 15px',
                                    gap: 16,
                                    color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                                    backgroundColor: active ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                                    position: 'relative',
                                    overflow: 'hidden',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s',
                                }}
                            >
                                {active && (
                                    <motion.div
                                        layoutId="sidebar-nav-v2"
                                        style={{
                                            position: 'absolute', left: 0,
                                            width: 3, height: 20,
                                            background: 'var(--accent-primary)',
                                            borderRadius: '0 4px 4px 0',
                                        }}
                                    />
                                )}
                                <Icon size={20} style={{ minWidth: 20 }} />
                                <AnimatePresence>
                                    {isHovered && (
                                        <motion.span
                                            initial={{ opacity: 0, x: -10 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            exit={{ opacity: 0, x: -10 }}
                                            style={{ fontSize: '0.9375rem', fontWeight: active ? 600 : 500, whiteSpace: 'nowrap' }}
                                        >
                                            {label}
                                        </motion.span>
                                    )}
                                </AnimatePresence>
                            </motion.div>
                        </Link>
                    )
                })}
            </nav>

            {/* Logout */}
            <div style={{ padding: '12px', borderTop: '1px solid var(--border-subtle)' }}>
                <button
                    className="nav-item"
                    style={{ 
                        width: '100%', border: 'none', background: 'none', padding: '0 15px', 
                        height: 48, borderRadius: 16, gap: 16, margin: 0,
                        color: 'var(--error)', transition: 'all 0.2s'
                    }}
                    onClick={handleLogout}
                >
                    <LogOut size={18} style={{ minWidth: 18 }} />
                    <AnimatePresence>
                        {isHovered && (
                            <motion.span
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -10 }}
                                style={{ fontSize: '0.9375rem', fontWeight: 500, whiteSpace: 'nowrap' }}
                            >
                                Sign Out
                            </motion.span>
                        )}
                    </AnimatePresence>
                </button>
            </div>
        </motion.aside>
    )
}
