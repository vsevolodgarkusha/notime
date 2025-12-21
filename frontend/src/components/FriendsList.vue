<template>
  <div class="friends-container">
    <div class="tabs">
      <button
        :class="['tab', { active: activeTab === 'friends' }]"
        @click="activeTab = 'friends'"
      >
        Друзья
      </button>
      <button
        :class="['tab', { active: activeTab === 'requests' }]"
        @click="activeTab = 'requests'"
      >
        Запросы
        <span v-if="pendingCount > 0" class="badge">{{ pendingCount }}</span>
      </button>
    </div>

    <div v-if="loading" class="feedback">Загрузка...</div>
    <div v-else-if="error" class="feedback error">{{ error }}</div>

    <template v-else>
      <!-- Friends Tab -->
      <div v-if="activeTab === 'friends'" class="section">
        <div v-if="friends.length === 0" class="feedback">
          Нет друзей. Добавьте через /add_friend в боте.
        </div>
        <div v-for="friend in friends" :key="friend.id" class="friend-item">
          <div class="friend-info">
            <div class="friend-name">
              {{ friend.telegram_username ? '@' + friend.telegram_username : 'ID: ' + friend.telegram_id }}
            </div>
          </div>
        </div>
      </div>

      <!-- Requests Tab -->
      <div v-if="activeTab === 'requests'" class="section">
        <div v-if="requests.length === 0" class="feedback">
          Нет входящих запросов
        </div>
        <div v-for="request in requests" :key="request.id" class="request-item">
          <div class="request-info">
            <div class="request-from">
              От: {{ request.from_user_username ? '@' + request.from_user_username : 'ID: ' + request.from_user_telegram_id }}
            </div>
            <div class="request-status" :class="request.status">
              {{ statusLabel(request.status) }}
            </div>
          </div>
          <div class="request-actions">
            <button
              v-if="request.status === 'pending' || request.status === 'rejected'"
              @click="respondToRequest(request.id, 'accept')"
              class="btn btn-accept"
            >
              Принять
            </button>
            <button
              v-if="request.status === 'pending'"
              @click="respondToRequest(request.id, 'reject')"
              class="btn btn-reject"
            >
              Отклонить
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';

interface Friend {
  id: number;
  telegram_id: number;
  telegram_username: string | null;
  status: string;
}

interface FriendRequest {
  id: number;
  from_user_telegram_id: number;
  from_user_username: string | null;
  status: string;
  created_at: string;
}

const friends = ref<Friend[]>([]);
const requests = ref<FriendRequest[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const telegramUserId = ref<number | null>(null);
const activeTab = ref<'friends' | 'requests'>('friends');

const API_BASE = '/api';

const pendingCount = computed(() =>
  requests.value.filter(r => r.status === 'pending').length
);

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    pending: 'Ожидает',
    accepted: 'Принят',
    rejected: 'Отклонен',
  };
  return labels[status] || status;
};

const fetchFriends = async () => {
  if (!telegramUserId.value) return;

  try {
    const response = await fetch(`${API_BASE}/friends?telegram_id=${telegramUserId.value}`);
    if (!response.ok) throw new Error('Не удалось загрузить друзей');
    friends.value = await response.json();
  } catch (e: any) {
    console.error(e);
  }
};

const fetchRequests = async () => {
  if (!telegramUserId.value) return;

  try {
    const response = await fetch(`${API_BASE}/friends/requests?telegram_id=${telegramUserId.value}`);
    if (!response.ok) throw new Error('Не удалось загрузить запросы');
    requests.value = await response.json();
  } catch (e: any) {
    console.error(e);
  }
};

const respondToRequest = async (requestId: number, action: 'accept' | 'reject') => {
  if (!telegramUserId.value) return;

  try {
    const response = await fetch(
      `${API_BASE}/friends/requests/${requestId}/respond?telegram_id=${telegramUserId.value}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      }
    );

    if (!response.ok) throw new Error('Не удалось обработать запрос');

    // Refresh data
    await fetchFriends();
    await fetchRequests();
  } catch (e: any) {
    error.value = e.message;
  }
};

onMounted(async () => {
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

  if (!telegramUserId.value) {
    error.value = 'Не удалось получить ID пользователя';
    loading.value = false;
    return;
  }

  await Promise.all([fetchFriends(), fetchRequests()]);
  loading.value = false;
});
</script>

<style scoped>
.friends-container {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  padding: 16px;
  background-color: var(--tg-theme-bg-color, #1a1a2e);
  color: var(--tg-theme-text-color, #eaeaea);
  min-height: 100vh;
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.tab {
  flex: 1;
  padding: 12px 16px;
  border: none;
  border-radius: 8px;
  background: var(--tg-theme-secondary-bg-color, #2d2d44);
  color: var(--tg-theme-text-color, #eaeaea);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.tab.active {
  background: var(--tg-theme-button-color, #5288c1);
  color: var(--tg-theme-button-text-color, #fff);
}

.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #f44336;
  color: white;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
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

.friend-item,
.request-item {
  background: var(--tg-theme-secondary-bg-color, #2d2d44);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

.friend-name,
.request-from {
  font-size: 16px;
  font-weight: 500;
  color: var(--tg-theme-text-color, #eaeaea);
}

.request-status {
  font-size: 12px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 6px;
  display: inline-block;
  margin-top: 8px;
}

.request-status.pending {
  background-color: rgba(255, 193, 7, 0.2);
  color: #ffc107;
}

.request-status.rejected {
  background-color: rgba(244, 67, 54, 0.2);
  color: #f44336;
}

.request-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
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

.btn-accept {
  background: linear-gradient(135deg, #4caf50 0%, #388e3c 100%);
  color: white;
}

.btn-reject {
  background: linear-gradient(135deg, #f44336 0%, #c62828 100%);
  color: white;
}
</style>
