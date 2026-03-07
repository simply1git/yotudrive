'use client'
import { useState, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { jobsApi, storageApi } from '@/lib/api'
import { 
  Upload, File, Box, Zap, ArrowRight,
  Monitor, Cpu, Layers, MousePointer2, ShieldCheck,
  Settings2
} from 'lucide-react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'

export default function EncoderPage() {
    const router = useRouter()
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const [pathInput, setPathInput] = useState('')
    const [mode, setMode] = useState<'standard' | 'advanced' | 'nebula'>('standard')
    const [isDragging, setIsDragging] = useState(false)
    const [overrides, setOverrides] = useState({
        block_size: 2,
        ecc_bytes: 32,
        threads: 4,
        encoder: 'libx264'
    })
    
    const fileInputRef = useRef<HTMLInputElement>(null)

    const uploadFile = useMutation({
        mutationFn: (file: File) => storageApi.upload(file),
    })

    const startJob = useMutation({
        mutationFn: (data: any) => jobsApi.pipelineEncodeStart(data),
        onSuccess: () => {
            router.push('/transfers')
        },
        onError: (err: any) => {
            console.error('Start job error:', err)
            const msg = err.response?.data?.error?.message || 'Failed to initiate job. Check your connection.'
            alert(`Station Error: ${msg}`)
        }
    })

    const handleSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault()
        if (!selectedFile && !pathInput) return
        
        let serverPath = pathInput.trim()
        
        if (selectedFile) {
            try {
                const uploadRes = await uploadFile.mutateAsync(selectedFile)
                serverPath = uploadRes.path
            } catch (err) {
                console.error('Upload error:', err)
                alert('Upload failed. Please try again.')
                return
            }
        }

        const outVideo = serverPath + '.encoded.mp4'
        startJob.mutate({
            input_file: serverPath,
            output_video: outVideo,
            register_in_db: true,
            managed: mode === 'nebula',
            overrides: mode === 'advanced' ? overrides : undefined
        })
    }

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(true)
    }

    const handleDragLeave = () => {
        setIsDragging(false)
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) {
            setSelectedFile(file)
            setPathInput(file.name)
        }
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) {
            setSelectedFile(file)
            setPathInput(file.name)
        }
    }

    return (
        <div className="max-w-5xl mx-auto pb-20">
            <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden" 
                onChange={handleFileSelect}
            />
            <header className="page-header mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div>
                    <h1 className="page-title text-glow flex items-center gap-3">
                        <Upload size={32} className="text-accent" />
                        Encoder
                    </h1>
                    <p className="page-subtitle">Transform data into high-resilience YouTube streams.</p>
                </div>
                
                <div className="flex bg-surface rounded-xl p-1 border border-subtle overflow-hidden self-start md:self-auto">
                    <button 
                        onClick={() => setMode('standard')}
                        className={`px-4 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${mode === 'standard' ? 'bg-glass text-primary shadow-glow' : 'text-muted hover:text-primary'}`}
                    >
                        Standard
                    </button>
                    <button 
                        onClick={() => setMode('advanced')}
                        className={`px-4 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${mode === 'advanced' ? 'bg-glass text-primary shadow-glow' : 'text-muted hover:text-primary'}`}
                    >
                        Advanced
                    </button>
                    <button 
                        onClick={() => setMode('nebula')}
                        className={`px-4 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${mode === 'nebula' ? 'bg-accent text-bg-surface-solid shadow-glow' : 'text-muted hover:text-accent'}`}
                    >
                        Nebula (GPU)
                    </button>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Main Drop Zone */}
                <div className="lg:col-span-2 space-y-6">
                    <motion.div
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                        animate={{ 
                            borderColor: isDragging ? 'var(--accent-primary)' : 'var(--border-subtle)',
                            backgroundColor: isDragging ? 'var(--bg-glass-hover)' : 'var(--bg-glass)',
                            scale: isDragging ? 1.01 : 1
                        }}
                        className="drop-zone relative overflow-hidden group cursor-pointer"
                        style={{ minHeight: '340px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}
                    >
                        <div className="absolute top-4 right-4 text-xs font-mono text-muted uppercase tracking-widest opacity-30">
                            V5 Codec Engine
                        </div>
                        
                        <div className={`transition-all duration-500 ${isDragging || selectedFile ? 'scale-110' : 'scale-100'}`}>
                            <div className="w-20 h-20 rounded-3xl bg-accent-glow flex items-center justify-center mb-6 relative">
                                {selectedFile ? <File size={40} className="text-accent relative z-10" /> : <Box size={40} className="text-accent relative z-10" />}
                                <motion.div 
                                    animate={{ rotate: 360 }}
                                    transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
                                    className="absolute inset-0 border-2 border-dashed border-accent/30 rounded-3xl"
                                />
                            </div>
                        </div>

                        <h3 className="text-xl font-bold font-display mb-2">
                            {selectedFile ? selectedFile.name : 'Drop payload here'}
                        </h3>
                        <p className="text-muted text-sm max-w-xs mx-auto mb-8">
                            {selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB ready` : 'Drag any file or click to browse for the Reed-Solomon process.'}
                        </p>

                        <div className="w-full max-w-md px-8" onClick={e => e.stopPropagation()}>
                            <div className="relative group/input">
                                <input
                                    className="input pr-12 text-center font-mono text-sm"
                                    placeholder="Or manually enter server path..."
                                    value={pathInput}
                                    onChange={e => {
                                        setPathInput(e.target.value)
                                        setSelectedFile(null)
                                    }}
                                />
                                <div className="absolute right-4 top-1/2 -translate-y-1/2 text-muted group-focus-within/input:text-accent transition-colors">
                                    <MousePointer2 size={16} />
                                </div>
                            </div>
                        </div>

                        {isDragging && (
                            <motion.div 
                                initial={{ opacity: 0 }} 
                                animate={{ opacity: 1 }}
                                className="absolute inset-0 bg-accent/5 backdrop-blur-[2px] pointer-events-none flex items-center justify-center border-2 border-accent border-dashed m-2 rounded-[inherit]"
                            >
                                <div className="bg-bg-surface-solid px-6 py-3 rounded-2xl border border-accent shadow-glow flex items-center gap-3">
                                    <Upload size={20} className="text-accent" />
                                    <span className="font-bold text-accent">Ready to process</span>
                                </div>
                            </motion.div>
                        )}
                    </motion.div>

                    <div className="card glass-panel p-6 flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center text-success">
                                <ShieldCheck size={20} />
                            </div>
                            <div>
                                <h4 className="font-bold text-sm">Integrity Guaranteed</h4>
                                <p className="text-xs text-muted">Checksums are verified pre and post-encode.</p>
                            </div>
                        </div>
                        <button
                            onClick={() => handleSubmit()}
                            disabled={(!pathInput && !selectedFile) || uploadFile.isPending || startJob.isPending}
                            className="btn btn-primary h-12 px-10 group"
                        >
                            {uploadFile.isPending ? 'Uploading...' : startJob.isPending ? 'Processing...' : 'Commence'}
                            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                        </button>
                    </div>
                </div>

                {/* Sidebar Config / Info */}
                <div className="space-y-6">
                    <AnimatePresence mode="wait">
                        {mode === 'advanced' ? (
                            <motion.div
                                key="advanced"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 20 }}
                                className="card h-full p-6 space-y-6"
                            >
                                <h3 className="font-bold font-display flex items-center gap-2">
                                    <Settings2 size={18} className="text-accent" /> Configuration
                                </h3>
                                
                                <div className="space-y-4">
                                    <div className="input-group">
                                        <label className="input-label flex items-center gap-2">
                                            <Layers size={14} /> Density (Block Size)
                                        </label>
                                        <select
                                            className="input"
                                            value={overrides.block_size}
                                            onChange={e => setOverrides({...overrides, block_size: parseInt(e.target.value)})}
                                        >
                                            <option value={1}>1px - Ultra (Slow)</option>
                                            <option value={2}>2px - Standard</option>
                                            <option value={4}>4px - Resilient</option>
                                        </select>
                                    </div>

                                    <div className="input-group">
                                        <label className="input-label flex items-center gap-2">
                                            <ShieldCheck size={14} /> RS Parity (Bytes)
                                        </label>
                                        <input
                                            type="number" className="input" min={2} max={128}
                                            value={overrides.ecc_bytes}
                                            onChange={e => setOverrides({...overrides, ecc_bytes: parseInt(e.target.value)})}
                                        />
                                    </div>

                                    <div className="input-group">
                                        <label className="input-label flex items-center gap-2">
                                            <Cpu size={14} /> Parallel Workers
                                        </label>
                                        <input
                                            type="number" className="input" min={1} max={32}
                                            value={overrides.threads}
                                            onChange={e => setOverrides({...overrides, threads: parseInt(e.target.value)})}
                                        />
                                    </div>

                                    <div className="input-group">
                                        <label className="input-label flex items-center gap-2">
                                            <Monitor size={14} /> Video Codec
                                        </label>
                                        <select
                                            className="input"
                                            value={overrides.encoder}
                                            onChange={e => setOverrides({...overrides, encoder: e.target.value})}
                                        >
                                            <option value="libx264">Software (x264)</option>
                                            <option value="h264_nvenc">Hardware (NVIDIA)</option>
                                            <option value="h264_qsv">Hardware (Intel)</option>
                                        </select>
                                    </div>
                                </div>
                            </motion.div>
                        ) : mode === 'nebula' ? (
                            <motion.div
                                key="nebula"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 20 }}
                                className="card h-full p-6 space-y-4 border-accent/40 bg-accent/5"
                            >
                                <div className="w-12 h-12 rounded-2xl bg-accent/20 flex items-center justify-center text-accent mb-2">
                                    <Zap size={24} />
                                </div>
                                <h3 className="font-bold font-display text-accent">Nebula Mode</h3>
                                <p className="text-xs text-muted leading-relaxed">
                                    Offload the heavy encoding to a remote **GPU Worker** (Google Colab / Kaggle).
                                </p>
                                <div className="p-3 rounded-lg bg-surface/50 border border-subtle space-y-2">
                                    <p className="text-[10px] font-bold text-accent uppercase tracking-widest">How to use:</p>
                                    <ol className="text-[10px] text-muted list-decimal list-inside space-y-1">
                                        <li>Start the job here</li>
                                        <li>Open your Nebula Worker script</li>
                                        <li>Worker claims job & encodes on GPU</li>
                                    </ol>
                                </div>
                                <p className="text-[10px] text-muted italic">
                                    Ideal for files over 1GB or 18GB archives.
                                </p>
                            </motion.div>
                        ) : (
                            <motion.div
                                key="standard"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 20 }}
                                className="card h-full p-6"
                            >
                                <div className="text-center py-10">
                                    <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-4">
                                        <Zap size={24} className="text-accent" />
                                    </div>
                                    <h4 className="font-bold mb-2">Turbo Mode</h4>
                                    <p className="text-xs text-muted leading-relaxed">
                                        Using optimized defaults: 2px blocks, 32-byte parity, and multi-threaded CPU encoding.
                                    </p>
                                    <button 
                                        onClick={() => setMode('advanced')}
                                        className="mt-8 text-xs font-bold text-accent hover:underline uppercase tracking-widest"
                                    >
                                        Customize parameters
                                    </button>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    )
}
