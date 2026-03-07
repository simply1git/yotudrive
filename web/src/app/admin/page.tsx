'use client'
import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/lib/api'
import { 
  ShieldAlert, Users, Activity, LogOut, Check, X, Shield, Plus,
  Terminal, BarChart3, Settings2, Trash2, Search, Filter,
  RefreshCw, ChevronRight, AlertTriangle
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

export default function AdminPage() {
    const queryClient = useQueryClient()
    const [activeTab, setActiveTab] = useState<'metrics' | 'users' | 'logs'>('metrics')
    
    // Data Fetching
    const { data: usersData, isLoading: usersLoading } = useQuery({ 
      queryKey: ['admin_users'], 
      queryFn: () => adminApi.users.list() 
    })
    const { data: metricsData } = useQuery({ 
      queryKey: ['admin_metrics'], 
      queryFn: () => adminApi.metrics() 
    })
    const { data: logsData, refetch: refetchLogs, isLoading: isLogsLoading } = useQuery({ 
      queryKey: ['admin_logs'], 
      queryFn: () => adminApi.system.logs(),
      refetchInterval: 5000 // Auto refresh logs every 5s
    })

    const [newEmail, setNewEmail] = useState('')
    const [newRole, setNewRole] = useState('member')

    const addUserMut = useMutation({
        mutationFn: (data: any) => adminApi.users.add(data.email, data.role),
        onSuccess: () => {
            setNewEmail('')
            queryClient.invalidateQueries({ queryKey: ['admin_users'] })
            queryClient.invalidateQueries({ queryKey: ['admin_metrics'] })
        }
    })

    const toggleUserMut = useMutation({
        mutationFn: (data: { email: string, enabled: boolean }) => adminApi.users.patch(data.email, data.enabled),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin_users'] })
    })

    const revokeAllMut = useMutation({
        mutationFn: (email: string) => adminApi.sessions.revokeAll(email),
        onSuccess: () => alert('Sessions invalidated.')
    })

    if (!usersLoading && !usersData) {
        return (
            <div className="card glass-panel text-center py-20 max-w-lg mx-auto mt-20 border-error/20">
                <ShieldAlert size={48} className="mx-auto text-error mb-4 animate-pulse" />
                <h3 className="text-xl font-bold font-display uppercase tracking-widest text-error">Access Restricted</h3>
                <p className="text-muted mt-2 text-sm">Elevated privileges required for the Command Center.</p>
            </div>
        )
    }

    const users = usersData?.users || []
    const metrics = metricsData || { users: {}, jobs: { by_status: {} }, files: {} }
    const logs = logsData?.logs || []

    return (
        <div className="max-w-6xl mx-auto pb-20">
            <header className="page-header mb-12 flex justify-between items-end">
                <div>
                    <h1 className="page-title text-glow flex items-center gap-3">
                        <Shield size={32} className="text-accent" />
                        Command Center
                    </h1>
                    <p className="page-subtitle">Mission control for user permissions, system health, and logs.</p>
                </div>
                
                <div className="flex bg-surface/30 backdrop-blur-xl border border-subtle rounded-2xl p-1 gap-1">
                    <button 
                      onClick={() => setActiveTab('metrics')}
                      className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${activeTab === 'metrics' ? 'bg-accent text-white shadow-glow' : 'text-muted hover:text-primary'}`}
                    >
                      <BarChart3 size={14} /> Analytics
                    </button>
                    <button 
                      onClick={() => setActiveTab('users')}
                      className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${activeTab === 'users' ? 'bg-accent text-white shadow-glow' : 'text-muted hover:text-primary'}`}
                    >
                      <Users size={14} /> Directory
                    </button>
                    <button 
                      onClick={() => setActiveTab('logs')}
                      className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${activeTab === 'logs' ? 'bg-accent text-white shadow-glow' : 'text-muted hover:text-primary'}`}
                    >
                      <Terminal size={14} /> System Logs
                    </button>
                </div>
            </header>

            <AnimatePresence mode="wait">
                {activeTab === 'metrics' && (
                    <motion.div
                        key="metrics"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                    >
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
                            <div className="card-bento p-6">
                                <div className="flex justify-between items-center mb-4">
                                    <Users size={20} className="text-accent" />
                                    <span className="text-[10px] font-bold text-muted uppercase tracking-tighter">Capacity</span>
                                </div>
                                <p className="text-3xl font-display font-black">{metrics.users.active} / {metrics.users.cap}</p>
                                <p className="text-xs text-muted mt-2">Provisioned accounts</p>
                            </div>
                            <div className="card-bento p-6">
                                <Activity size={20} className="text-accent-secondary mb-4" />
                                <p className="text-3xl font-display font-black text-glow">{metrics.jobs.total || 0}</p>
                                <p className="text-xs text-muted mt-2">Transmissions executed</p>
                            </div>
                            <div className="card-bento p-6">
                                <Check size={20} className="text-success mb-4" />
                                <p className="text-3xl font-display font-black">
                                    {metrics.jobs.total ? Math.round(((metrics.jobs.by_status.done || 0) / metrics.jobs.total) * 100) : 100}%
                                </p>
                                <p className="text-xs text-muted mt-2">Success rate accuracy</p>
                            </div>
                            <div className="card-bento p-6">
                                <AlertTriangle size={20} className="text-warning mb-4" />
                                <p className="text-3xl font-display font-black text-warning">{(metrics.jobs.by_status.failed || 0)}</p>
                                <p className="text-xs text-muted mt-2">System exceptions</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                          <div className="lg:col-span-8 overflow-hidden rounded-3xl border border-subtle bg-surface/30">
                            <div className="p-6 border-b border-subtle flex justify-between items-center">
                              <h3 className="font-bold flex items-center gap-2"><RefreshCw size={16} className="text-accent" /> Recent Events</h3>
                              <button onClick={() => refetchLogs()} className="text-[10px] uppercase font-bold text-accent hover:underline">Refresh Stream</button>
                            </div>
                            <div className="h-[400px] overflow-y-auto p-4 font-mono text-[11px] bg-black/40 backdrop-blur-sm">
                              {logs.length > 0 ? (
                                logs.map((log: string, idx: number) => (
                                  <div key={idx} className="flex gap-4 py-1 border-b border-white/5 last:border-0">
                                    <span className="text-muted shrink-0">{(idx + 1).toString().padStart(3, '0')}</span>
                                    <span className={log.includes('ERROR') ? 'text-error' : log.includes('INFO') ? 'text-primary' : 'text-muted'}>
                                      {log}
                                    </span>
                                  </div>
                                ))
                              ) : (
                                <div className="h-full flex items-center justify-center text-muted italic">
                                  Waiting for system broadcast...
                                </div>
                              )}
                            </div>
                          </div>
                          
                          <div className="lg:col-span-4 space-y-6">
                            <div className="card p-6 bg-accent/5 border-accent/20">
                                <h3 className="font-bold mb-4 flex items-center gap-2"><Plus size={16} className="text-accent" /> Provision Hub</h3>
                                <div className="space-y-4">
                                    <div className="input-group">
                                        <input
                                            type="email" required className="input bg-surface/50" placeholder="Agent Email"
                                            value={newEmail} onChange={e => setNewEmail(e.target.value)}
                                        />
                                    </div>
                                    <div className="input-group">
                                        <select className="input bg-surface/50" value={newRole} onChange={e => setNewRole(e.target.value)}>
                                            <option value="member">Field Agent (Member)</option>
                                            <option value="admin">Director (Admin)</option>
                                        </select>
                                    </div>
                                    <button 
                                      onClick={() => addUserMut.mutate({ email: newEmail, role: newRole })}
                                      disabled={addUserMut.isPending || !newEmail}
                                      className="btn btn-primary w-full py-3 shadow-glow"
                                    >
                                        Enroll Account
                                    </button>
                                </div>
                            </div>
                          </div>
                        </div>
                    </motion.div>
                )}

                {activeTab === 'users' && (
                    <motion.div
                        key="users"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="card glass-panel overflow-hidden"
                    >
                        <div className="p-6 border-b border-subtle flex justify-between items-center">
                            <div className="relative w-72">
                                <input className="input pl-10 h-10 text-xs" placeholder="Search operational accounts..." />
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={14} />
                            </div>
                            <div className="flex gap-3">
                                <div className="badge border-accent/20 text-accent font-bold px-4">{users.length} Enrolled</div>
                            </div>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead className="bg-surface/50 border-b border-subtle text-[10px] uppercase font-bold tracking-widest text-muted">
                                    <tr>
                                        <th className="px-8 py-4">Identity</th>
                                        <th className="px-6 py-4">Authorization</th>
                                        <th className="px-6 py-4">Operational Status</th>
                                        <th className="px-8 py-4 text-right">Overrides</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-subtle">
                                    {users.map((u: any) => (
                                        <tr key={u.email} className="hover:bg-accent/5 transition-colors group">
                                            <td className="px-8 py-5">
                                                <div className="font-bold text-primary">{u.email}</div>
                                                <div className="text-[10px] text-muted">Created: {new Date(u.created_at * 1000).toLocaleDateString()}</div>
                                            </td>
                                            <td className="px-6 py-5">
                                                <span className={`inline-flex items-center px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest ${u.role === 'admin' ? 'bg-accent/20 text-accent border border-accent/30' : 'bg-surface/50 text-muted border border-subtle'}`}>
                                                    {u.role}
                                                </span>
                                            </td>
                                            <td className="px-6 py-5">
                                                {u.enabled ? (
                                                    <span className="flex items-center gap-2 text-success text-[10px] font-bold uppercase tracking-widest">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-success shadow-[0_0_8px_var(--success)]" /> Active
                                                    </span>
                                                ) : (
                                                    <span className="flex items-center gap-2 text-error text-[10px] font-bold uppercase tracking-widest">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-error" /> Decommissioned
                                                    </span>
                                                )}
                                            </td>
                                            <td className="px-8 py-5 text-right">
                                                <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <button
                                                        className={`px-4 py-1.5 rounded-xl text-[10px] font-bold uppercase transition-all ${u.enabled ? 'bg-error/10 text-error border border-error/20 hover:bg-error/20' : 'bg-success/10 text-success border border-success/20 hover:bg-success/20'}`}
                                                        onClick={() => toggleUserMut.mutate({ email: u.email, enabled: !u.enabled })}
                                                        disabled={toggleUserMut.isPending}
                                                    >
                                                        {u.enabled ? 'Disable' : 'Restore'}
                                                    </button>
                                                    <button
                                                        title="Emergency Session Invalidation"
                                                        className="p-2 rounded-xl bg-surface hover:bg-warning/10 text-muted hover:text-warning transition-colors"
                                                        onClick={() => {
                                                            if (confirm(`Revoke all sessions for ${u.email}?`)) revokeAllMut.mutate(u.email)
                                                        }}
                                                    >
                                                        <LogOut size={14} />
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </motion.div>
                )}

                {activeTab === 'logs' && (
                    <motion.div
                        key="logs"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="card glass-panel overflow-hidden"
                    >
                        <div className="p-6 border-b border-subtle flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2"><Terminal size={18} className="text-accent" /> System Terminal</h3>
                            <div className="flex gap-4 items-center">
                                <span className="text-[10px] font-bold text-muted flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-success animate-pulse" /> Live Uplink
                                </span>
                                <button onClick={() => refetchLogs()} className="btn btn-ghost h-9 px-4 text-xs font-bold gap-2">
                                    <RefreshCw size={14} className={isLogsLoading ? 'animate-spin' : ''} /> Force Update
                                </button>
                            </div>
                        </div>
                        <div className="h-[600px] overflow-y-auto p-8 font-mono text-xs bg-black/60 relative scrollbar-custom">
                            <div className="space-y-1">
                                {logs.map((log: string, idx: number) => (
                                    <div key={idx} className="flex gap-6 group hover:bg-white/5 py-0.5 px-2 rounded -mx-2 transition-colors">
                                        <span className="text-white/20 select-none w-10 shrink-0">{(idx + 1).toString().padStart(4, '0')}</span>
                                        <span className={`
                                            ${log.includes('ERROR') ? 'text-error font-bold shadow-glow-error' : 
                                              log.includes('WARNING') ? 'text-warning' : 
                                              log.includes('INFO') ? 'text-primary/80' : 'text-muted/60'}
                                        `}>
                                            {log}
                                        </span>
                                    </div>
                                ))}
                            </div>
                            {logs.length === 0 && (
                                <div className="h-full flex flex-col items-center justify-center text-muted gap-4">
                                    <RefreshCw size={32} className="animate-spin opacity-20" />
                                    <p className="italic font-display uppercase tracking-widest text-[10px]">Synchronizing with core engine...</p>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
