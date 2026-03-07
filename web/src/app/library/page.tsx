'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { filesApi } from '@/lib/api'
import { 
  FolderOpen, FileVideo, Trash2, Search, Link2, 
  HardDrive, LayoutGrid, List, Activity, 
  Clock, ArrowUpRight, ShieldCheck, Zap
} from 'lucide-react'
import { BentoGrid, BentoItem } from '@/components/BentoGrid'
import { motion, AnimatePresence } from 'framer-motion'

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
                    <h1 className="page-title text-glow">
                        <Zap size={28} className="inline mr-3 text-accent" />
                        Dashboard
                    </h1>
                    <p className="page-subtitle">Your space-time file library.</p>
                </div>

                <div className="flex items-center gap-4">
                    <div className="relative">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                        <input
                            type="text"
                            placeholder="Search archives..."
                            className="input pl-10 w-64"
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                        />
                    </div>
                </div>
            </header>

            <BentoGrid>
                {/* Storage Overview */}
                <BentoItem colSpan={2}>
                    <div className="card-body flex items-center justify-between h-full">
                        <div>
                            <p className="text-muted text-sm font-medium flex items-center gap-2 mb-2">
                                <HardDrive size={16} /> Total Usage
                            </p>
                            <h2 className="text-4xl font-bold text-accent font-display">{bytesToSize(totalSize)}</h2>
                            <p className="text-xs text-muted mt-2">Distributed across {files.length} YouTube archives</p>
                        </div>
                        <div className="relative w-24 h-24">
                            <svg className="w-full h-full" viewBox="0 0 100 100">
                                <circle cx="50" cy="50" r="45" fill="none" stroke="var(--border-subtle)" strokeWidth="8" />
                                <motion.circle 
                                    cx="50" cy="50" r="45" fill="none" 
                                    stroke="var(--accent-primary)" strokeWidth="8" 
                                    strokeDasharray="282.7"
                                    initial={{ strokeDashoffset: 282.7 }}
                                    animate={{ strokeDashoffset: 282.7 * (1 - Math.min(files.length / 100, 1)) }}
                                    transition={{ duration: 1.5, ease: "easeOut" }}
                                    strokeLinecap="round"
                                />
                            </svg>
                            <div className="absolute inset-0 flex items-center justify-center flex-col">
                                <span className="text-lg font-bold">{files.length}%</span>
                            </div>
                        </div>
                    </div>
                </BentoItem>

                {/* Quick Stats */}
                <BentoItem>
                    <div className="card-body">
                        <p className="text-muted text-sm font-medium flex items-center gap-2 mb-4">
                            <Activity size={16} /> Status
                        </p>
                        <div className="space-y-4">
                            <div className="flex justify-between items-center">
                                <span className="text-sm text-secondary">Healthy Files</span>
                                <span className="text-sm font-bold text-success">{files.length - pending}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-sm text-secondary">Pending Links</span>
                                <span className="text-sm font-bold text-warning">{pending}</span>
                            </div>
                            <div className="pt-2 border-t border-subtle">
                                <div className="flex justify-between items-center text-xs">
                                    <span className="text-muted">Avg Block Size</span>
                                    <span className="text-primary">2.0 MB</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </BentoItem>

                {/* File List Header */}
                <div style={{ gridColumn: 'span 3', display: 'flex', alignItems: 'center', justifyContent: 'between', marginTop: '1rem' }}>
                    <h3 className="text-lg font-bold font-display">Recent Archives</h3>
                    <div style={{ marginLeft: 'auto' }} className="flex bg-surface rounded-md p-1 border border-subtle">
                        <button className={`p-1.5 rounded ${view === 'grid' ? 'bg-glass text-primary' : 'text-muted'}`} onClick={() => setView('grid')}>
                            <LayoutGrid size={16} />
                        </button>
                        <button className={`p-1.5 rounded ${view === 'list' ? 'bg-glass text-primary' : 'text-muted'}`} onClick={() => setView('list')}>
                            <List size={16} />
                        </button>
                    </div>
                </div>

                {/* Files Grid/List */}
                {isLoading ? (
                    <div style={{ gridColumn: 'span 3' }} className="py-20 text-center text-muted">Scanning sub-space...</div>
                ) : filtered.length === 0 ? (
                    <div style={{ gridColumn: 'span 3' }} className="card py-20 text-center">
                         <FolderOpen size={48} className="mx-auto text-muted mb-4 opacity-50" />
                         <p className="text-muted">No archives detected in this sector.</p>
                    </div>
                ) : (
                    <div style={{ gridColumn: 'span 3', display: 'grid', gridTemplateColumns: view === 'grid' ? 'repeat(auto-fill, minmax(280px, 1fr))' : '1fr', gap: '1rem' }}>
                         {filtered.map((f: any) => (
                             <motion.div 
                                layout
                                key={f.id} 
                                className={`card ${view === 'list' ? 'flex items-center p-4 gap-4' : 'flex-col overflow-hidden'}`}
                             >
                                 <div className={view === 'grid' ? 'p-5' : 'flex items-center gap-4 flex-1'}>
                                     <div style={{ 
                                         width: 48, height: 48, borderRadius: 12, 
                                         background: 'rgba(56, 189, 248, 0.05)',
                                         display: 'flex', alignItems: 'center', justifyContent: 'center',
                                         marginBottom: view === 'grid' ? 16 : 0
                                     }}>
                                         <FileVideo size={24} className="text-accent" />
                                     </div>
                                     <div className="flex-1 min-w-0">
                                         <h4 className="font-bold text-primary truncate" title={f.file_name}>{f.file_name}</h4>
                                         <p className="text-xs text-muted flex items-center gap-2 mt-1">
                                             <Clock size={12} /> {new Date(f.timestamp * 1000).toLocaleDateString()}
                                             <span className="text-muted opacity-50">•</span>
                                             <span>{bytesToSize(f.file_size)}</span>
                                         </p>
                                     </div>
                                 </div>

                                 <div className={`flex gap-2 ${view === 'grid' ? 'p-4 border-t border-subtle' : 'pr-4'}`}>
                                     <a
                                         href={`https://youtube.com/watch?v=${f.video_id}`}
                                         target="_blank"
                                         className="btn btn-ghost btn-sm"
                                         title="View on YouTube"
                                         {...(f.video_id === 'pending' && { 'data-disabled': true, style: { opacity: 0.5, pointerEvents: 'none' } })}
                                     >
                                         <ArrowUpRight size={14} />
                                     </a>
                                     <button
                                         className="btn btn-ghost btn-sm"
                                         style={{ color: 'var(--error)' }}
                                         onClick={() => {
                                             if (confirm(`Purge archive ${f.file_name}?`)) delMutation.mutate(f.id)
                                         }}
                                     >
                                         <Trash2 size={14} />
                                     </button>
                                 </div>
                             </motion.div>
                         ))}
                    </div>
                )}
            </BentoGrid>
        </div>
    )
}

