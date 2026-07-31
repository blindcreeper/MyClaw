<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'

defineProps<{
  qqOnline: boolean
}>()

const route = useRoute()

const navItems = [
  { path: '/', name: 'dashboard', label: 'Dashboard', icon: '◈' },
  { path: '/monitor', name: 'monitor', label: 'Monitor', icon: '◉' },
  { path: '/skills', name: 'skills', label: 'Skills', icon: '◇' },
]

function isActive(name: string) {
  return route.name === name
}
</script>

<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="logo">
      <span class="logo-icon">⧫</span>
      <span class="logo-text">My<span class="accent">Claw</span></span>
    </div>

    <!-- Nav -->
    <nav class="nav">
      <router-link
        v-for="item in navItems"
        :key="item.name"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item.name) }"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- Status -->
    <div class="status-bar">
      <div class="status-dot" :class="{ online: qqOnline, offline: !qqOnline }" />
      <span class="status-text">{{ qqOnline ? 'QQ Online' : 'QQ Offline' }}</span>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 220px;
  min-width: 220px;
  height: 100vh;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  padding: var(--space-lg);
  user-select: none;
}

/* ---- Logo ---- */
.logo {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-xl);
  padding: var(--space-sm) var(--space-xs);
}

.logo-icon {
  font-size: 24px;
  color: var(--color-cyan);
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  font-family: var(--font-mono);
  letter-spacing: -0.5px;
}

.logo-text .accent {
  color: var(--color-purple);
}

/* ---- Nav ---- */
.nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.nav-item:hover {
  background: var(--bg-card);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--bg-card);
  color: var(--color-cyan);
  box-shadow: inset 2px 0 0 var(--color-cyan);
}

.nav-icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
}

/* ---- Status ---- */
.status-bar {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md);
  border-top: 1px solid var(--border-subtle);
  font-size: 12px;
  color: var(--text-dim);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.online {
  background: var(--color-green);
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.5);
}

.status-dot.offline {
  background: var(--color-red);
  box-shadow: 0 0 6px rgba(248, 113, 113, 0.3);
}

.status-text {
  font-size: 12px;
}
</style>
