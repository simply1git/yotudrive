'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { authApi, setToken } from '@/lib/api'
import { Zap, Mail, Chrome } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleDevLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await authApi.devLogin(email.trim().toLowerCase())
      setToken(res.session.bearer)
      router.push('/library')
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Login failed. Email not in allowlist.')
    } finally {
      setLoading(false)
    }
  }

  async function handleGoogleLogin() {
    setLoading(true)
    setError('')
    try {
      const res = await authApi.googleStart()
      if (res.auth_url) window.location.href = res.auth_url
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Google OAuth not configured.')
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', padding: '2rem',
      background: 'radial-gradient(ellipse 100% 100% at 50% 0%, rgba(99,102,241,0.08) 0%, transparent 60%)',
    }}>
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
        style={{ width: '100%', maxWidth: 420 }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{
            width: 64, height: 64, borderRadius: 18, margin: '0 auto 1rem',
            background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 8px 32px rgba(99,102,241,0.4)',
          }}>
            <Zap size={28} color="white" />
          </div>
          <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            YotuDrive
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: 6, fontSize: '0.9rem' }}>
            Infinite cloud storage on YouTube
          </p>
        </div>

        {/* Card */}
        <div className="card card-body" style={{ padding: '2rem' }}>
          {/* Google */}
          <button
            className="btn btn-ghost w-full"
            onClick={handleGoogleLogin}
            disabled={loading}
            style={{ marginBottom: '1.25rem', justifyContent: 'center', padding: '0.75rem' }}
          >
            <Chrome size={18} />
            Continue with Google
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
            <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
              or sign in with email
            </span>
            <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
          </div>

          <form onSubmit={handleDevLogin}>
            <div className="input-group" style={{ marginBottom: '1.25rem' }}>
              <label className="input-label">Email address</label>
              <div style={{ position: 'relative' }}>
                <input
                  type="email"
                  className="input"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  style={{ paddingLeft: '2.5rem' }}
                  required
                />
                <Mail size={15} style={{ position: 'absolute', left: '0.875rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              </div>
            </div>

            {error && (
              <div style={{ marginBottom: '1rem', padding: '0.75rem', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, fontSize: '0.8125rem', color: 'var(--error)' }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={loading || !email}
              style={{ justifyContent: 'center', padding: '0.75rem' }}
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        </div>

        <p style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '1.5rem' }}>
          Closed beta — access by invitation only
        </p>
      </motion.div>
    </div>
  )
}
