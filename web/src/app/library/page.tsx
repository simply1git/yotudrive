'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { filesApi, api } from '@/lib/api'
import { FolderOpen, FileVideo, Trash2, Search, Link2, Download, AlertCircle, HardDrive, LayoutGrid, List } from 'lucide-react'

export default function LibraryPage() {
    const queryClient = useQueryClient()
    const [search, setSearch] = useState('')
    const [view, setView] = useState<'grid' | 'list'>('grid')

    const { data, isLoading } = useQuery({
        queryKey: ['files'],
        queryFn: () => filesApi.list(),
    })

    const delMutation = useMutation({
        mutationFn: (id: string) => filesApi.delete(id),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['files'] }),
    })

    function bytesToSize(bytes: number) {
        if (bytes === 0) return '0 B'
        const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }

    const files = data?.files || []
    const filtered = files.filter((f: any) =>
        f.file_name?.toLowerCase().includes(search.toLowerCase())
    )

    const pending = files.filter((f: any) => f.video_id === 'pending').length
    const totalSize = files.reduce((acc: number, f: any) => acc + (f.file_size || 0), 0)

    return (
        <div>
            <header className="page-header flex items-center justify-between mb-8">
                <div>
                    <h1 className="page-title"><FolderOpen size={28} className="inline mr-3 text-accent" />Library</h1>
                    <p className="page-subtitle">Manage your cloud storage archives.</p>
                </div>

                <div className="flex items-center gap-4">
                    <div className="relative">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                        <input
                            type="text"
                            placeholder="Search files..."
                            className="input pl-10 w-64"
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                        />
                    </div>
                    <div className="flex bg-surface rounded-md p-1 border border-subtle">
                        <button className={`p-1.5 rounded ${view === 'grid' ? 'bg-glass text-primary' : 'text-muted'}`} onClick={() => setView('grid')}>
                            <LayoutGrid size={18} />
                        </button>
                        <button className={`p-1.5 rounded ${view === 'list' ? 'bg-glass text-primary' : 'text-muted'}`} onClick={() => setView('list')}>
                            <List size={18} />
                        </button>
                    </div>
                </div>
            </header>

            {/* Stats row */}
            <div className="grid-4 mb-8">
                <div className="stat-card">
                    <p className="stat-label flex items-center gap-2"><HardDrive size={16} /> Total Storage</p>
                    <p className="stat-value text-accent">{bytesToSize(totalSize)}</p>
                </div>
                <div className="stat-card">
                    <p className="stat-label flex items-center gap-2"><FileVideo size={16} /> Total Archives</p>
                    <p className="stat-value">{files.length}</p>
                </div>
                <div className="stat-card">
                    <p className="stat-label flex items-center gap-2"><FolderOpen size={16} /> Pending Jobs</p>
                    <p className="stat-value">{pending}</p>
                </div>
            </div>

            {isLoading ? (
                <div className="text-center py-20 text-muted">Loading files...</div>
            ) : filtered.length === 0 ? (
                <div className="card text-center py-20">
                    <FolderOpen size={48} className="mx-auto text-muted mb-4 opacity-50" />
                    <h3 className="text-lg font-semibold text-primary mb-2">No files found</h3>
                    <p className="text-muted text-sm max-w-sm mx-auto">Your library is empty. Go to the Encoder to start turning files into YouTube videos.</p>
                </div>
            ) : (
                <div className={view === 'grid' ? 'grid-3' : 'flex flex-col gap-4'}>
                    {filtered.map((f: any) => (
                        <div key={f.id} className={`card ${view === 'list' ? 'flex items-center p-4 gap-4' : 'flex-col overflow-hidden'}`}>
                            {view === 'grid' && (
                                <div className="h-32 bg-surface/50 flex items-center justify-center border-b border-subtle relative overflow-hidden group">
                                    <FileVideo size={48} className="text-muted/50 group-hover:scale-110 transition-transform duration-500" />
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                                    <div className="absolute bottom-3 left-4 right-4 flex justify-between">
                                        <span className="text-xs font-mono bg-black/60 px-2 py-1 rounded">{bytesToSize(f.file_size)}</span>
                                    </div>
                                </div>
                            )}

                            <div className={`flex-1 ${view === 'grid' ? 'p-5' : 'flex items-center justify-between'}`}>
                                <div className={view === 'list' ? 'flex items-center gap-4 flex-1' : ''}>
                                    {view === 'list' && (
                                        <div className="w-10 h-10 rounded-lg bg-surface flex items-center justify-center">
                                            <FileVideo size={20} className="text-muted" />
                                        </div>
                                    )}
                                    <div>
                                        <h3 className="font-semibold text-primary truncate" style={{ maxWidth: view === 'grid' ? '100%' : '300px' }} title={f.file_name}>
                                            {f.file_name}
                                        </h3>
                                        <p className="text-xs text-muted mt-1 font-mono">
                                            {new Date(f.timestamp * 1000).toLocaleDateString()} • {f.video_id === 'pending' ? <span className="text-warning">Pending</span> : f.video_id}
                                        </p>
                                    </div>
                                </div>

                                <div className={`flex gap-2 ${view === 'grid' ? 'mt-6 pt-4 border-t border-subtle' : ''}`}>
                                    <a
                                        href={`https://youtube.com/watch?v=${f.video_id}`}
                                        target="_blank"
                                        className="btn btn-ghost btn-sm flex-1 justify-center"
                                        {...(f.video_id === 'pending' && { 'data-disabled': true, style: { opacity: 0.5, pointerEvents: 'none' } })}
                                    >
                                        <Link2 size={14} /> View
                                    </a>
                                    <button
                                        className="btn btn-danger btn-sm"
                                        onClick={() => {
                                            if (confirm(`Delete ${f.file_name}?`)) delMutation.mutate(f.id)
                                        }}
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
