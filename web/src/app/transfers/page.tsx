'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { jobsApi, Job } from '@/lib/api'
import { Activity, XCircle, CheckCircle2, Clock, PlayCircle, Loader2, Trash2 } from 'lucide-react'

function getStatusIcon(status: string) {
    switch (status) {
        case 'done': return <CheckCircle2 size={20} className="text-emerald-500" />
        case 'running': return <Loader2 size={20} className="text-blue-500 animate-spin" />
        case 'failed': return <XCircle size={20} className="text-red-500" />
        case 'pending': return <Clock size={20} className="text-gray-400" />
        case 'cancelled': return <XCircle size={20} className="text-orange-400" />
        default: return <PlayCircle size={20} className="text-indigo-400" />
    }
}

function getBadgeClass(status: string) {
    switch (status) {
        case 'done': return 'badge-done'
        case 'running': return 'badge-running'
        case 'failed': return 'badge-failed'
        case 'pending': return 'badge-pending'
        case 'cancelled': return 'badge-cancelled'
        default: return 'badge-pending'
    }
}

function JobCard({ job }: { job: Job }) {
    const queryClient = useQueryClient()
    
    const cancelMutation = useMutation({
        mutationFn: (id: string) => jobsApi.cancel(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['jobs'] })
        },
        onError: (err: any) => {
            console.error('Cancel failed:', err)
            // fallback: refetch to see current state
            queryClient.invalidateQueries({ queryKey: ['jobs'] })
        }
    })

    const isWorking = job.status === 'running' || job.status === 'pending'

    return (
        <div className="card p-5 group hover:border-accent/40 transition-colors">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    {getStatusIcon(job.status)}
                    <div>
                        <h4 className="font-semibold text-primary capitalize flex items-center gap-2">
                            {job.kind.replace('_', ' ')} Pipeline
                            <span className={`badge ${getBadgeClass(job.status)} uppercase text-[10px]`}>
                                {job.status}
                            </span>
                        </h4>
                        <p className="text-xs text-muted font-mono mt-0.5">ID: {job.id}</p>
                    </div>
                </div>
                <div className="flex flex-col items-end gap-2">
                    <div className="text-right">
                        <p className="text-sm font-medium text-primary">{job.progress}%</p>
                        <p className="text-xs text-muted mt-0.5 truncate max-w-[150px] md:max-w-xs">{job.message}</p>
                    </div>
                    {isWorking && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation()
                                cancelMutation.mutate(job.id)
                            }}
                            disabled={cancelMutation.isPending}
                            className={`text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 transition-all ${cancelMutation.isPending ? 'text-muted' : 'text-red-400 hover:text-red-300'}`}
                        >
                            <XCircle size={12} />
                            {cancelMutation.isPending ? 'Aborting...' : 'Cancel'}
                        </button>
                    )}
                </div>
            </div>

            {/* Progress Bar */}
            <div className="progress-track mb-3 h-2 bg-surface/50 border border-subtle overflow-hidden relative">
                <div
                    className={`progress-fill absolute inset-y-0 left-0 transition-all duration-500 ${job.status === 'failed' ? 'bg-red-500' : job.status === 'done' ? 'bg-emerald-500' : 'bg-accent shadow-glow'}`}
                    style={{ width: `${job.progress}%` }}
                />
            </div>

            <div className="flex justify-between items-center text-xs text-muted">
                <span>Started: {new Date(job.created_at * 1000).toLocaleString()}</span>
                {(job.error || job.status === 'failed') && (
                    <span className="text-red-400 truncate max-w-sm ml-4 font-medium" title={job.error || ''}>
                        {job.error || 'Operation failed'}
                    </span>
                )}
            </div>
        </div>
    )
}

export default function TransfersPage() {
    const queryClient = useQueryClient()
    
    // Polling every 2s
    const { data, isLoading, isError } = useQuery({
        queryKey: ['jobs'],
        queryFn: () => jobsApi.list({ limit: 50 }),
        refetchInterval: 2000
    })
    const clearMutation = useMutation({
        mutationFn: () => jobsApi.clear(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['jobs'] })
        },
        onError: (err: any) => {
            console.error('Clear failed:', err)
            const msg = err.response?.data?.error?.message || err.message || 'Cleanup failed.'
            alert(`Station Error: ${msg}`)
        }
    })

    const jobs = data?.jobs || []
    const hasTerminalJobs = jobs.some((j: Job) => ['done', 'failed', 'cancelled'].includes(j.status))

    return (
        <div className="max-w-5xl mx-auto px-4">
            <header className="page-header mb-8 flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div>
                    <h1 className="page-title"><Activity size={28} className="inline mr-3 text-accent" />Transfers & Jobs</h1>
                    <p className="page-subtitle">Live monitoring of your cosmic data pipelines.</p>
                </div>
                {hasTerminalJobs && (
                    <button
                        onClick={() => clearMutation.mutate()}
                        disabled={clearMutation.isPending}
                        className="btn-glass px-4 py-2 text-xs font-bold uppercase tracking-widest flex items-center gap-2 hover:bg-red-500/20 hover:text-red-300 transition-all border border-red-500/30 text-red-400 disabled:opacity-50 self-start md:self-auto shrink-0"
                    >
                        {clearMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                        Clear Completed
                    </button>
                )}
            </header>

            {isError && (
                <div className="card p-4 border-red-500/20 bg-red-500/5 mb-6">
                    <div className="flex items-center gap-3 text-red-400">
                        <XCircle size={18} />
                        <p className="text-xs font-bold uppercase tracking-widest">Station Link Severed</p>
                    </div>
                </div>
            )}

            {isLoading && jobs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 opacity-50">
                    <Loader2 size={40} className="animate-spin text-accent mb-4" />
                    <p className="text-sm font-medium uppercase tracking-widest text-muted">Syncing with Station...</p>
                </div>
            ) : jobs.length === 0 ? (
                <div className="card text-center py-20 bg-glass/20 border-dashed">
                    <Activity size={48} className="mx-auto text-muted mb-4 opacity-20" />
                    <h3 className="text-lg font-semibold text-primary mb-2">No active transfers</h3>
                    <p className="text-muted text-sm">Jobs will appear here when you initiate an encode or decode cycle.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-4">
                    {jobs.map((job: any) => (
                        <JobCard key={job.id} job={job} />
                    ))}
                </div>
            )}
        </div>
    )
}
