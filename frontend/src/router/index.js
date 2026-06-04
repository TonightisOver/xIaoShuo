import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/Home.vue') },
  { path: '/tasks', name: 'tasks', component: () => import('../views/TaskList.vue') },
  { path: '/create', name: 'create', component: () => import('../views/Create.vue') },
  { path: '/task/:id', name: 'task', component: () => import('../views/TaskDetail.vue') },
  { path: '/novels/:id', name: 'novel', component: () => import('../views/NovelDetail.vue') },
  { path: '/novels/:id/world', name: 'world', component: () => import('../views/WorldEdit.vue') },
  { path: '/novels/:id/characters', name: 'characters', component: () => import('../views/Characters.vue') },
  { path: '/novels/:id/careers', name: 'careers', component: () => import('../views/Careers.vue') },
  { path: '/novels/:id/chapters/:num', name: 'chapter-edit', component: () => import('../views/ChapterEdit.vue') },
  { path: '/novels/:id/conversations/:convId', name: 'conversation', component: () => import('../views/Conversation.vue') },
  { path: '/novels/:id/outlines', name: 'outlines', component: () => import('../views/OutlineEditor.vue') },
  { path: '/novels/:id/storylines', name: 'storylines', component: () => import('../views/StorylineManager.vue') },
  { path: '/novels/:id/graph', name: 'graph', component: () => import('../views/RelationGraph.vue') },
  { path: '/novels/:id/foreshadows', name: 'foreshadows', component: () => import('../views/ForeshadowTracker.vue') },
  { path: '/settings/llm', name: 'LLMSettings', component: () => import('../views/LLMSettings.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})

