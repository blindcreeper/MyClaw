/* ====== useHealth — 健康检查轮询 ====== */

import { ref, onMounted, onUnmounted, type Ref } from 'vue'
import { fetchHealth, type HealthData } from '@/api'

export function useHealth(): {
  health: Ref<HealthData | null>
  error: Ref<string>
  loading: Ref<boolean>
} {
  const health = ref<HealthData | null>(null)
  const error = ref('')
  const loading = ref(true)
  let timer: ReturnType<typeof setInterval> | null = null

  async function poll() {
    try {
      health.value = await fetchHealth()
      error.value = ''
    } catch (e: any) {
      error.value = e.message || '无法连接服务器'
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    poll()
    timer = setInterval(poll, 5000) // 每 5 秒刷新
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { health, error, loading }
}
