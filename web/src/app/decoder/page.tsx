'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { jobsApi } from '@/lib/api'
import { Download, Youtube, Play, CheckCircle2 } from 'lucide-react'
import { useRouter } from 'next/navigation'

export default function DecoderPage() {
    const router = useRouter()

    const [inputType, setInputType] = useState<'local' | 'youtube'>('local')
    const [pathInput, setPathInput] = useState('')
    const [ytUrl, setYtUrl] = useState('')
    const [outPath, setOutPath] = useState('')

    const startLocalDecode = useMutation({
        mutationFn: (data: any) => jobsApi.pipelineDecodeStart(data),
        onSuccess: () => router.push('/transfers')
    })

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()

        if (inputType === 'local') {
            if (!pathInput || !outPath) return alert("Required fields missing")
            startLocalDecode.mutate({
                video_path: pathInput.trim(),
                output_file: outPath.trim()
            })
        } else {
            alert("YouTube auto-download trigger not fully hooked up in UI yet. Please use local file.")
        }
    }

    return (
        <div className="max-w-4xl mx-auto">
            <header className="page-header mb-8 text-center pt-8">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 border border-emerald-500/30 flex items-center justify-center mx-auto mb-6">
                    <Download size={32} className="text-emerald-400" />
                </div>
                <h1 className="page-title text-4xl mb-4">Extract Payload</h1>
                <p className="page-subtitle text-lg max-w-2xl mx-auto">
                    Recover your original files from a YotuDrive video archive. Built-in CRC checks and RS error recovery ensure bit-perfect restoration.
                </p>
            </header>

            <form onSubmit={handleSubmit} className="card overflow-hidden">
                <div className="p-8 border-b border-subtle">

                    <div className="flex bg-surface rounded-lg p-1 border border-subtle w-fit mb-8 mx-auto">
                        <button
                            type="button"
                            className={`px-6 py-2.5 rounded-md text-sm font-medium transition-all ${inputType === 'local' ? 'bg-glass text-primary shadow-sm' : 'text-muted hover:text-primary'}`}
                            onClick={() => setInputType('local')}
                        >
                            Local Video File
                        </button>
                        <button
                            type="button"
                            className={`px-6 py-2.5 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${inputType === 'youtube' ? 'bg-glass text-primary shadow-sm' : 'text-muted hover:text-primary'}`}
                            onClick={() => setInputType('youtube')}
                        >
                            <Youtube size={16} /> YouTube URL
                        </button>
                    </div>

                    <div className="space-y-6 max-w-2xl mx-auto">
                        {inputType === 'local' ? (
                            <div className="input-group">
                                <label className="input-label text-center">Video Archive Path</label>
                                <input
                                    className="input text-center text-lg py-3 font-mono"
                                    placeholder="C:\Downloads\archive.mp4"
                                    value={pathInput}
                                    onChange={e => setPathInput(e.target.value)}
                                    required={inputType === 'local'}
                                />
                            </div>
                        ) : (
                            <div className="input-group">
                                <label className="input-label text-center">YouTube Video URL</label>
                                <input
                                    className="input text-center text-lg py-3"
                                    placeholder="https://youtube.com/watch?v=..."
                                    value={ytUrl}
                                    onChange={e => setYtUrl(e.target.value)}
                                    required={inputType === 'youtube'}
                                />
                            </div>
                        )}

                        <div className="h-px bg-border-subtle my-8 w-1/2 mx-auto" />

                        <div className="input-group">
                            <label className="input-label text-center">Output File Dump Location</label>
                            <input
                                className="input text-center text-lg py-3 font-mono"
                                placeholder="C:\Downloads\restored.zip"
                                value={outPath}
                                onChange={e => setOutPath(e.target.value)}
                                required
                            />
                            <p className="text-center text-xs text-muted mt-2">
                                If the archive name is preserved, the engine will automatically rename it if possible.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="p-6 bg-surface/50 flex flex-col sm:flex-row gap-4 justify-between items-center text-center sm:text-left">
                    <p className="text-sm text-muted flex items-center gap-2">
                        <CheckCircle2 size={16} className="text-success" /> Multi-core frame extraction enabled.
                    </p>
                    <button
                        type="submit"
                        className="btn btn-primary px-10 py-3 text-base"
                        style={{ background: 'linear-gradient(135deg, #10b981, #059669)', boxShadow: '0 4px 15px rgba(16, 185, 129, 0.3)' }}
                        disabled={startLocalDecode.isPending || (!pathInput && !ytUrl) || !outPath}
                    >
                        {startLocalDecode.isPending ? 'Initiating...' : 'Extract Pipeline'} <Play size={18} />
                    </button>
                </div>
            </form>
        </div>
    )
}
