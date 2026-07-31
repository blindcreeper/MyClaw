<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useSSE } from '@/composables/useSSE'
import LogLine from '@/components/LogLine.vue'

const { logs, paused, count, togglePause, clearLogs } = useSSE()

const logContainer = ref<HTMLElement | null>(null)
const autoScroll = ref(true)

// 用户手动滚动时暂停自动滚动，滚到底部时恢复
function onScroll() {
  if (!logContainer.value) return
  const el = logContainer.value
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  autoScroll.value = atBottom
}

// 新日志到达时自动滚到底部
watch(
  () => logs.value.length,
  () => {
    if (autoScroll.value) {
      nextTick(() => {
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight
        }
      })
    }
  }
)
</script>

<template>
  <div class="monitor">
    <header class="page-header">
      <div class="header-left">
        <h1 class="page-title">Monitor</h1>
        <p class="page-subtitle">实时审计日志流</p>
      </div>
      <div class="header-actions">
        <span class="log-count">{{ count }} 条</span>
        <button
          class="action-btn"
          :class="{ active: paused }"
          @click="togglePause"
        >
          {{ paused ? '▶ 继续' : '⏸ 暂停' }}
        </button>
        <button class="action-btn" @click="clearLogs">🗑 清空</button>
      </div>
    </header>

    <!-- 日志流 -->
    <div
      ref="logContainer"
      class="log-container"
      @scroll="onScroll"
    >
      <div v-if="logs.length === 0" class="empty-state">
        <span class="empty-icon">◉</span>
        <span class="empty-text">等待日志事件...</span>
        <span class="empty-hint">启动 NapCat 并发送消息后，这里将实时显示 Agent 活动</span>
      </div>

      <LogLine v-for="(entry, i) in logs" :key="i" :entry="entry" />

      <!-- 自动滚动指示器 -->
      <div v-if="!autoScroll && logs.length > 0" class="scroll-hint" @click="autoScroll = true">
        ↓ 滚动到底部
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitor {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--space-xl) * 2);
  max-width: 1100px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-md);
  flex-shrink: 0;
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

/* ---- 操作按钮 ---- */
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.log-count {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-dim);
  margin-right: var(--space-sm);
}

.action-btn {
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--bg-card-hover);
  color: var(--text-primary);
}

.action-btn.active {
  background: rgba(251, 191, 36, 0.1);
  border-color: var(--color-yellow);
  color: var(--color-yellow);
}

/* ---- 日志容器 ---- */
.log-container {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-sm);
  position: relative;
}

/* ---- 空状态 ---- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: var(--space-sm);
  color: var(--text-muted);
}

.empty-icon {
  font-size: 40px;
  opacity: 0.3;
}

.empty-text {
  font-size: 15px;
  font-weight: 500;
}

.empty-hint {
  font-size: 12px;
  color: var(--text-muted);
}

/* ---- 滚动提示 ---- */
.scroll-hint {
  position: sticky;
  bottom: var(--space-sm);
  left: 50%;
  transform: translateX(-50%);
  display: inline-flex;
  padding: 6px 16px;
  border-radius: 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-active);
  color: var(--color-cyan);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--shadow-glow-cyan);
  z-index: 10;
}

.scroll-hint:hover {
  background: var(--bg-card-hover);
}
</style>
