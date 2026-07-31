/* ====== useSSE — 实时日志流 ====== */

import { ref, onMounted, onUnmounted, type Ref } from 'vue'
import { connectMonitorStream } from '@/api'

export interface LogEntry {
  ts: string
  thread_id: string
  event: string
  [key: string]: any
}

export function useSSE(): {
  logs: Ref<LogEntry[]>
  paused: Ref<boolean>
  count: Ref<number>
  togglePause: () => void
  clearLogs: () => void
} {
  const logs = ref<LogEntry[]>([])
  const paused = ref(false)
  const count = ref(0)
  let es: EventSource | null = null
  let buffer: LogEntry[] = []

  function flushBuffer() {
    if (buffer.length > 0) {
      logs.value = [...logs.value, ...buffer].slice(-500) // 最多保留 500 条
      count.value += buffer.length
      buffer = []
    }
  }

  onMounted(() => {
    es = connectMonitorStream((entry: LogEntry) => {
      if (paused.value) {
        buffer.push(entry)
      } else {
        buffer.push(entry)
        flushBuffer()
      }
    })

    // 每秒刷新一次缓冲区（暂停期间积累的日志批量展示）
    const flushTimer = setInterval(flushBuffer, 1000)

    onUnmounted(() => {
      clearInterval(flushTimer)
    })
  })

  onUnmounted(() => {
    es?.close()
  })

  function togglePause() {
    paused.value = !paused.value
    if (!paused.value) {
      flushBuffer()
    }
  }

  function clearLogs() {
    logs.value = []
    buffer = []
    count.value = 0
  }

  return { logs, paused, count, togglePause, clearLogs }
}
