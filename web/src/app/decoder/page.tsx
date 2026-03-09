'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { jobsApi } from '@/lib/api'
import {
    Download, Youtube, Play, CheckCircle2,
    Search, FileVideo, HardDrive,
    ArrowRight, ShieldCheck, Zap
} from 'lucide-react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'

export default function DecoderPage() {
    const router = useRouter()

    const [inputType, setInputType] = useState<'local' | 'youtube'>('local')
    const [pathInput, setPathInput] = useState('')
    const [ytUrl, setYtUrl] = useState('')
    const [outPath, setOutPath] = useState('')
    const [useRemote, setUseRemote] = useState(false)

    const startLocalDecode = useMutation({
        mutationFn: (data: any) => jobsApi.pipelineDecodeStart(data),
        onSuccess: () => router.push('/transfers'),
        onError: (err: any) => {
            console.error('Decode failed:', err)
            const msg = err.response?.data?.error?.message || err.message || 'Check your connection.'
            alert(`Station Error: ${msg}`)
        }
    })

    const handleSubmit = (e?: React.FormEvent) => {
        e?.preventDefault()

        if (inputType === 'local') {
            if (!pathInput || !outPath) return
            startLocalDecode.mutate({
                video_path: pathInput.trim(),
                output_file: outPath.trim(),
                managed: useRemote
            })
        } else {
            alert("YouTube auto-recovery is in development. Please provide the local video path.")
        }
    }

    return (
        <div className="max-w-5xl mx-auto pb-20">
            <header className="page-header mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div>
                    <h1 className="page-title text-glow flex items-center gap-3">
                        <Download size={32} className="text-success" />
                        Decoder
                    </h1>
                    <p className="page-subtitle">Restore your data from video archives with bit-perfect accuracy.</p>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                {/* Main Card */}
                <div className="lg:col-span-8">
                    <div className="card glass-panel overflow-hidden">
                        <div className="p-1 border-b border-subtle flex">
                            <button
                                onClick={() => setInputType('local')}
                                className={`flex-1 py-4 text-sm font-bold transition-all flex items-center justify-center gap-2 ${inputType === 'local' ? 'text-primary' : 'text-muted'}`}
                            >
                                <FileVideo size={16} /> Local File
                                {inputType === 'local' && <motion.div layoutId="tab" className="absolute bottom-0 h-0.5 bg-success w-1/4" />}
                            </button>
                            <button
                                onClick={() => setInputType('youtube')}
                                className={`flex-1 py-4 text-sm font-bold transition-all flex items-center justify-center gap-2 ${inputType === 'youtube' ? 'text-primary' : 'text-muted'}`}
                            >
                                <Youtube size={16} /> YouTube URL
                                {inputType === 'youtube' && <motion.div layoutId="tab" className="absolute bottom-0 h-0.5 bg-success w-1/4" />}
                            </button>
                        </div>

                        <div className="p-10 space-y-8">
                            <AnimatePresence mode="wait">
                                {inputType === 'local' ? (
                                    <motion.div
                                        key="local"
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, y: -10 }}
                                        className="space-y-6"
                                    >
                                        <div className="input-group">
                                            <label className="input-label">Video Archive Source</label>
                                            <div className="relative group">
                                                <input
                                                    className="input pl-12 font-mono"
                                                    placeholder="C:\Downloads\archive_part_1.mp4"
                                                    value={pathInput}
                                                    onChange={e => setPathInput(e.target.value)}
                                                />
                                                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-muted group-focus-within:text-success transition-colors">
                                                    <FileVideo size={18} />
                                                </div>
                                            </div>
                                        </div>
                                    </motion.div>
                                ) : (
                                    <motion.div
                                        key="youtube"
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, y: -10 }}
                                        className="space-y-6"
                                    >
                                        <div className="input-group">
                                            <label className="input-label">Archive URL</label>
                                            <div className="relative group">
                                                <input
                                                    className="input pl-12"
                                                    placeholder="https://youtube.com/watch?v=..."
                                                    value={ytUrl}
                                                    onChange={e => setYtUrl(e.target.value)}
                                                />
                                                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-muted group-focus-within:text-success transition-colors">
                                                    <Search size={18} />
                                                </div>
                                            </div>
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>

                            <div className="input-group">
                                <label className="input-label">Restoration Target (Destination Path)</label>
                                <div className="relative group">
                                    <input
                                        className="input pl-12 font-mono"
                                        placeholder="C:\Restored\my_data.zip"
                                        value={outPath}
                                        onChange={e => setOutPath(e.target.value)}
                                    />
                                    <div className="absolute left-4 top-1/2 -translate-y-1/2 text-muted group-focus-within:text-success transition-colors">
                                        <HardDrive size={18} />
                                    </div>
                                </div>

                                {/* Remote Worker Toggle */}
                                <div className="flex items-center justify-between p-4 bg-accent/5 border border-accent/20 rounded-xl">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center text-accent">
                                            <Zap size={20} />
                                        </div>
                                        <div>
                                            <p className="text-sm font-bold text-primary">Nebula Supercompute</p>
                                            <p className="text-[10px] text-muted uppercase tracking-wider">Offload extraction to remote GPU nodes</p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => setUseRemote(!useRemote)}
                                        className={`relative w-12 h-6 rounded-full transition-colors ${useRemote ? 'bg-success' : 'bg-surface-light border border-subtle'}`}
                                    >
                                        <motion.div
                                            animate={{ x: useRemote ? 24 : 4 }}
                                            className="absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm"
                                        />
                                    </button>
                                </div>
                            </div>

                            <div className="p-6 bg-surface/50 border-t border-subtle flex items-center justify-between">
                                <div className="flex items-center gap-2 text-xs text-muted">
                                    <ShieldCheck size={14} className="text-success" />
                                    RS Reconstruction Engine v5.0
                                </div>
                                <button
                                    onClick={() => handleSubmit()}
                                    disabled={startLocalDecode.isPending || (!pathInput && !ytUrl) || !outPath}
                                    className="btn btn-primary h-12 px-10 gap-3"
                                    style={{ background: 'var(--success)', color: 'white' }}
                                >
                                    {startLocalDecode.isPending ? 'Processing...' : 'Start Extraction'}
                                    <Zap size={18} />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Info Sidebar */}
                <div className="lg:col-span-4 space-y-6">
                    <div className="card p-6">
                        <h3 className="font-bold flex items-center gap-2 mb-4">
                            <Zap size={18} className="text-success" /> Quality Assurance
                        </h3>
                        <div className="space-y-4">
                            <div className="flex gap-3">
                                <div className="w-8 h-8 rounded-lg bg-surface flex items-center justify-center shrink-0">
                                    <CheckCircle2 size={16} className="text-success" />
                                </div>
                                <p className="text-xs text-muted leading-relaxed">
                                    <span className="text-primary font-bold">SHA-256 Verification:</span> Every byte is checked against its original hash before being written to disk.
                                </p>
                            </div>
                            <div className="flex gap-3">
                                <div className="w-8 h-8 rounded-lg bg-surface flex items-center justify-center shrink-0">
                                    <CheckCircle2 size={16} className="text-success" />
                                </div>
                                <p className="text-xs text-muted leading-relaxed">
                                    <span className="text-primary font-bold">Error Correction:</span> Up to 32 bytes of parity per block allow for pixel-perfect recovery even with compression artifacts.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
