<template>
  <div>
    <h1>Task List</h1>
    <p v-if="loading">Loading tasks...</p>
    <p v-else-if="error">{{ error }}</p>
    <ul v-else-if="tasks.length">
      <li v-for="task in tasks" :key="task.id">
        {{ task.title }} - {{ task.completed ? 'Completed' : 'Pending' }}
      </li>
    </ul>
    <p v-else>No tasks found.</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface Task {
  id: number
  title: string
  completed: boolean
}

const tasks = ref<Task[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const fetchTasks = async () => {
  try {
    const response = await fetch('/api/tasks') // Assuming a backend API endpoint
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    tasks.value = await response.json()
  } catch (e: any) {
    error.value = 'Failed to fetch tasks: ' + e.message
  } finally {
    loading.value = false
  }
}

onMounted(fetchTasks)
</script>

<style scoped>
/* Add some basic styling if needed */
ul {
  list-style-type: none;
  padding: 0;
}

li {
  background-color: #f0f0f0;
  margin: 5px 0;
  padding: 10px;
  border-radius: 5px;
}
</style>
