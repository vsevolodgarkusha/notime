<template>
  <div class="task-list-container">
    <header class="page-header">
      <h1 class="header-title">Мои задачи</h1>
      <p class="header-subtitle" v-if="activeTasks.length">{{ activeTasks.length }} активных</p>
    </header>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Загрузка задач...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <span class="error-icon">⚠️</span>
      <p>{{ error }}</p>
    </div>

    <template v-else>
      <div v-if="activeTasks.length" class="tasks-section">
        <div v-for="task in activeTasks" :key="task.id" class="task-card">
          <div class="task-header">
            <div class="task-status-indicator" :class="task.status"></div>
            <span class="task-status-text">{{ statusLabel(task.status) }}</span>
          </div>

          <div class="task-body">
            <div v-if="editingTaskId === task.id" class="edit-mode">
              <input
                v-model="editingText"
                @keyup.enter="saveEdit(task)"
                @keyup.esc="cancelEdit"
                class="edit-input"
                placeholder="Описание задачи..."
              />
              <div class="edit-actions">
                <button @click="saveEdit(task)" class="btn-icon save">
                  <span>✓</span>
                </button>
                <button @click="cancelEdit" class="btn-icon cancel">
                  <span>✕</span>
                </button>
              </div>
            </div>
            <div v-else @click="startEdit(task)" class="task-description">
              {{ task.description }}
              <span class="edit-hint">✏️</span>
            </div>
          </div>

          <div class="task-time">
            <span class="time-icon">⏰</span>
            {{ task.display_date || formatDate(task.due_date) }}
          </div>

          <div class="task-actions">
            <button @click="completeTask(task.id)" class="btn btn-complete">
              <span class="btn-icon-left">✓</span>
              Завершить
            </button>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <div class="empty-icon">📝</div>
        <h3>Нет активных задач</h3>
        <p>Отправьте боту сообщение, чтобы создать напоминание</p>
      </div>

      <div v-if="completedTasks.length" class="completed-section">
        <div class="section-divider">
          <div class="divider-line"></div>
          <span class="divider-text">Завершённые</span>
          <div class="divider-line"></div>
        </div>

        <div v-for="task in completedTasks" :key="task.id" class="task-card completed">
          <div class="task-header">
            <div class="task-status-indicator" :class="task.status"></div>
            <span class="task-status-text">{{ statusLabel(task.status) }}</span>
          </div>
          <div class="task-body">
            <div class="task-description strikethrough">{{ task.description }}</div>
          </div>
          <div class="task-time completed-time">
            <span class="time-icon">✓</span>
            {{ task.display_completed_at || (task.display_date || formatDate(task.due_date)) }}
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';

interface Task {
  id: number;
  description: string;
  due_date: string;
  display_date: string;
  status: string;
  created_at: string;
  completed_at?: string;
  display_completed_at?: string;
}

const tasks = ref<Task[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const editingTaskId = ref<number | null>(null);
const editingText = ref('');

const API_BASE = '/api';

const getAuthHeaders = (): HeadersInit => {
  const initData = window.Telegram?.WebApp?.initData;
  if (initData) {
    return {
      'Authorization': `tma ${initData}`,
      'Content-Type': 'application/json'
    };
  }
  return { 'Content-Type': 'application/json' };
};

const activeTasks = computed(() =>
  tasks.value.filter(t => t.status === 'created' || t.status === 'scheduled' || t.status === 'sent')
    .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime())
);

const completedTasks = computed(() =>
  tasks.value.filter(t => t.status === 'completed')
    .sort((a, b) => {
      const aTime = a.completed_at ? new Date(a.completed_at).getTime() : 0;
      const bTime = b.completed_at ? new Date(b.completed_at).getTime() : 0;
      return bTime - aTime;
    })
);

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    created: 'Запланировано',
    scheduled: 'Запланировано',
    sent: 'Отправлено',
    completed: 'Завершено',
  };
  return labels[status] || status;
};

const formatDate = (isoDate: string) => {
  if (!isoDate) return '';
  const date = new Date(isoDate);
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const isToday = date.toDateString() === now.toDateString();
  const isTomorrow = date.toDateString() === tomorrow.toDateString();

  const time = date.toLocaleString('ru-RU', { hour: '2-digit', minute: '2-digit' });

  if (isToday) return `Сегодня, ${time}`;
  if (isTomorrow) return `Завтра, ${time}`;

  return date.toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const fetchTasks = async () => {
  try {
    const response = await fetch(`${API_BASE}/tasks`, {
      headers: getAuthHeaders()
    });
    if (response.status === 401) {
      error.value = 'Ошибка авторизации';
      loading.value = false;
      return;
    }
    if (!response.ok) throw new Error('Не удалось загрузить задачи');
    tasks.value = await response.json();
  } catch (e: any) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
};

const updateTaskStatus = async (id: number, status: string) => {
  try {
    const response = await fetch(`${API_BASE}/tasks/${id}`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify({ status }),
    });
    if (!response.ok) throw new Error('Не удалось обновить статус');

    const taskIndex = tasks.value.findIndex(t => t.id === id);
    if (taskIndex !== -1) {
      tasks.value[taskIndex]!.status = status;
    }
  } catch (e: any) {
    error.value = e.message;
  }
};

