import { createRouter, createWebHistory } from 'vue-router'
import TaskList from '../components/TaskList.vue'
import FriendsList from '../components/FriendsList.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/tasks',
    },
    {
      path: '/tasks',
      name: 'TaskList',
      component: TaskList,
    },
    {
      path: '/friends',
      name: 'FriendsList',
      component: FriendsList,
    },
  ],
})

export default router
