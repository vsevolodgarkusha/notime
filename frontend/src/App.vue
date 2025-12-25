<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="app-container">
    <main class="main-content">
      <RouterView />
    </main>
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
  /* Telegram theme colors */
  --tg-bg: var(--tg-theme-bg-color, #ffffff);
  --tg-text: var(--tg-theme-text-color, #000000);
  --tg-hint: var(--tg-theme-hint-color, #999999);
  --tg-link: var(--tg-theme-link-color, #2481cc);
  --tg-button: var(--tg-theme-button-color, #2481cc);
  --tg-button-text: var(--tg-theme-button-text-color, #ffffff);
  --tg-secondary-bg: var(--tg-theme-secondary-bg-color, #f4f4f5);
  --tg-header-bg: var(--tg-theme-header-bg-color, #ffffff);
  --tg-section-bg: var(--tg-theme-section-bg-color, #ffffff);
  --tg-section-header: var(--tg-theme-section-header-text-color, #6d6d72);
  --tg-section-separator: var(--tg-theme-section-separator-color, #d1d1d6);
  --tg-accent: var(--tg-theme-accent-text-color, #2481cc);
  --tg-subtitle: var(--tg-theme-subtitle-text-color, #999999);
  --tg-destructive: var(--tg-theme-destructive-text-color, #ff3b30);

  /* App-specific colors */
  --success: #34c759;
  --warning: #ff9500;
  --border: var(--tg-section-separator);
  --shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  --radius: 12px;
  --radius-sm: 8px;
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
  background: var(--tg-bg);
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
  background: var(--tg-secondary-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 8px 12px;
  padding-bottom: max(8px, env(safe-area-inset-bottom));
  z-index: 100;
  box-shadow: var(--shadow);
}

.nav-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  text-decoration: none;
  color: var(--tg-hint);
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
}

.nav-item:hover {
  background: var(--tg-section-bg);
}

.nav-item.active {
  color: var(--tg-accent);
  background: var(--tg-section-bg);
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
