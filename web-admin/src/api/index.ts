/* ====== MyClaw Admin — API 层 ====== */

const BASE = '' // Vite proxy handles /api → localhost:9910
const TOKEN_KEY = 'myclaw_admin_token'

// -------- types --------

export interface HealthData {
  status: string
  uptime: number
  active_sessions: number
  qq_online: boolean
}

export interface SkillInfo {
  name: string
  description: string
  folder: string
}

// -------- helpers --------

function token(): string {
  return localStorage.getItem(TOKEN_KEY) || 'myclaw-admin-2026'
}

export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t)
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token()}`,
      ...options?.headers,
    },
  })
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
  return res.json()
}

// -------- endpoints --------

export async function fetchHealth(): Promise<HealthData> {
  return request<HealthData>('/api/health')
}

export async function fetchSkills(): Promise<SkillInfo[]> {
  return request<SkillInfo[]>('/api/skills')
}

// -------- SSE --------

export type SSECallback = (data: any) => void

export function connectMonitorStream(onMessage: SSECallback): EventSource {
  const url = `${BASE}/api/monitor/stream`
  const es = new EventSource(url)

  es.onmessage = (e) => {
    try {
      const parsed = JSON.parse(e.data)
      onMessage(parsed)
    } catch {
      // 忽略解析失败的行
    }
  }

  es.onerror = () => {
    // EventSource 会自动重连，不需要手动处理
  }

  return es
}
