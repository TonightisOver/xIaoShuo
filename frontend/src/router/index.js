import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/Home.vue') },
  { path: '/create', name: 'create', component: () => import('../views/Create.vue') },
  { path: '/task/:id', name: 'task', component: () => import('../views/TaskDetail.vue') },
  { path: '/novels/:id', name: 'novel', component: () => import('../views/NovelDetail.vue') },
  { path: '/novels/:id/world', name: 'world', component: () => import('../views/WorldEdit.vue') },
  { path: '/novels/:id/characters', name: 'characters', component: () => import('../views/Characters.vue') },
  { path: '/novels/:id/chapters/:num', name: 'chapter-edit', component: () => import('../views/ChapterEdit.vue') },
  { path: '/novels/:id/conversations/:convId', name: 'conversation', component: () => import('../views/Conversation.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
