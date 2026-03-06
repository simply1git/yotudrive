'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/lib/api'
import { ShieldAlert, Users, Activity, LogOut, Check, X, Shield, Plus } from 'lucide-react'

export default function AdminPage() {
    const queryClient = useQueryClient()

    const { data: usersData, isLoading: usersLoading } = useQuery({ queryKey: ['admin_users'], queryFn: () => adminApi.users.list() })
    const { data: metricsData } = useQuery({ queryKey: ['admin_metrics'], queryFn: () => adminApi.metrics() })

    const [newEmail, setNewEmail] = useState('')
    const [newRole, setNewRole] = useState('member')

    const addUserMut = useMutation({
        mutationFn: (data: any) => adminApi.users.add(data.email, data.role),
        onSuccess: () => {
            setNewEmail('')
            queryClient.invalidateQueries({ queryKey: ['admin_users'] })
            queryClient.invalidateQueries({ queryKey: ['admin_metrics'] })
        },
        onError: (err: any) => alert(err.response?.data?.error?.message || 'Error adding user')
    })

    const toggleUserMut = useMutation({
        mutationFn: (data: { email: string, enabled: boolean }) => adminApi.users.patch(data.email, data.enabled),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin_users'] })
    })

    const revokeAllMut = useMutation({
        mutationFn: (email: string) => adminApi.sessions.revokeAll(email),
        onSuccess: () => alert('Sessions revoked.')
    })

    // Security Gate
    if (!usersLoading && !usersData) {
        return (
            <div className="card text-center py-20 max-w-lg mx-auto mt-20">
                <ShieldAlert size={48} className="mx-auto text-error mb-4" />
                <h3 className="text-xl font-bold">Access Denied</h3>
                <p className="text-muted mt-2">You must be an administrator to view this page.</p>
            </div>
        )
    }

    const users = usersData?.users || []
    const metrics = metricsData || { users: {}, jobs: { by_status: {} }, files: {} }

    return (
        <div>
            <header className="page-header mb-8">
                <h1 className="page-title"><ShieldAlert size={28} className="inline mr-3 text-accent" />Admin Panel</h1>
                <p className="page-subtitle">Manage platform users, metrics, and global state.</p>
            </header>

            {/* Metrics Row */}
            <div className="grid-4 mb-8">
                <div className="stat-card border-accent/30 bg-accent/5">
                    <p className="stat-label flex items-center gap-2 text-accent"><Users size={16} /> Active Users</p>
                    <p className="stat-value">{metrics.users.active} / {metrics.users.cap}</p>
                </div>
                <div className="stat-card">
                    <p className="stat-label flex items-center gap-2"><Activity size={16} /> Total Jobs Executed</p>
                    <p className="stat-value">{metrics.jobs.total || 0}</p>
                </div>
                <div className="stat-card">
                    <p className="stat-label flex items-center gap-2"><Check className="text-success" size={16} /> Success Rate</p>
                    <p className="stat-value">
                        {metrics.jobs.total ? Math.round(((metrics.jobs.by_status.done || 0) / metrics.jobs.total) * 100) : 100}%
                    </p>
                </div>
                <div className="stat-card">
                    <p className="stat-label flex items-center gap-2 text-warning"><Shield size={16} /> Ghost / Legacy Files</p>
                    <p className="stat-value">{metrics.files.legacy || 0}</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* User Management List */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="card">
                        <div className="p-5 border-b border-subtle flex justify-between items-center">
                            <h2 className="font-semibold text-lg flex items-center gap-2"><Users size={18} className="text-accent" /> User Directory</h2>
                            <span className="badge badge-member">{users.length} enrolled</span>
                        </div>

                        <div className="table-wrapper border-0 rounded-none rounded-b-lg">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Email</th>
                                        <th>Role</th>
                                        <th>Status</th>
                                        <th className="text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map((u: any) => (
                                        <tr key={u.email}>
                                            <td className="font-medium text-primary">{u.email}</td>
                                            <td>
                                                <span className={`badge ${u.role === 'admin' ? 'badge-admin' : 'badge-member'}`}>
                                                    {u.role}
                                                </span>
                                            </td>
                                            <td>
                                                {u.enabled ? (
                                                    <span className="flex items-center gap-1 text-success text-xs font-semibold"><Check size={14} /> Active</span>
                                                ) : (
                                                    <span className="flex items-center gap-1 text-error text-xs font-semibold"><X size={14} /> Disabled</span>
                                                )}
                                            </td>
                                            <td className="text-right flex items-center justify-end gap-2">
                                                <button
                                                    className={`btn btn-sm ${u.enabled ? 'btn-danger' : 'btn-ghost'}`}
                                                    onClick={() => toggleUserMut.mutate({ email: u.email, enabled: !u.enabled })}
                                                    disabled={toggleUserMut.isPending}
                                                >
                                                    {u.enabled ? 'Disable' : 'Enable'}
                                                </button>
                                                <button
                                                    title="Revoke all active sessions for this user"
                                                    className="btn btn-ghost btn-sm text-warning hover:text-warning"
                                                    onClick={() => {
                                                        if (confirm(`Revoke all sessions for ${u.email}?`)) revokeAllMut.mutate(u.email)
                                                    }}
                                                >
                                                    <LogOut size={14} />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                {/* Add User Tool */}
                <div>
                    <form className="card sticky top-6" onSubmit={(e) => { e.preventDefault(); addUserMut.mutate({ email: newEmail, role: newRole }) }}>
                        <div className="p-5 border-b border-subtle">
                            <h2 className="font-semibold text-lg flex items-center gap-2"><Plus size={18} className="text-success" /> Provision Account</h2>
                        </div>
                        <div className="p-5 space-y-4">
                            <div className="input-group">
                                <label className="input-label">Email Address</label>
                                <input
                                    type="email" required className="input" placeholder="new.user@domain.com"
                                    value={newEmail} onChange={e => setNewEmail(e.target.value)}
                                />
                            </div>
                            <div className="input-group">
                                <label className="input-label">System Role</label>
                                <select className="input cursor-pointer" value={newRole} onChange={e => setNewRole(e.target.value)}>
                                    <option value="member">Member (Read/Write)</option>
                                    <option value="admin">Administrator (Full Access)</option>
                                </select>
                            </div>
                            <button disabled={addUserMut.isPending || !newEmail} className="btn btn-primary w-full justify-center mt-2">
                                Create Account
                            </button>
                            <p className="text-xs text-muted text-center max-w-xs mx-auto mt-4">
                                Users must log in using Google OAuth with this exact email address to gain entry.
                            </p>
                        </div>
                    </form>
                </div>

            </div>
        </div>
    )
}
