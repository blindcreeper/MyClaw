<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  icon: string
  accent?: 'cyan' | 'purple' | 'green' | 'yellow' | 'red'
}>()
</script>

<template>
  <div class="status-card" :class="[`accent-${accent || 'purple'}`]">
    <span class="card-icon">{{ icon }}</span>
    <div class="card-body">
      <span class="card-value">{{ value }}</span>
      <span class="card-label">{{ label }}</span>
    </div>
  </div>
</template>

<style scoped>
.status-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
  display: flex;
  align-items: center;
  gap: var(--space-md);
  transition: all var(--transition-normal);
}

.status-card:hover {
  background: var(--bg-card-hover);
  border-color: var(--border-active);
  transform: translateY(-1px);
}

.card-icon {
  font-size: 28px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: rgba(141, 82, 255, 0.1);
  flex-shrink: 0;
}

.accent-cyan .card-icon {
  background: rgba(0, 255, 255, 0.1);
  color: var(--color-cyan);
}

.accent-purple .card-icon {
  background: rgba(141, 82, 255, 0.1);
  color: var(--color-purple);
}

.accent-green .card-icon {
  background: rgba(74, 222, 128, 0.1);
  color: var(--color-green);
}

.accent-yellow .card-icon {
  background: rgba(251, 191, 36, 0.1);
  color: var(--color-yellow);
}

.accent-red .card-icon {
  background: rgba(248, 113, 113, 0.1);
  color: var(--color-red);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.card-value {
  font-size: 22px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.card-label {
  font-size: 12px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>
