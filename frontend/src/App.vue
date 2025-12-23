<script setup lang="ts">
import { RouterView, RouterLink, useRoute } from 'vue-router'
import { computed, ref, onMounted } from 'vue'

const route = useRoute()

const isTasksActive = computed(() => route.path === '/tasks' || route.path === '/')
const isFriendsActive = computed(() => route.path === '/friends')

const hasFriends = ref(false)

const getAuthHeaders = (): HeadersInit => {
  const initData = window.Telegram?.WebApp?.initData
  if (initData) {
    return { 'Authorization': `tma ${initData}` }
  }
  return {}
}

onMounted(async () => {
  try {
    const response = await fetch('/api/friends/status', {
      headers: getAuthHeaders()
    })
    if (response.ok) {
      const data = await response.json()
      hasFriends.value = data.has_friends
    }
  } catch (e) {
    console.error('Failed to fetch friends status:', e)
  }
})
</script>

<template>
  <div class="app-container">
    <main class="main-content">
      <RouterView />
    </main>
    <nav class="bottom-nav">
      <RouterLink to="/tasks" :class="['nav-item', { active: isTasksActive }]">
        <div class="nav-icon-wrapper">
          <span class="nav-icon">📋</span>
        </div>
        <span class="nav-label">Задачи</span>
      </RouterLink>
      <RouterLink v-if="hasFriends" to="/friends" :class="['nav-item', { active: isFriendsActive }]">
        <div class="nav-icon-wrapper">
          <span class="nav-icon">👥</span>
        </div>
        <span class="nav-label">Друзья</span>
      </RouterLink>
    </nav>
  </div>
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-primary: var(--tg-theme-bg-color, #0f0f1a);
  --bg-secondary: var(--tg-theme-secondary-bg-color, #1a1a2e);
  --bg-card: rgba(255, 255, 255, 0.03);
  --text-primary: var(--tg-theme-text-color, #ffffff);
  --text-secondary: var(--tg-theme-hint-color, #8b8b9e);
  --accent: var(--tg-theme-button-color, #6c5ce7);
  --accent-light: rgba(108, 92, 231, 0.15);
  --success: #00d26a;
  --danger: #ff4757;
  --warning: #ffa502;
  --border: rgba(255, 255, 255, 0.06);
  --shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  --radius: 16px;
  --radius-sm: 12px;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  overflow-y: scroll;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE/Edge */
}

body::-webkit-scrollbar {
  display: none; /* Chrome/Safari/Opera */
}

.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
}

.main-content {
  flex: 1;
  padding-bottom: 44px;
  overflow-y: auto;
}

.bottom-nav {
  position: fixed;
  bottom: 8px;
  left: 12px;
  right: 12px;
  display: flex;
  justify-content: center;
  gap: 8px;
  background: rgba(30, 30, 45, 0.75);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius);
  padding: 8px 12px;
  padding-bottom: max(8px, env(safe-area-inset-bottom));
  z-index: 100;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
}

.nav-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  text-decoration: none;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.nav-item.active {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.1);
}

.nav-icon-wrapper {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-icon {
  font-size: 15px;
}

.nav-label {
  font-size: 13px;
  font-weight: 500;
}
</style>
