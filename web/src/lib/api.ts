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

// ─── Helper ───────────────────────────────────────────────────────
async function get<T = any>(path: string, params?: any): Promise<T> {
  const res = await api.get(path, { params })
  return res.data
}

async function post<T = any>(path: string, body?: any): Promise<T> {
  const res = await api.post(path, body)
  return res.data
}

async function put<T = any>(path: string, body?: any): Promise<T> {
  const res = await api.put(path, body)
  return res.data
}

async function del<T = any>(path: string, params?: any): Promise<T> {
  const res = await api.delete(path, { params })
  return res.data
}

// ─── Auth ─────────────────────────────────────────────────────────
export const authApi = {
  health: () => get('/api/health'),
  devLogin: (email: string) => post('/api/auth/dev/login', { email }),
  googleStart: () => get('/api/auth/google/start'),
  googleStatus: () => get('/api/auth/google/status'),
  session: () => get('/api/auth/session'),
  logout: () => post('/api/auth/logout'),
  bootstrapAdmin: (email: string) => post('/api/auth/bootstrap-admin', { email }),
}

// ─── Files ───────────────────────────────────────────────────────
export const filesApi = {
  list: (params?: { include_legacy?: boolean }) => get('/api/me/files', params),
  delete: (fileId: string) => del(`/api/me/files/${fileId}`),
  attach: (fileId: string, videoId: string, videoUrl?: string) =>
    post(`/api/me/files/${fileId}/attach`, { video_id: videoId, video_url: videoUrl }),
  registerManual: (data: { file_name: string; video_id: string; file_size?: number }) =>
    post('/api/upload/manual/register', data),
}

// ─── Jobs ─────────────────────────────────────────────────────────
export const jobsApi = {
  list: (params?: { limit?: number; offset?: number; status?: string }) =>
    get('/api/me/jobs', params),
  get: (jobId: string) => get(`/api/jobs/${jobId}`),
  encodeStart: (data: { input_file: string; output_dir: string; password?: string; block_size?: number; ecc_bytes?: number }) =>
    post('/api/encode/start', data),
  decodeStart: (data: { frames_dir: string; output_path: string; password?: string }) =>
    post('/api/decode/start', data),
  pipelineEncodeStart: (data: { input_file: string; output_video: string; password?: string; overrides?: any; register_in_db?: boolean }) =>
    post('/api/pipeline/encode-video/start', data),
  pipelineDecodeStart: (data: { video_path: string; output_file: string; password?: string; overrides?: any }) =>
    post('/api/pipeline/decode-video/start', data),
}

// ─── Settings ─────────────────────────────────────────────────────
export const settingsApi = {
  get: () => get('/api/settings'),
  update: (settings: Record<string, any>) => put('/api/settings', settings),
}

// ─── Tools ────────────────────────────────────────────────────────
export const toolsApi = {
  verify: (videoPath: string) => post('/api/verify', { video_path: videoPath }),
  autoJoin: (fileList: string[]) => post('/api/tools/auto-join', { file_list: fileList }),
  inspectPlaylist: (playlistUrl: string) =>
    post('/api/youtube/playlist/inspect', { playlist_url: playlistUrl }),
}

// ─── Admin ────────────────────────────────────────────────────────
export const adminApi = {
  users: {
    list: () => get('/api/admin/users'),
    add: (email: string, role?: string) => post('/api/admin/users', { email, role }),
    patch: (email: string, enabled: boolean) =>
      api.patch(`/api/admin/users/${email}`, { enabled }).then((r) => r.data),
  },
  sessions: {
    list: (params?: { email?: string; include_revoked?: boolean }) =>
      get('/api/admin/sessions', params),
    revokeAll: (email: string) => del('/api/admin/sessions', { email }),
    revoke: (tokenId: string) => del(`/api/admin/sessions/${tokenId}`),
  },
  jobs: {
    list: (params?: { owner_email?: string; status?: string }) =>
      get('/api/admin/jobs', params),
    get: (jobId: string) => get(`/api/admin/jobs/${jobId}`),
    delete: (jobId: string) => del(`/api/admin/jobs/${jobId}`),
  },
  metrics: () => get('/api/admin/metrics'),
  system: {
    logs: () => get('/api/admin/system/logs'),
  },
}
