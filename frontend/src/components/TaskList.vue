<template>
  <div class="task-list-container">
    <h1 class="header">📋 Мои задачи</h1>

    <div v-if="loading" class="feedback">Загрузка...</div>
    <div v-else-if="error" class="feedback error">{{ error }}</div>
    
    <template v-else>
      <!-- Active tasks -->
      <div v-if="activeTasks.length" class="section">
        <div v-for="task in activeTasks" :key="task.id" class="task-item">
          <div class="task-content">
            <div class="task-description">
              <div v-if="editingTaskId === task.id" class="edit-mode">
                <input 
                  v-model="editingText" 
                  ref="editInput"
                  @keyup.enter="saveEdit(task)"
                  @keyup.esc="cancelEdit"
                  class="edit-input"
                />
                <button @click="saveEdit(task)" class="btn-icon">💾</button>
                <button @click="cancelEdit" class="btn-icon">✖</button>
              </div>
              <div v-else @click="startEdit(task)" class="text-display">
                {{ task.description }} ✏️
              </div>
            </div>
            <div class="task-time">{{ task.display_date || formatDate(task.due_date) }}</div>
            <div class="task-status" :class="task.status">{{ statusLabel(task.status) }}</div>
          </div>
          <div class="task-actions">
            <button @click="completeTask(task.id)" class="btn btn-complete">✓ Готово</button>
            <button @click="cancelTask(task.id)" class="btn btn-cancel">✗ Отменить</button>
          </div>
        </div>
      </div>
      <div v-else class="feedback">Нет активных задач</div>

      <!-- Divider -->
      <div v-if="completedTasks.length" class="divider">
        <span>Завершённые</span>
      </div>

      <!-- Completed/Cancelled tasks -->
      <div v-if="completedTasks.length" class="section completed-section">
        <div v-for="task in completedTasks" :key="task.id" class="task-item inactive">
          <div class="task-content">
            <div class="task-description strikethrough">{{ task.description }}</div>
            <div class="task-time">{{ formatDate(task.due_date) }}</div>
            <div class="task-status" :class="task.status">{{ statusLabel(task.status) }}</div>
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
  tasks.value.filter(t => t.status === 'created' || t.status === 'sent')
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
);

const completedTasks = computed(() => 
  tasks.value.filter(t => t.status === 'completed' || t.status === 'cancelled')
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
);

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    created: '⏳ Ожидает',
    sent: '🔔 Отправлено',
    completed: '✅ Выполнено',
    cancelled: '❌ Отменено',
  };
  return labels[status] || status;
};

const formatDate = (isoDate: string) => {
  if (!isoDate) return '';
  const date = new Date(isoDate);
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
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
    const response = await fetch(`${API_BASE}/tasks/${id}/status`, {
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
  
  // For development without Telegram
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
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  padding: 16px;
  background-color: var(--tg-theme-bg-color, #1a1a2e);
  color: var(--tg-theme-text-color, #eaeaea);
  min-height: 100vh;
}

.header {
  text-align: center;
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 20px;
  color: var(--tg-theme-text-color, #eaeaea);
}

.feedback {
  text-align: center;
  color: var(--tg-theme-hint-color, #888);
  font-size: 16px;
  padding: 40px 20px;
}

.error {
  color: #ff6b6b;
}

.section {
  margin-bottom: 16px;
}

.task-item {
  background: var(--tg-theme-secondary-bg-color, #2d2d44);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.task-item.inactive {
  opacity: 0.6;
  background: var(--tg-theme-secondary-bg-color, #252535);
}

.task-content {
  margin-bottom: 12px;
}

.task-description {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--tg-theme-text-color, #eaeaea);
}

.task-description.strikethrough {
  text-decoration: line-through;
  opacity: 0.7;
}

.task-time {
  font-size: 13px;
  color: var(--tg-theme-hint-color, #888);
  margin-bottom: 4px;
}

.task-status {
  font-size: 12px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 6px;
  display: inline-block;
}

.task-status.created {
  background-color: rgba(255, 193, 7, 0.2);
  color: #ffc107;
}

.task-status.sent {
  background-color: rgba(33, 150, 243, 0.2);
  color: #2196f3;
}

.task-status.completed {
  background-color: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.task-status.cancelled {
  background-color: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.task-actions {
  display: flex;
  gap: 8px;
}

.btn {
  flex: 1;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-complete {
  background: linear-gradient(135deg, #4caf50 0%, #388e3c 100%);
  color: white;
}

.btn-complete:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(76, 175, 80, 0.4);
}

.btn-cancel {
  background: linear-gradient(135deg, #f44336 0%, #c62828 100%);
  color: white;
}

.btn-cancel:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(244, 67, 54, 0.4);
}

.divider {
  display: flex;
  align-items: center;
  margin: 24px 0 16px;
  color: var(--tg-theme-hint-color, #666);
  font-size: 13px;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background-color: var(--tg-theme-hint-color, #333);
}

.divider span {
  padding: 0 12px;
}

.completed-section .task-item {
  padding: 12px;
}

.completed-section .task-actions {
  display: none;
}

.edit-mode {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.edit-input {
  flex: 1;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid var(--tg-theme-hint-color, #888);
  background: var(--tg-theme-bg-color, #fff);
  color: var(--tg-theme-text-color, #000);
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  padding: 4px;
}

.text-display {
  cursor: pointer;
  border-bottom: 1px dashed transparent;
  transition: border-color 0.2s;
}

.text-display:hover {
  border-bottom-color: var(--tg-theme-hint-color, #888);
}
</style>
