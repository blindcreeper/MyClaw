<script setup lang="ts">
import { computed } from 'vue'
import StatusCard from '@/components/StatusCard.vue'
import type { HealthData } from '@/api'

const props = defineProps<{
  health: HealthData | null
}>()

const fmtUptime = computed(() => {
  if (!props.health) return '--'
  const s = props.health.uptime
  if (s < 60) return `${Math.floor(s)}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
})

const serverStatus = computed(() =>
  props.health?.status === 'ok' ? 'Running' : 'Degraded'
)

const serverStatusColor = computed(() =>
  props.health?.status === 'ok' ? 'green' : 'red'
)

const qqStatus = computed(() =>
  props.health?.qq_online ? 'Online' : 'Offline'
)

const qqStatusColor = computed(() =>
  props.health?.qq_online ? 'green' : 'red'
)
</script>

<template>
  <div class="dashboard">
    <header class="page-header">
      <h1 class="page-title">Dashboard</h1>
      <p class="page-subtitle">MyClaw 服务状态概览</p>
    </header>

    <!-- 状态卡片网格 -->
    <div class="card-grid">
      <StatusCard
        :label="serverStatus"
        :value="serverStatus"
        icon="◈"
        :accent="serverStatusColor"
      />
      <StatusCard
        label="Uptime"
        :value="fmtUptime"
        icon="⏱"
        accent="cyan"
      />
      <StatusCard
        label="Active Sessions"
        :value="health?.active_sessions ?? '--'"
        icon="◎"
        accent="purple"
      />
      <StatusCard
        :label="`QQ Bot: ${qqStatus}`"
        :value="qqStatus"
        icon="☁"
        :accent="qqStatusColor"
      />
    </div>

    <!-- 详情面板 -->
    <div class="detail-panel">
      <h2 class="section-title">连接信息</h2>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">OneBot WS</span>
          <code class="info-value">ws://127.0.0.1:9910/ws/onebot</code>
        </div>
        <div class="info-item">
          <span class="info-label">Admin Panel</span>
          <code class="info-value">http://localhost:9910</code>
        </div>
        <div class="info-item">
          <span class="info-label">Health API</span>
          <code class="info-value">GET /api/health</code>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 900px;
}

.page-header {
  margin-bottom: var(--space-xl);
}

.page-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  margin-top: var(--space-xs);
  font-size: 14px;
  color: var(--text-dim);
}

/* ---- 卡片网格 ---- */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-md);
  margin-bottom: var(--space-2xl);
}

/* ---- 详情面板 ---- */
.detail-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-lg) var(--space-xl);
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-md);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.info-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-sm) 0;
  border-bottom: 1px solid var(--border-subtle);
}

.info-item:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 13px;
  color: var(--text-dim);
}

.info-value {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-cyan);
  background: rgba(0, 255, 255, 0.06);
  padding: 4px var(--space-sm);
  border-radius: var(--radius-sm);
}
</style>
