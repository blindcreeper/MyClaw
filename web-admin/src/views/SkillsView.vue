<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchSkills, type SkillInfo } from '@/api'

const skills = ref<SkillInfo[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    skills.value = await fetchSkills()
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="skills-page">
    <header class="page-header">
      <h1 class="page-title">Skills</h1>
      <p class="page-subtitle">已加载 {{ skills.length }} 个技能</p>
    </header>

    <!-- 加载态 -->
    <div v-if="loading" class="loading">
      <span class="loading-spinner">◌</span>
      <span>加载中...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="error-card">
      <span class="error-icon">⚠</span>
      <div>
        <p class="error-title">加载失败</p>
        <p class="error-msg">{{ error }}</p>
      </div>
    </div>

    <!-- 空 -->
    <div v-else-if="skills.length === 0" class="empty-card">
      <span class="empty-icon">◇</span>
      <p class="empty-title">暂无技能</p>
      <p class="empty-hint">在 workspace/office/skills/ 下添加技能文件夹即可自动发现</p>
    </div>

    <!-- 技能卡片 -->
    <div v-else class="skills-grid">
      <div v-for="skill in skills" :key="skill.name" class="skill-card">
        <div class="skill-header">
          <span class="skill-folder">📁 {{ skill.folder }}</span>
          <span class="skill-badge">v1</span>
        </div>
        <h3 class="skill-name">{{ skill.name }}</h3>
        <p class="skill-desc">{{ skill.description }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.skills-page {
  max-width: 1000px;
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

/* ---- 加载 / 错误 / 空 ---- */
.loading, .error-card, .empty-card {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-xl);
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
}

.loading-spinner {
  font-size: 24px;
  animation: spin 1.5s linear infinite;
  color: var(--color-cyan);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-card {
  border-color: rgba(248, 113, 113, 0.2);
}

.error-icon {
  font-size: 24px;
}

.error-title {
  font-weight: 600;
  color: var(--color-red);
}

.error-msg {
  font-size: 13px;
  color: var(--text-dim);
  margin-top: 2px;
}

.empty-card {
  flex-direction: column;
  text-align: center;
}

.empty-icon {
  font-size: 40px;
  opacity: 0.3;
  color: var(--text-muted);
}

.empty-title {
  font-weight: 600;
  color: var(--text-secondary);
}

.empty-hint {
  font-size: 13px;
  color: var(--text-muted);
}

/* ---- 技能卡片网格 ---- */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-md);
}

.skill-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
  transition: all var(--transition-normal);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.skill-card:hover {
  background: var(--bg-card-hover);
  border-color: var(--color-purple);
  box-shadow: var(--shadow-glow-purple);
  transform: translateY(-2px);
}

.skill-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.skill-folder {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-cyan);
}

.skill-badge {
  font-size: 10px;
  font-weight: 600;
  color: var(--color-purple-light);
  background: rgba(141, 82, 255, 0.12);
  padding: 1px 8px;
  border-radius: 10px;
}

.skill-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.skill-desc {
  font-size: 13px;
  color: var(--text-dim);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
</style>
