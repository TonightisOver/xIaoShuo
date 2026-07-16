import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/welcome', name: 'landing', component: () => import('../views/Landing.vue') },
  { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
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
  { path: '/novels/:id/knowledge-graph', name: 'knowledge-graph', component: () => import('../views/KnowledgeGraphView.vue') },
  { path: '/settings/llm', name: 'LLMSettings', component: () => import('../views/LLMSettings.vue') },
  { path: '/inspiration', name: 'inspiration', component: () => import('../views/Inspiration.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 暂时取消登录注册拦截：所有页面直接可进
// 恢复鉴权时改回：未带 token 且非 landing/login → 跳 login
router.beforeEach((to, from, next) => {
  next()
})

export default router


