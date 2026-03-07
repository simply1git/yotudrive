'use client'
import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { settingsApi, getToken, API_BASE } from '@/lib/api'
import { 
  Settings, Save, Server, SlidersHorizontal, 
  Cpu, Monitor, Zap, ShieldCheck, 
  Trash2, Database, Info, Copy, Check
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

export default function SettingsPage() {
    const { data, isLoading, refetch } = useQuery({
        queryKey: ['settings'],
        queryFn: () => settingsApi.get()
    })

    const [form, setForm] = useState<Record<string, any>>({})
    const [successMsg, setSuccessMsg] = useState('')
    const [token, setTokenState] = useState('')
    const [copiedField, setCopiedField] = useState<string | null>(null)

    useEffect(() => {
        setTokenState(getToken() || '')
    }, [])

    const copyToClipboard = (text: string, field: string) => {
        navigator.clipboard.writeText(text)
        setCopiedField(field)
        setTimeout(() => setCopiedField(null), 2000)
    }

    useEffect(() => {
        if (data?.settings) setForm(data.settings)
    }, [data])

    const saveMut = useMutation({
        mutationFn: (updates: any) => settingsApi.update(updates),
        onSuccess: () => {
            setSuccessMsg('Hyper-parameters synchronized.')
            setTimeout(() => setSuccessMsg(''), 3000)
            refetch()
        }
    })

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        saveMut.mutate(form)
    }

    if (isLoading) return <div className="p-8 text-muted">Awaiting system link...</div>

    return (
        <div className="max-w-5xl mx-auto pb-20">
            <header className="page-header mb-12 flex justify-between items-end">
                <div>
                    <h1 className="page-title text-glow flex items-center gap-3">
                        <Settings size={32} className="text-accent" />
                        Settings
                    </h1>
                    <p className="page-subtitle">Configure application defaults and resource limits.</p>
                </div>
            </header>

            <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                <div className="lg:col-span-8 space-y-8">
                    {/* Encoding Engine */}
                    <section className="card shadow-glow-hover transition-all">
                        <div className="p-6 border-b border-subtle flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center text-accent">
                                <Cpu size={20} />
                            </div>
                            <div>
                                <h2 className="font-bold">Codec Defaults</h2>
                                <p className="text-xs text-muted">Baseline parameters for the V5 engine.</p>
                            </div>
                        </div>
                        <div className="p-8 grid grid-cols-1 md:grid-cols-2 gap-8">
                            <div className="input-group">
                                <label className="input-label">Block Size (Density)</label>
                                <select className="input" value={form.block_size || 2} onChange={e => setForm({ ...form, block_size: parseInt(e.target.value) })}>
                                    <option value={1}>1px (Ultra Slow)</option>
                                    <option value={2}>2px (Standard)</option>
                                    <option value={4}>4px (Resilient)</option>
                                </select>
                            </div>
                            <div className="input-group">
                                <label className="input-label">RS Parity Bytes</label>
                                <input type="number" className="input" min={0} max={128} value={form.ecc_bytes || 32} onChange={e => setForm({ ...form, ecc_bytes: parseInt(e.target.value) })} />
                            </div>
                            <div className="input-group">
                                <label className="input-label">Parallel Threads</label>
                                <input type="number" className="input" min={1} max={32} value={form.threads || 4} onChange={e => setForm({ ...form, threads: parseInt(e.target.value) })} />
                            </div>
                            <div className="input-group">
                                <label className="input-label">Global Video Codec</label>
                                <select className="input" value={form.encoder || 'libx264'} onChange={e => setForm({ ...form, encoder: e.target.value })}>
                                    <option value="libx264">libx264 (Standard)</option>
                                    <option value="h264_nvenc">h264_nvenc (NVIDIA)</option>
                                    <option value="h264_qsv">h264_qsv (Intel)</option>
                                </select>
                            </div>
                        </div>
                    </section>

                    {/* Global Behaviors */}
                    <section className="card shadow-glow-hover transition-all">
                        <div className="p-6 border-b border-subtle flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-accent-secondary/10 flex items-center justify-center text-accent-secondary">
                                <SlidersHorizontal size={20} />
                            </div>
                            <div>
                                <h2 className="font-bold">Auto-Management</h2>
                                <p className="text-xs text-muted">Intelligent system cleanup and optimization.</p>
                            </div>
                        </div>
                        <div className="p-8 space-y-6">
                            <label className="flex items-center gap-4 p-4 rounded-2xl bg-surface/30 border border-subtle cursor-pointer hover:border-accent/40 transition-colors">
                                <input
                                    type="checkbox"
                                    checked={form.auto_cleanup ?? true}
                                    onChange={e => setForm({ ...form, auto_cleanup: e.target.checked })}
                                    className="w-5 h-5 rounded border-subtle text-accent focus:ring-accent"
                                />
                                <div>
                                    <span className="font-bold text-sm text-primary">Ephemeral Data Purge</span>
                                    <p className="text-xs text-muted mt-0.5">Automatically remove temporary frames after conversion cycles.</p>
                                </div>
                            </label>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div className="input-group">
                                    <label className="input-label">Archive Compression</label>
                                    <select className="input" value={form.compression || 'Fast (Deflate)'} onChange={e => setForm({ ...form, compression: e.target.value })}>
                                        <option value="Store (No Compression)">Off (No Compression)</option>
                                        <option value="Fast (Deflate)">Deflate (Standard)</option>
                                        <option value="Best (LZMA)">LZMA (Max Density)</option>
                                    </select>
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Auto-Segmentation</label>
                                    <select className="input" value={form.split_size || 'No Split'} onChange={e => setForm({ ...form, split_size: e.target.value })}>
                                        <option value="No Split">Full File</option>
                                        <option value="1 GB">1 GB Blocks</option>
                                        <option value="10 GB">10 GB Blocks</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </section>
                </div>

                {/* Status Sidebar */}
                <div className="lg:col-span-4 space-y-8">
                    <div className="card p-6 bg-accent-glow border-accent/20">
                        <div className="flex items-center gap-3 mb-6">
                            <Database size={24} className="text-accent" />
                            <h3 className="font-bold font-display">Engine State</h3>
                        </div>
                        <div className="space-y-4">
                            <div className="flex justify-between items-center text-sm">
                                <span className="text-muted">Database Connection</span>
                                <span className="text-success font-bold flex items-center gap-1">
                                    <span className="w-2 h-2 rounded-full bg-success animate-pulse" /> Live
                                </span>
                            </div>
                            <div className="flex justify-between items-center text-sm">
                                <span className="text-muted">RS-V5 Availability</span>
                                <span className="text-primary font-bold">100%</span>
                            </div>
                        </div>
                        
                        <div className="mt-10">
                            <button 
                                type="submit" 
                                className="btn btn-primary w-full py-4 font-bold h-auto shadow-glow group"
                                disabled={saveMut.isPending}
                            >
                                <Save size={18} className="group-hover:scale-110 transition-transform" /> 
                                {saveMut.isPending ? 'Syncing...' : 'Apply System Changes'}
                            </button>
                            <p className="text-[10px] text-center text-muted mt-4 uppercase tracking-widest font-bold">
                                {successMsg || 'Changes are persistent across sessions'}
                            </p>
                        </div>
                    </div>

                    <div className="card p-6 border-warning/20 bg-warning/5">
                        <div className="flex gap-4">
                            <Info size={20} className="text-warning shrink-0" />
                            <div>
                                <h4 className="text-sm font-bold text-warning mb-1">Performance Warning</h4>
                                <p className="text-xs text-muted leading-relaxed">
                                    Reducing block size below 2px significantly increases CPU overhead and RAM usage. 
                                    Use only for critical small-payload archives.
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="card p-6 border-accent/20 bg-accent/5 overflow-hidden">
                        <div className="flex items-center gap-3 mb-5">
                            <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center text-accent">
                                <Zap size={16} />
                            </div>
                            <h3 className="font-bold text-sm tracking-tight text-accent">Nebula Worker Config</h3>
                        </div>
                        
                        <div className="space-y-5">
                            <div className="space-y-2">
                                <label className="text-[10px] font-bold text-muted uppercase tracking-widest ml-1">Orchestrator URL</label>
                                <div className="group relative">
                                    <div className="p-3 bg-surface/40 rounded-xl border border-subtle font-mono text-[11px] leading-tight break-all pr-10">
                                        {API_BASE}
                                    </div>
                                    <button 
                                        type="button"
                                        onClick={() => copyToClipboard(API_BASE, 'url')}
                                        className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-accent/10 text-accent transition-all"
                                    >
                                        {copiedField === 'url' ? <Check size={14} /> : <Copy size={14} />}
                                    </button>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <label className="text-[10px] font-bold text-muted uppercase tracking-widest ml-1">Access Token</label>
                                <div className="group relative">
                                    <div className="p-3 bg-surface/40 rounded-xl border border-subtle font-mono text-[11px] leading-tight pr-10 overflow-hidden text-ellipsis whitespace-nowrap">
                                        {token || 'No session token'}
                                    </div>
                                    <button 
                                        type="button"
                                        onClick={() => copyToClipboard(token, 'token')}
                                        className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-accent/10 text-accent transition-all"
                                    >
                                        {copiedField === 'token' ? <Check size={14} /> : <Copy size={14} />}
                                    </button>
                                </div>
                            </div>
                            
                            <p className="text-[10px] text-muted italic leading-relaxed px-1">
                                Paste these into your Nebula script on Colab to authorize your remote worker.
                            </p>
                        </div>
                    </div>
                </div>
            </form>
        </div>
    )
}
