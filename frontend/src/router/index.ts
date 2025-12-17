import { createRouter, createWebHistory } from 'vue-router'
import TaskList from '../components/TaskList.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/tasks',
      name: 'TaskList',
      component: TaskList,
    },
  ],
})

export default router
