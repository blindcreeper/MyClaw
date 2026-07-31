<script setup lang="ts">
import AppSidebar from '@/components/AppSidebar.vue'
import { useHealth } from '@/composables/useHealth'

const { health } = useHealth()
</script>

<template>
  <div class="app-shell">
    <AppSidebar :qqOnline="health?.qq_online ?? false" />
    <main class="main-content">
      <router-view :health="health" />
    </main>
  </div>
</template>

<style>
/* ====== Global Reset ====== */
*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
  font-family: var(--font-sans);
  background: var(--bg-root);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  height: 100%;
}

a {
  color: inherit;
  text-decoration: none;
}

button {
  font-family: inherit;
  cursor: pointer;
  border: none;
  background: none;
  color: inherit;
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--border-active);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--text-dim);
}
</style>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-xl) var(--space-2xl);
}
</style>