const completeTask = (id: number) => updateTaskStatus(id, 'completed');

const startEdit = (task: Task) => {
  editingTaskId.value = task.id;
  editingText.value = task.description;
};

const cancelEdit = () => {
  editingTaskId.value = null;
  editingText.value = '';
};

const saveEdit = async (task: Task) => {
  if (!editingText.value.trim() || editingText.value === task.description) {
    cancelEdit();
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/tasks/${task.id}`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify({ description: editingText.value }),
    });

    if (!response.ok) throw new Error('Не удалось сохранить изменения');

    task.description = editingText.value;
    cancelEdit();
  } catch (e: any) {
    error.value = e.message;
  }
};

onMounted(() => {
  if (window.Telegram?.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
  }

  fetchTasks();
});
</script>

<style scoped>
.task-list-container {
  padding: 16px;
  min-height: 100vh;
  background: var(--tg-bg);
}

.page-header {
  margin-bottom: 20px;
  padding: 4px 0;
}

.header-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--tg-text);
  margin-bottom: 4px;
  letter-spacing: -0.5px;
}

.header-subtitle {
  font-size: 15px;
  color: var(--tg-hint);
  font-weight: 500;
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--tg-secondary-bg);
  border-top-color: var(--tg-accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-state p,
.error-state p {
  color: var(--tg-hint);
  font-size: 15px;
}

.error-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-state {
  padding: 80px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.5;
}

.empty-state h3 {
  font-size: 20px;
  font-weight: 600;
  color: var(--tg-text);
  margin-bottom: 8px;
}

.empty-state p {
  font-size: 15px;
  color: var(--tg-hint);
  max-width: 280px;
  line-height: 1.4;
}

.task-card {
  background: var(--tg-section-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  margin-bottom: 8px;
  transition: all 0.2s ease;
}

.task-card:active {
  transform: scale(0.98);
  opacity: 0.9;
}

.task-card.completed {
  opacity: 0.65;
}

.task-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.task-status-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.task-status-indicator.created,
.task-status-indicator.scheduled {
  background: var(--warning);
}

.task-status-indicator.sent {
  background: var(--tg-accent);
}

.task-status-indicator.completed {
  background: var(--success);
}

.task-status-text {
  font-size: 11px;
  font-weight: 600;
  color: var(--tg-section-header);
  text-transform: uppercase;
  letter-spacing: 0.6px;
}

.task-body {
  margin-bottom: 12px;
  overflow: hidden;
}

.task-description {
  font-size: 16px;
  font-weight: 500;
  color: var(--tg-text);
  line-height: 1.45;
  cursor: pointer;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.task-description.strikethrough {
  text-decoration: line-through;
  opacity: 0.6;
  cursor: default;
}

.edit-hint {
  opacity: 0;
  transition: opacity 0.2s;
  font-size: 14px;
}

.task-description:hover .edit-hint {
  opacity: 0.4;
}

.edit-mode {
  display: flex;
  gap: 6px;
  align-items: center;
  width: 100%;
  min-width: 0;
}

.edit-input {
  flex: 1;
  min-width: 0;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  border: 2px solid var(--tg-accent);
  background: var(--tg-secondary-bg);
  color: var(--tg-text);
  font-size: 15px;
  font-family: inherit;
  outline: none;
}

.edit-input::placeholder {
  color: var(--tg-hint);
}

.edit-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.btn-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  transition: all 0.2s;
}

.btn-icon.save {
  background: var(--success);
  color: white;
}

.btn-icon.cancel {
  background: var(--tg-secondary-bg);
  color: var(--tg-hint);
}

.btn-icon:active {
  transform: scale(0.95);
}

.task-time {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--tg-subtitle);
  margin-bottom: 14px;
  font-weight: 500;
}

.time-icon {
  font-size: 14px;
  opacity: 0.8;
}

.completed-time {
  margin-bottom: 0;
  opacity: 0.6;
}

.task-actions {
  display: flex;
  gap: 8px;
}

.btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px 16px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-icon-left {
  font-size: 16px;
}

.btn-complete {
  background: var(--tg-button);
  color: var(--tg-button-text);
}

.btn-complete:active {
  transform: scale(0.97);
  opacity: 0.9;
}

.completed-section {
  margin-top: 28px;
}

.section-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: var(--border);
}

.divider-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--tg-section-header);
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.completed-section .task-card {
  padding: 12px 14px;
}

.completed-section .task-actions {
  display: none;
}
</style>
