<script setup lang="ts">
import { computed } from 'vue'
import type { LogEntry } from '@/composables/useSSE'

const props = defineProps<{
  entry: LogEntry
}>()

const eventLabel = computed(() => {
  const map: Record<string, string> = {
    ai_message: 'AI',
    tool_call: 'TOOL',
    tool_result: 'RESULT',
    llm_input: 'INPUT',
  }
  return map[props.entry.event] || props.entry.event.toUpperCase()
})

const eventClass = computed(() => `event-${props.entry.event}`)

const summary = computed(() => {
  const e = props.entry
  if (e.event === 'ai_message') return e.content?.slice(0, 120) || ''
  if (e.event === 'tool_call') return e.tool || ''
  if (e.event === 'tool_result') return e.result_summary?.slice(0, 80) || ''
  if (e.event === 'llm_input') return `${e.message_count || '?'} messages`
  return JSON.stringify(e).slice(0, 80)
})

const time = computed(() => {
  const ts = props.entry.ts || ''
  return ts.slice(11, 19) // "HH:MM:SS"
})
</script>

<template>
  <div class="log-line" :class="eventClass">
    <span class="log-time">{{ time }}</span>
    <span class="log-thread">{{ entry.thread_id }}</span>
    <span class="log-event">{{ eventLabel }}</span>
    <span class="log-summary">{{ summary }}</span>
  </div>
</template>

<style scoped>
.log-line {
  display: flex;
  align-items: baseline;
  gap: var(--space-md);
  padding: 6px var(--space-md);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.5;
  transition: background var(--transition-fast);
}

.log-line:hover {
  background: rgba(255, 255, 255, 0.02);
}

.log-time {
  color: var(--text-dim);
  flex-shrink: 0;
  font-size: 12px;
  width: 70px;
}

.log-thread {
  color: var(--text-muted);
  flex-shrink: 0;
  font-size: 11px;
  width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-event {
  flex-shrink: 0;
  width: 56px;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  text-align: center;
}

/* ---- Event Colors ---- */
.event-ai_message .log-event {
  background: rgba(74, 222, 128, 0.12);
  color: var(--log-ai-message);
}

.event-tool_call .log-event {
  background: rgba(0, 255, 255, 0.1);
  color: var(--log-tool-call);
}

.event-tool_result .log-event {
  background: rgba(107, 114, 128, 0.12);
  color: var(--log-tool-result);
}

.event-llm_input .log-event {
  background: rgba(179, 136, 255, 0.1);
  color: var(--log-llm-input);
}

.log-summary {
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

/* 行级高亮 */
.event-ai_message {
  border-left: 2px solid transparent;
}
.event-ai_message:hover {
  border-left-color: var(--log-ai-message);
}

.event-tool_call {
  border-left: 2px solid transparent;
}
.event-tool_call:hover {
  border-left-color: var(--log-tool-call);
}
</style>
