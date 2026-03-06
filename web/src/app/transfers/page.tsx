'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { jobsApi } from '@/lib/api'
import { Activity, XCircle, CheckCircle2, Clock, PlayCircle, Loader2 } from 'lucide-react'

export default function TransfersPage() {
    const queryClient = useQueryClient()

    // Polling every 2s to show live progress
    const { data } = useQuery({
        queryKey: ['jobs'],
        queryFn: () => jobsApi.list({ limit: 50 }),
        refetchInterval: 2000
    })

    // We could implement job cancellation on backend, but for UI sake let's just delete the job
    const delMutation = useMutation({
        mutationFn: (id: string) => jobsApi.get(id), // Pseudo cancel by deleting (if admin/owns)
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] })
    })

    const jobs = data?.jobs || []

    function getStatusIcon(status: string) {
        switch (status) {
            case 'done': return <CheckCircle2 size={20} className="text-emerald-500" />
            case 'running': return <Loader2 size={20} className="text-blue-500 animate-spin" />
            case 'failed': return <XCircle size={20} className="text-red-500" />
            case 'pending': return <Clock size={20} className="text-gray-400" />
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

    return (
        <div>
            <header className="page-header mb-8">
                <h1 className="page-title"><Activity size={28} className="inline mr-3 text-accent" />Transfers & Jobs</h1>
                <p className="page-subtitle">Live status of encoding, decoding, and upload pipelines.</p>
            </header>

            {jobs.length === 0 ? (
                <div className="card text-center py-20">
                    <Activity size={48} className="mx-auto text-muted mb-4 opacity-30" />
                    <h3 className="text-lg font-semibold text-primary mb-2">No active transfers</h3>
                    <p className="text-muted text-sm">Jobs will appear here when you encode or decode files.</p>
                </div>
            ) : (
                <div className="flex flex-col gap-4">
                    {jobs.map((job: any) => (
                        <div key={job.id} className="card p-5">
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
                                <div className="text-right">
                                    <p className="text-sm font-medium text-primary">{job.progress}%</p>
                                    <p className="text-xs text-muted mt-0.5">{job.message}</p>
                                </div>
                            </div>

                            {/* Progress Bar */}
                            <div className="progress-track mb-3 h-2 bg-surface/50 border border-subtle">
                                <div
                                    className={`progress-fill ${job.status === 'failed' ? 'error' : job.status === 'done' ? 'success' : ''}`}
                                    style={{ width: `${job.progress}%` }}
                                />
                            </div>

                            <div className="flex justify-between items-center text-xs text-muted">
                                <span>Started: {new Date(job.created_at * 1000).toLocaleString()}</span>
                                {job.error && <span className="text-error truncate max-w-sm ml-4" title={job.error}>Error: {job.error}</span>}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
