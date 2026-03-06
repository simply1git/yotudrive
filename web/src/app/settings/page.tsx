'use client'
import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { settingsApi } from '@/lib/api'
import { Settings, Save, Server, SlidersHorizontal, Package } from 'lucide-react'

export default function SettingsPage() {
    const { data, isLoading, refetch } = useQuery({
        queryKey: ['settings'],
        queryFn: () => settingsApi.get()
    })

    const [form, setForm] = useState<Record<string, any>>({})
    const [successMsg, setSuccessMsg] = useState('')

    useEffect(() => {
        if (data?.settings) setForm(data.settings)
    }, [data])

    const saveMut = useMutation({
        mutationFn: (updates: any) => settingsApi.update(updates),
        onSuccess: () => {
            setSuccessMsg('Settings saved successfully.')
            setTimeout(() => setSuccessMsg(''), 3000)
            refetch()
        }
    })

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        saveMut.mutate(form)
    }

    if (isLoading) return <div className="p-8 text-muted">Loading settings...</div>

    return (
        <div className="max-w-3xl">
            <header className="page-header mb-8">
                <h1 className="page-title"><Settings size={28} className="inline mr-3 text-accent" />Settings</h1>
                <p className="page-subtitle">Configure application defaults and resource limits.</p>
            </header>

            <form onSubmit={handleSubmit} className="space-y-6">
                {/* Encoding Engine */}
                <section className="card">
                    <div className="p-5 border-b border-subtle flex items-center gap-3">
                        <Server className="text-accent" size={20} />
                        <h2 className="font-semibold text-lg">Encoding Engine Defaults</h2>
                    </div>
                    <div className="p-6 grid-2 gap-6">
                        <div className="input-group">
                            <label className="input-label">Default Block Size (px)</label>
                            <select className="input" value={form.block_size || 2} onChange={e => setForm({ ...form, block_size: parseInt(e.target.value) })}>
                                <option value={1}>1</option>
                                <option value={2}>2</option>
                                <option value={4}>4</option>
                            </select>
                        </div>
                        <div className="input-group">
                            <label className="input-label">Default ECC Bytes</label>
                            <input type="number" className="input" min={0} max={128} value={form.ecc_bytes || 32} onChange={e => setForm({ ...form, ecc_bytes: parseInt(e.target.value) })} />
                        </div>
                        <div className="input-group">
                            <label className="input-label">Worker Threads</label>
                            <input type="number" className="input" min={1} max={32} value={form.threads || 4} onChange={e => setForm({ ...form, threads: parseInt(e.target.value) })} />
                        </div>
                        <div className="input-group">
                            <label className="input-label">FFmpeg Video Encoder</label>
                            <select className="input" value={form.encoder || 'libx264'} onChange={e => setForm({ ...form, encoder: e.target.value })}>
                                <option value="libx264">libx264 (CPU)</option>
                                <option value="h264_nvenc">h264_nvenc (NVIDIA)</option>
                                <option value="h264_qsv">h264_qsv (Intel)</option>
                                <option value="h264_amf">h264_amf (AMD)</option>
                            </select>
                        </div>
                    </div>
                </section>

                {/* Global Behaviors */}
                <section className="card">
                    <div className="p-5 border-b border-subtle flex items-center gap-3">
                        <SlidersHorizontal className="text-accent" size={20} />
                        <h2 className="font-semibold text-lg">System Behaviors</h2>
                    </div>
                    <div className="p-6 space-y-4">
                        <label className="flex items-center gap-3 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={form.auto_cleanup ?? true}
                                onChange={e => setForm({ ...form, auto_cleanup: e.target.checked })}
                                className="w-5 h-5 rounded border-subtle text-accent"
                            />
                            <div>
                                <span className="font-medium text-primary">Auto-cleanup Temp Files</span>
                                <p className="text-xs text-muted mt-0.5">Delete temporary PNG frames after video stitching/extraction.</p>
                            </div>
                        </label>

                        <div className="grid-2 gap-6 mt-4">
                            <div className="input-group">
                                <label className="input-label">Compression Level</label>
                                <select className="input" value={form.compression || 'Fast (Deflate)'} onChange={e => setForm({ ...form, compression: e.target.value })}>
                                    <option value="Store (No Compression)">Store (None)</option>
                                    <option value="Fast (Deflate)">Fast (Deflate - Default)</option>
                                    <option value="Best (LZMA)">Best (LZMA)</option>
                                    <option value="BZIP2">BZIP2</option>
                                </select>
                            </div>
                            <div className="input-group">
                                <label className="input-label">Auto Split Size</label>
                                <select className="input" value={form.split_size || 'No Split'} onChange={e => setForm({ ...form, split_size: e.target.value })}>
                                    <option value="No Split">No Split</option>
                                    <option value="100 MB">100 MB</option>
                                    <option value="500 MB">500 MB</option>
                                    <option value="1 GB">1 GB</option>
                                    <option value="10 GB">10 GB</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </section>

                <div className="flex items-center justify-between pt-4">
                    <p className="text-success text-sm font-medium">{successMsg}</p>
                    <button type="submit" className="btn btn-primary px-8" disabled={saveMut.isPending}>
                        <Save size={16} /> {saveMut.isPending ? 'Saving...' : 'Save Configuration'}
                    </button>
                </div>
            </form>
        </div>
    )
}
