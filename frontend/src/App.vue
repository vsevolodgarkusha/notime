<script setup lang="ts">
import { RouterView, RouterLink, useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()

const isTasksActive = computed(() => route.path === '/tasks' || route.path === '/')
const isFriendsActive = computed(() => route.path === '/friends')
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
      <RouterLink to="/friends" :class="['nav-item', { active: isFriendsActive }]">
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
}

.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
}

.main-content {
  flex: 1;
  padding-bottom: 90px;
  overflow-y: auto;
}

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  gap: 8px;
  background: rgba(15, 15, 26, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid var(--border);
  padding: 12px 24px;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
  z-index: 100;
}

.nav-item {
  flex: 1;
  max-width: 160px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  text-decoration: none;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.nav-item:hover {
  background: var(--bg-card);
}

.nav-item.active {
  color: var(--accent);
  background: var(--accent-light);
}

.nav-icon-wrapper {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.nav-item.active .nav-icon-wrapper {
  background: var(--accent);
  box-shadow: 0 4px 15px rgba(108, 92, 231, 0.4);
}

.nav-icon {
  font-size: 22px;
  transition: transform 0.3s ease;
}

.nav-item.active .nav-icon {
  transform: scale(1.1);
  filter: brightness(2) saturate(0);
}

.nav-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.3px;
}
</style>
