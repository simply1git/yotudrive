'use client'
import { useState, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { jobsApi } from '@/lib/api'
import { Upload, File, Play, Settings2, CheckCircle2 } from 'lucide-react'
import { useRouter } from 'next/navigation'

export default function EncoderPage() {
    const router = useRouter()
    const fileRef = useRef<HTMLInputElement>(null)

    const [file, setFile] = useState<File | null>(null)
    const [useOauth, setUseOauth] = useState(false)
    const [advanced, setAdvanced] = useState(false)

    const [overrides, setOverrides] = useState({
        block_size: 2,
        ecc_bytes: 32,
        threads: 4,
        encoder: 'libx264'
    })

    // Since we are wrapping a python backend that expects a local path for the encoder (not a multipart upload),
    // in a real Electron desktop app the UI would just pass the absolute filepath.
    // For the web interface, we assume the backend has local filesystem access or expects an absolute path.
    // We'll provide a local file path input as a fallback to actual file selection.
    const [pathInput, setPathInput] = useState('')

    const startJob = useMutation({
        mutationFn: (data: any) => jobsApi.pipelineEncodeStart(data),
        onSuccess: () => {
            router.push('/transfers')
        }
    })

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (!pathInput) return alert("Please specify the absolute path to the input file to encode.")

        // Auto-generate output next to input
        const outVideo = pathInput + '.encoded.mp4'

        startJob.mutate({
            input_file: pathInput.trim(),
            output_video: outVideo,
            register_in_db: true,
            overrides: advanced ? overrides : undefined
        })
    }

    return (
        <div className="max-w-4xl mx-auto">
            <header className="page-header mb-8 text-center pt-8">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center mx-auto mb-6">
                    <Upload size={32} className="text-accent" />
                </div>
                <h1 className="page-title text-4xl mb-4">New Archive Payload</h1>
                <p className="page-subtitle text-lg max-w-2xl mx-auto">
                    Convert any file into a resilient, YouTube-compatible video stream using Reed-Solomon error correction.
                </p>
            </header>

            <form onSubmit={handleSubmit} className="card overflow-hidden">
                <div className="p-8 border-b border-subtle">
                    <div className="mb-6">
                        <label className="input-label mb-2">Input File Path (Absolute path on the server/local machine)</label>
                        <input
                            className="input text-lg py-3 font-mono"
                            placeholder="C:\Downloads\my_backup.zip"
                            value={pathInput}
                            onChange={e => setPathInput(e.target.value)}
                            required
                        />
                        <p className="text-xs text-muted mt-2">
                            Note: The web client accesses local backend storage. For pure web uploads, a chunking uploader endpoint would be required.
                        </p>
                    </div>

                    <div className="flex bg-surface rounded-lg p-1 border border-subtle w-fit mb-8">
                        <button
                            type="button"
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${!advanced ? 'bg-glass text-primary shadow-sm' : 'text-muted hover:text-primary'}`}
                            onClick={() => setAdvanced(false)}
                        >
                            Standard Preset
                        </button>
                        <button
                            type="button"
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${advanced ? 'bg-glass text-primary shadow-sm' : 'text-muted hover:text-primary'}`}
                            onClick={() => setAdvanced(true)}
                        >
                            Advanced Config
                        </button>
                    </div>

                    {advanced && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            className="grid-2 bg-surface/50 p-6 rounded-xl border border-subtle mb-8"
                        >
                            <div className="input-group">
                                <label className="input-label">Block Size</label>
                                <select
                                    className="input cursor-pointer"
                                    value={overrides.block_size}
                                    onChange={e => setOverrides({ ...overrides, block_size: parseInt(e.target.value) })}
                                >
                                    <option value={1}>1px (Highest Density)</option>
                                    <option value={2}>2px (Standard Web)</option>
                                    <option value={4}>4px (Highest Resilience)</option>
                                </select>
                            </div>
                            <div className="input-group">
                                <label className="input-label">ECC Bytes (Redundancy)</label>
                                <input
                                    type="number" className="input" min={0} max={128}
                                    value={overrides.ecc_bytes}
                                    onChange={e => setOverrides({ ...overrides, ecc_bytes: parseInt(e.target.value) })}
                                />
                            </div>
                            <div className="input-group">
                                <label className="input-label">Worker Threads</label>
                                <input
                                    type="number" className="input" min={1} max={32}
                                    value={overrides.threads}
                                    onChange={e => setOverrides({ ...overrides, threads: parseInt(e.target.value) })}
                                />
                            </div>
                            <div className="input-group">
                                <label className="input-label">FFmpeg Video Encoder</label>
                                <select
                                    className="input cursor-pointer"
                                    value={overrides.encoder}
                                    onChange={e => setOverrides({ ...overrides, encoder: e.target.value })}
                                >
                                    <option value="libx264">libx264 (CPU - Default)</option>
                                    <option value="h264_nvenc">h264_nvenc (NVIDIA)</option>
                                    <option value="h264_qsv">h264_qsv (Intel)</option>
                                    <option value="h264_amf">h264_amf (AMD)</option>
                                </select>
                            </div>
                        </motion.div>
                    )}

                    <label className="flex items-center gap-3 p-4 border border-subtle rounded-xl cursor-pointer hover:border-accent/50 transition-colors bg-surface/30">
                        <input
                            type="checkbox"
                            checked={useOauth}
                            onChange={e => setUseOauth(e.target.checked)}
                            className="w-5 h-5 rounded border-subtle text-accent focus:ring-accent"
                            disabled
                        />
                        <div>
                            <p className="font-medium text-primary flex items-center gap-2">
                                Auto-upload to YouTube via OAuth <span className="px-2 py-0.5 rounded-full bg-indigo-500/20 text-accent text-[10px] uppercase font-bold tracking-wider">Coming Soon</span>
                            </p>
                            <p className="text-sm text-muted mt-0.5">Automatically stream the encoded payload to your channel as an unlisted video.</p>
                        </div>
                    </label>
                </div>

                <div className="p-6 bg-surface/50 flex justify-between items-center">
                    <p className="text-sm text-muted flex items-center gap-2">
                        <CheckCircle2 size={16} className="text-success" /> End-to-end payload checksums enforced.
                    </p>
                    <button
                        type="submit"
                        className="btn btn-primary px-8 py-3 text-base"
                        disabled={startJob.isPending || !pathInput}
                    >
                        {startJob.isPending ? 'Starting Engine...' : 'Commence Encoding'} <Play size={18} />
                    </button>
                </div>
            </form>
        </div>
    )
}
