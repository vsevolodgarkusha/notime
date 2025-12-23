<template>
  <div class="friends-container">
    <header class="page-header">
      <h1 class="header-title">Друзья</h1>
    </header>

    <div class="tabs">
      <button
        :class="['tab', { active: activeTab === 'friends' }]"
        @click="activeTab = 'friends'"
      >
        <span class="tab-icon">👥</span>
        Друзья
      </button>
      <button
        :class="['tab', { active: activeTab === 'requests' }]"
        @click="activeTab = 'requests'"
      >
        <span class="tab-icon">📬</span>
        Запросы
        <span v-if="pendingCount > 0" class="badge">{{ pendingCount }}</span>
      </button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Загрузка...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <span class="error-icon">⚠️</span>
      <p>{{ error }}</p>
    </div>

    <template v-else>
      <!-- Friends Tab -->
      <div v-if="activeTab === 'friends'" class="section">
        <div v-if="friends.length === 0" class="empty-state">
          <div class="empty-icon">👋</div>
          <h3>Нет друзей</h3>
          <p>Добавьте друзей через команду /add_friend в боте</p>
        </div>

        <div v-for="friend in friends" :key="friend.id" class="friend-card">
          <div class="friend-avatar">
            {{ getInitials(friend.telegram_username || friend.telegram_id.toString()) }}
          </div>
          <div class="friend-info">
            <div class="friend-name">
              {{ friend.telegram_username ? '@' + friend.telegram_username : 'ID: ' + friend.telegram_id }}
            </div>
            <div class="friend-status">Друг</div>
          </div>
          <button @click="deleteFriend(friend.id)" class="btn-delete" title="Удалить друга">
            <span>✕</span>
          </button>
        </div>
      </div>

      <!-- Requests Tab -->
      <div v-if="activeTab === 'requests'" class="section">
        <div v-if="requests.length === 0" class="empty-state">
          <div class="empty-icon">📭</div>
          <h3>Нет запросов</h3>
          <p>Входящие запросы в друзья будут отображаться здесь</p>
        </div>

        <div v-for="request in requests" :key="request.id" class="request-card">
          <div class="friend-avatar request">
            {{ getInitials(request.from_user_username || request.from_user_telegram_id.toString()) }}
          </div>
          <div class="request-info">
            <div class="request-from">
              {{ request.from_user_username ? '@' + request.from_user_username : 'ID: ' + request.from_user_telegram_id }}
            </div>
            <div class="request-meta">
              <span class="request-status" :class="request.status">
                {{ statusLabel(request.status) }}
              </span>
            </div>
          </div>
          <div class="request-actions" v-if="request.status === 'pending' || request.status === 'rejected'">
            <button
              v-if="request.status === 'pending' || request.status === 'rejected'"
              @click="respondToRequest(request.id, 'accept')"
              class="btn-action accept"
              title="Принять"
            >
              <span>✓</span>
            </button>
            <button
              v-if="request.status === 'pending'"
              @click="respondToRequest(request.id, 'reject')"
              class="btn-action reject"
              title="Отклонить"
            >
              <span>✕</span>
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
const activeTab = ref<'friends' | 'requests'>('friends');

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

const pendingCount = computed(() =>
  requests.value.filter(r => r.status === 'pending').length
);

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    pending: 'Ожидает',
    accepted: 'Принят',
    rejected: 'Отклонён',
  };
  return labels[status] || status;
};

const getInitials = (name: string) => {
  if (name.startsWith('@')) name = name.slice(1);
  return name.slice(0, 2).toUpperCase();
};

const fetchFriends = async () => {
  try {
    const response = await fetch(`${API_BASE}/friends`, {
      headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Не удалось загрузить друзей');
    friends.value = await response.json();
  } catch (e: any) {
    console.error(e);
  }
};

const fetchRequests = async () => {
  try {
    const response = await fetch(`${API_BASE}/friends/requests`, {
      headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Не удалось загрузить запросы');
    requests.value = await response.json();
  } catch (e: any) {
    console.error(e);
  }
};

const respondToRequest = async (requestId: number, action: 'accept' | 'reject') => {
  try {
    const response = await fetch(
      `${API_BASE}/friends/requests/${requestId}/respond`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ action }),
      }
    );

    if (!response.ok) throw new Error('Не удалось обработать запрос');

    await fetchFriends();
    await fetchRequests();
  } catch (e: any) {
    error.value = e.message;
  }
};

const deleteFriend = async (friendshipId: number) => {
  try {
    const response = await fetch(
      `${API_BASE}/friends/${friendshipId}`,
      {
        method: 'DELETE',
        headers: getAuthHeaders()
      }
    );

    if (!response.ok) throw new Error('Не удалось удалить друга');

    await fetchFriends();
  } catch (e: any) {
    error.value = e.message;
  }
};

onMounted(async () => {
  if (window.Telegram?.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
  }

  await Promise.all([fetchFriends(), fetchRequests()]);
  loading.value = false;
});
</script>

<style scoped>
.friends-container {
  padding: 20px;
  min-height: 100vh;
}

.page-header {
  margin-bottom: 20px;
  padding: 0 4px;
}

.header-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 6px;
}

.tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
}

.tab:hover {
  color: var(--text-primary);
}

.tab.active {
  background: var(--accent);
  color: white;
  box-shadow: 0 4px 15px rgba(108, 92, 231, 0.3);
}

.tab-icon {
  font-size: 16px;
}

.badge {
  position: absolute;
  top: 4px;
  right: 8px;
  background: var(--danger);
  color: white;
  border-radius: 10px;
  min-width: 20px;
  height: 20px;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
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

.friend-card,
.request-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
  transition: all 0.3s ease;
}

.friend-card:hover,
.request-card:hover {
  border-color: rgba(255, 255, 255, 0.1);
  transform: translateY(-2px);
}

.friend-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent) 0%, #a29bfe 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}

.friend-avatar.request {
  background: linear-gradient(135deg, var(--warning) 0%, #ffc048 100%);
}

.friend-info,
.request-info {
  flex: 1;
  min-width: 0;
}

.friend-name,
.request-from {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.friend-status {
  font-size: 13px;
  color: var(--success);
  margin-top: 2px;
}

.request-meta {
  margin-top: 4px;
}

.request-status {
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 6px;
  display: inline-block;
}

.request-status.pending {
  background: rgba(255, 165, 2, 0.15);
  color: var(--warning);
}

.request-status.rejected {
  background: rgba(255, 71, 87, 0.15);
  color: var(--danger);
}

.btn-delete {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(255, 71, 87, 0.3);
  background: rgba(255, 71, 87, 0.1);
  color: var(--danger);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.btn-delete:hover {
  background: var(--danger);
  color: white;
  border-color: transparent;
  transform: scale(1.05);
}

.request-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.btn-action {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  transition: all 0.2s;
}

.btn-action.accept {
  background: var(--success);
  color: white;
}

.btn-action.reject {
  background: rgba(255, 71, 87, 0.15);
  color: var(--danger);
  border: 1px solid rgba(255, 71, 87, 0.3);
}

.btn-action:hover {
  transform: scale(1.05);
}

.btn-action.reject:hover {
  background: var(--danger);
  color: white;
  border-color: transparent;
}
</style>
