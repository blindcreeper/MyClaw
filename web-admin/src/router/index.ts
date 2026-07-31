import type { Router } from 'vue-router'
import { createRouter, createWebHashHistory } from 'vue-router'

const router: Router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { title: 'Dashboard', icon: '◈' },
    },
    {
      path: '/monitor',
      name: 'monitor',
      component: () => import('@/views/MonitorView.vue'),
      meta: { title: 'Monitor', icon: '◉' },
    },
    {
      path: '/skills',
      name: 'skills',
      component: () => import('@/views/SkillsView.vue'),
      meta: { title: 'Skills', icon: '◇' },
    },
  ],
})

export default router
