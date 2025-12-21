<script setup lang="ts">
import { RouterView, RouterLink, useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()

const isTasksActive = computed(() => route.path === '/tasks' || route.path === '/')
const isFriendsActive = computed(() => route.path === '/friends')
</script>

<template>
  <div class="app-container">
    <nav class="bottom-nav">
      <RouterLink to="/tasks" :class="['nav-item', { active: isTasksActive }]">
        <span class="nav-icon">📋</span>
        <span class="nav-label">Задачи</span>
      </RouterLink>
      <RouterLink to="/friends" :class="['nav-item', { active: isFriendsActive }]">
        <span class="nav-icon">👥</span>
        <span class="nav-label">Друзья</span>
      </RouterLink>
    </nav>
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--tg-theme-bg-color, #1a1a2e);
}

.main-content {
  flex: 1;
  padding-bottom: 70px;
}

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  background-color: var(--tg-theme-secondary-bg-color, #2d2d44);
  border-top: 1px solid var(--tg-theme-hint-color, #333);
  padding: 8px 16px;
  padding-bottom: max(8px, env(safe-area-inset-bottom));
  z-index: 100;
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px;
  text-decoration: none;
  color: var(--tg-theme-hint-color, #888);
  transition: color 0.2s;
}

.nav-item.active {
  color: var(--tg-theme-button-color, #5288c1);
}

.nav-icon {
  font-size: 24px;
}

.nav-label {
  font-size: 12px;
  font-weight: 500;
}
</style>

