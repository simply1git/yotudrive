/**
 * YotuDrive API Client
 * Axios instance + React Query hooks + auth interceptor
 */
import axios from 'axios'

// Allow override via env for desktop (Electron points to local Flask)
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

// ─── Token storage ────────────────────────────────────────────────
const TOKEN_KEY = 'yotu_bearer'

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

// ─── Axios client ─────────────────────────────────────────────────
export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      clearToken()
      if (typeof window !== 'undefined') window.location.href = '/'
    }
    return Promise.reject(err)
  }
)

// ─── Types ────────────────────────────────────────────────────────
export interface ApiResponse<T = any> {
  status: 'ok' | 'error'
  data?: T
  error?: {
    code: string
    message: string
  }
}

export interface Job {
  id: string
  kind: string
  status: 'pending' | 'running' | 'done' | 'failed'
  progress: number
  message: string
  result?: any
  error?: string
  owner_email?: string
  created_at: number
}

// ─── Helper ───────────────────────────────────────────────────────
async function get<T>(path: string, params?: any): Promise<T> {
  const res = await api.get(path, { params })
  return res.data
}

async function post<T>(path: string, body?: any): Promise<T> {
  const res = await api.post(path, body)
  return res.data
}

async function put<T>(path: string, body?: any): Promise<T> {
  const res = await api.put(path, body)
  return res.data
}

async function del<T>(path: string, params?: any): Promise<T> {
  const res = await api.delete(path, { params })
  return res.data
}

// ─── Auth ─────────────────────────────────────────────────────────
export const authApi = {
  health: () => get<ApiResponse>('/api/health'),
  devLogin: (email: string) => post<{ user: any; token: string }>('/api/auth/dev/login', { email }),
  googleStart: () => get<{ url: string }>('/api/auth/google/start'),
  googleStatus: () => get<{ authenticated: boolean; user?: any }>('/api/auth/google/status'),
  session: () => get<{ user: any }>('/api/auth/session'),
  logout: () => post<ApiResponse>('/api/auth/logout'),
  bootstrapAdmin: (email: string) => post<ApiResponse>('/api/auth/bootstrap-admin', { email }),
}

// ─── Files ───────────────────────────────────────────────────────
export const filesApi = {
  list: (params?: { include_legacy?: boolean }) => get<{ files: any[] }>('/api/me/files', params),
  delete: (fileId: string) => del<ApiResponse>(`/api/me/files/${fileId}`),
  attach: (fileId: string, videoId: string, videoUrl?: string) =>
    post<ApiResponse>(`/api/me/files/${fileId}/attach`, { video_id: videoId, video_url: videoUrl }),
  registerManual: (data: { file_name: string; video_id: string; file_size?: number }) =>
    post<{ file_id: string }>('/api/upload/manual/register', data),
}

// ─── Jobs ─────────────────────────────────────────────────────────
export const jobsApi = {
  list: (params?: { limit?: number; offset?: number; status?: string }) =>
    get<{ jobs: Job[]; total: number }>('/api/me/jobs', params),
  get: (jobId: string) => get<{ job: Job }>(`/api/jobs/${jobId}`),
  cancel: (jobId: string) => post<ApiResponse>(`/api/jobs/${jobId}/cancel`),
  clear: () => post<ApiResponse>(`/api/me/jobs/clear`),
  encodeStart: (data: { input_file: string; output_dir: string; password?: string; block_size?: number; ecc_bytes?: number }) =>
    post<{ job_id: string }>('/api/encode/start', data),
  decodeStart: (data: { frames_dir: string; output_path: string; password?: string }) =>
    post<{ job_id: string }>('/api/decode/start', data),
  pipelineEncodeStart: (data: { input_file: string; output_video: string; password?: string; overrides?: any; register_in_db?: boolean }) =>
    post<{ job_id: string }>('/api/pipeline/encode-video/start', data),
  pipelineDecodeStart: (data: { video_path: string; output_file: string; password?: string; overrides?: any }) =>
    post<{ job_id: string }>('/api/pipeline/decode-video/start', data),
}

// ─── Settings ─────────────────────────────────────────────────────
export const settingsApi = {
  get: () => get<Record<string, any>>('/api/settings'),
  update: (settings: Record<string, any>) => put<ApiResponse>('/api/settings', settings),
}

// ─── Tools ────────────────────────────────────────────────────────
export const toolsApi = {
  verify: (videoPath: string) => post<ApiResponse>('/api/verify', { video_path: videoPath }),
  autoJoin: (fileList: string[]) => post<ApiResponse>('/api/tools/auto-join', { file_list: fileList }),
  inspectPlaylist: (playlistUrl: string) =>
    post<any>('/api/youtube/playlist/inspect', { playlist_url: playlistUrl }),
}

// ─── Admin ────────────────────────────────────────────────────────
export const adminApi = {
  users: {
    list: () => get<any[]>('/api/admin/users'),
    add: (email: string, role?: string) => post<any>('/api/admin/users', { email, role }),
    patch: (email: string, enabled: boolean) =>
      api.patch<any>(`/api/admin/users/${email}`, { enabled }).then((r) => r.data),
  },
  sessions: {
    list: (params?: { email?: string; include_revoked?: boolean }) =>
      get<any[]>('/api/admin/sessions', params),
    revokeAll: (email: string) => del<ApiResponse>('/api/admin/sessions', { email }),
    revoke: (tokenId: string) => del<ApiResponse>(`/api/admin/sessions/${tokenId}`),
  },
  jobs: {
    list: (params?: { owner_email?: string; status?: string }) =>
      get<{ jobs: Job[]; total: number }>('/api/admin/jobs', params),
    get: (jobId: string) => get<{ job: Job }>(`/api/admin/jobs/${jobId}`),
    delete: (jobId: string) => del<ApiResponse>(`/api/admin/jobs/${jobId}`),
  },
  metrics: () => get<any>('/api/admin/metrics'),
  system: {
    logs: () => get<string[]>('/api/admin/system/logs'),
  },
}

// ─── Storage ──────────────────────────────────────────────────────
export const storageApi = {
  upload: (file: File): Promise<{ path: string }> => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/api/storage/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
}
