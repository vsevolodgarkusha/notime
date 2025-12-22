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

          <div class="task-footer">
            <div class="task-time">
              <span class="time-icon">⏰</span>
              {{ task.display_date || formatDate(task.due_date) }}
            </div>
          </div>

          <div class="task-actions">
            <button @click="completeTask(task.id)" class="btn btn-complete">
              <span class="btn-icon-left">✓</span>
              Готово
            </button>
            <button @click="cancelTask(task.id)" class="btn btn-cancel">
              <span class="btn-icon-left">✕</span>
              Отменить
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
          <div class="task-footer">
            <div class="task-time">
              <span class="time-icon">⏰</span>
              {{ formatDate(task.due_date) }}
            </div>
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
}

const tasks = ref<Task[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const telegramUserId = ref<number | null>(null);

const editingTaskId = ref<number | null>(null);
const editingText = ref('');

const API_BASE = '/api';

const activeTasks = computed(() =>
  tasks.value.filter(t => t.status === 'created' || t.status === 'scheduled' || t.status === 'sent')
    .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime())
);

const completedTasks = computed(() =>
  tasks.value.filter(t => t.status === 'completed' || t.status === 'cancelled')
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
);

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    created: 'Запланировано',
    scheduled: 'Запланировано',
    sent: 'Отправлено',
    completed: 'Выполнено',
    cancelled: 'Отменено',
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
  if (!telegramUserId.value) {
    error.value = 'Не удалось получить ID пользователя';
    loading.value = false;
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/tasks?telegram_id=${telegramUserId.value}`);
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
      headers: { 'Content-Type': 'application/json' },
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
const cancelTask = (id: number) => updateTaskStatus(id, 'cancelled');

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
      headers: { 'Content-Type': 'application/json' },
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
    telegramUserId.value = window.Telegram?.WebApp?.initDataUnsafe?.user?.id ?? null;
  }

  if (!telegramUserId.value) {
    const urlParams = new URLSearchParams(window.location.search);
    const testId = urlParams.get('telegram_id');
    if (testId) {
      telegramUserId.value = parseInt(testId);
    }
  }

  fetchTasks();
});
</script>

<style scoped>
.task-list-container {
  padding: 20px;
  min-height: 100vh;
}

.page-header {
  margin-bottom: 24px;
  padding: 0 4px;
}

.header-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
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
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-state p,
.error-state p {
  color: var(--text-secondary);
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
  opacity: 0.8;
}

.empty-state h3 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.empty-state p {
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 240px;
}

.task-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
  transition: all 0.3s ease;
}

.task-card:hover {
  border-color: rgba(255, 255, 255, 0.1);
  transform: translateY(-2px);
}

.task-card.completed {
  opacity: 0.6;
}

.task-card.completed:hover {
  transform: none;
}

.task-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.task-status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.task-status-indicator.created,
.task-status-indicator.scheduled {
  background: var(--warning);
  box-shadow: 0 0 8px var(--warning);
}

.task-status-indicator.sent {
  background: var(--success);
  box-shadow: 0 0 8px var(--success);
}

.task-status-indicator.completed {
  background: var(--success);
}

.task-status-indicator.cancelled {
  background: var(--danger);
}

.task-status-text {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.task-body {
  margin-bottom: 12px;
  overflow: hidden;
}

.task-description {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.5;
  cursor: pointer;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.task-description.strikethrough {
  text-decoration: line-through;
  opacity: 0.7;
  cursor: default;
}

.edit-hint {
  opacity: 0;
  transition: opacity 0.2s;
  font-size: 14px;
}

.task-description:hover .edit-hint {
  opacity: 0.5;
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
  border: 1px solid var(--accent);
  background: rgba(108, 92, 231, 0.1);
  color: var(--text-primary);
  font-size: 15px;
  font-family: inherit;
  outline: none;
}

.edit-input::placeholder {
  color: var(--text-secondary);
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
  background: var(--border);
  color: var(--text-secondary);
}

.btn-icon:hover {
  transform: scale(1.05);
}

.task-footer {
  margin-bottom: 16px;
}

.task-time {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.time-icon {
  font-size: 14px;
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
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-icon-left {
  font-size: 16px;
}

.btn-complete {
  background: linear-gradient(135deg, var(--success) 0%, #00b359 100%);
  color: white;
}

.btn-complete:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 210, 106, 0.35);
}

.btn-cancel {
  background: rgba(255, 71, 87, 0.15);
  color: var(--danger);
  border: 1px solid rgba(255, 71, 87, 0.3);
}

.btn-cancel:hover {
  background: var(--danger);
  color: white;
  border-color: transparent;
}

.completed-section {
  margin-top: 32px;
}

.section-divider {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: var(--border);
}

.divider-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.completed-section .task-card {
  padding: 14px;
}

.completed-section .task-actions {
  display: none;
}
</style>
