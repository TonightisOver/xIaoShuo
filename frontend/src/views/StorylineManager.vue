<template>
  <div class="max-w-4xl mx-auto px-6 py-10">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-ink-900">故事线管理</h1>
      <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm">返回</router-link>
    </div>

    <!-- Error banner -->
    <div v-if="aiError" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex justify-between">
      <span>{{ aiError }}</span>
      <button @click="aiError = ''" class="text-red-400 hover:text-red-600 ml-2">✕</button>
    </div>

    <!-- AI Preview Panel: Storylines -->
    <div v-if="pendingStorylines.length" class="card p-5 mb-6 border-2 border-primary-200">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-medium text-ink-800">AI 生成预览 — 故事线（可修改后确认）</h3>
        <div class="flex gap-2">
          <button @click="confirmStorylines" class="btn-primary text-xs" :disabled="confirmingStorylines">{{ confirmingStorylines ? '保存中...' : '确认保存' }}</button>
          <button @click="pendingStorylines = []" class="btn-secondary text-xs">取消</button>
        </div>
      </div>
      <div v-for="(sl, i) in pendingStorylines" :key="i" class="mb-3 p-3 bg-ink-50 rounded-lg space-y-2">
        <div class="flex gap-2">
          <input v-model="sl.name" class="input text-sm flex-1" placeholder="故事线名称" />
          <select v-model="sl.type" class="input text-sm w-28">
            <option value="main">主线</option>
            <option value="sub">副线</option>
            <option value="hidden">暗线</option>
          </select>
          <button @click="pendingStorylines.splice(i, 1)" class="text-red-400 hover:text-red-600 text-xs px-2">删除</button>
        </div>
        <textarea v-model="sl.description" class="input text-xs w-full min-h-[50px] resize-y" placeholder="描述"></textarea>
      </div>
    </div>

    <!-- AI Preview Panel: Arcs -->
    <div v-if="pendingArcs.length" class="card p-5 mb-6 border-2 border-amber-200">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-medium text-ink-800">AI 生成预览 — 人物弧光（可修改后确认）</h3>
        <div class="flex gap-2">
          <button @click="confirmArcs" class="btn-primary text-xs" :disabled="confirmingArcs">{{ confirmingArcs ? '保存中...' : '确认保存' }}</button>
          <button @click="pendingArcs = []" class="btn-secondary text-xs">取消</button>
        </div>
      </div>
      <div v-for="(arc, i) in pendingArcs" :key="i" class="mb-3 p-3 bg-ink-50 rounded-lg space-y-2">
        <div class="flex gap-2 items-center">
          <span class="text-xs text-ink-500 shrink-0">人物：</span>
          <select v-model="arc.character_id" class="input text-sm w-40">
            <option v-for="c in characters" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <select v-model="arc.arc_type" class="input text-sm w-32">
            <option value="growth">成长</option>
            <option value="fall">堕落</option>
            <option value="transformation">蜕变</option>
            <option value="flat">平稳</option>
          </select>
          <button @click="pendingArcs.splice(i, 1)" class="text-red-400 hover:text-red-600 text-xs px-2">删除</button>
        </div>
        <textarea v-model="arc.description" class="input text-xs w-full min-h-[50px] resize-y" placeholder="弧光描述"></textarea>
      </div>
    </div>

    <!-- AI Preview Panel: Scenes -->
    <div v-if="pendingScenes.length" class="card p-5 mb-6 border-2 border-emerald-200">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-medium text-ink-800">AI 生成预览 — 场景（可修改后确认）</h3>
        <div class="flex gap-2">
          <button @click="confirmScenes" class="btn-primary text-xs" :disabled="confirmingScenes">{{ confirmingScenes ? '保存中...' : '确认保存' }}</button>
          <button @click="pendingScenes = []" class="btn-secondary text-xs">取消</button>
        </div>
      </div>
      <div v-for="(sc, i) in pendingScenes" :key="i" class="mb-3 p-3 bg-ink-50 rounded-lg space-y-2">
        <div class="flex gap-2">
          <input v-model="sc.name" class="input text-sm flex-1" placeholder="场景名称" />
          <input v-model="sc.location" class="input text-sm w-40" placeholder="地理位置" />
          <button @click="pendingScenes.splice(i, 1)" class="text-red-400 hover:text-red-600 text-xs px-2">删除</button>
        </div>
        <textarea v-model="sc.description" class="input text-xs w-full min-h-[50px] resize-y" placeholder="描述"></textarea>
      </div>
    </div>

    <!-- Storylines -->
    <section class="mb-8">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-medium text-ink-800">故事线</h2>
        <div class="flex gap-2">
          <button @click="aiGenerateStorylines" class="btn-secondary text-xs" :disabled="aiLoading === 'storylines'">
            {{ aiLoading === 'storylines' ? 'AI生成中...' : 'AI 生成' }}
          </button>
          <button @click="addStoryline" class="btn-primary text-xs">手动添加</button>
        </div>
      </div>
      <div v-if="storylines.length === 0" class="card p-4 text-center text-ink-400 text-sm">暂无故事线</div>
      <div v-for="sl in storylines" :key="sl.id" class="card p-4 mb-2">
        <div class="flex items-center justify-between">
          <div>
            <span class="badge bg-primary-50 text-primary-700 mr-2">{{ sl.type }}</span>
            <span class="font-medium text-sm">{{ sl.name }}</span>
            <span class="badge ml-2" :class="sl.status === 'active' ? 'badge-running' : 'badge-completed'">{{ sl.status }}</span>
          </div>
          <button @click="deleteStoryline(sl.id)" class="text-red-400 hover:text-red-600 text-xs">删除</button>
        </div>
        <p v-if="sl.description" class="text-xs text-ink-500 mt-1">{{ sl.description }}</p>
      </div>
    </section>

    <!-- Character Arcs -->
    <section class="mb-8">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-medium text-ink-800">人物弧光</h2>
        <div class="flex gap-2">
          <button @click="aiGenerateArcs" class="btn-secondary text-xs" :disabled="aiLoading === 'arcs'">
            {{ aiLoading === 'arcs' ? 'AI生成中...' : 'AI 生成' }}
          </button>
          <button @click="addArc" class="btn-primary text-xs">手动添加</button>
        </div>
      </div>
      <div v-if="arcs.length === 0" class="card p-4 text-center text-ink-400 text-sm">暂无人物弧光</div>
      <div v-for="arc in arcs" :key="arc.id" class="card p-4 mb-2">
        <div class="flex items-center justify-between">
          <div>
            <span class="badge bg-amber-50 text-amber-700 mr-2">{{ arc.arc_type }}</span>
            <span class="font-medium text-sm">{{ charName(arc.character_id) }}</span>
          </div>
          <button @click="deleteArc(arc.id)" class="text-red-400 hover:text-red-600 text-xs">删除</button>
        </div>
        <p v-if="arc.description" class="text-xs text-ink-500 mt-1">{{ arc.description }}</p>
      </div>
    </section>

    <!-- Scenes -->
    <section>
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-medium text-ink-800">场景</h2>
        <div class="flex gap-2">
          <button @click="aiGenerateScenes" class="btn-secondary text-xs" :disabled="aiLoading === 'scenes'">
            {{ aiLoading === 'scenes' ? 'AI生成中...' : 'AI 生成' }}
          </button>
          <button @click="addScene" class="btn-primary text-xs">手动添加</button>
        </div>
      </div>
      <div v-if="scenes.length === 0" class="card p-4 text-center text-ink-400 text-sm">暂无场景</div>
      <div v-for="scene in scenes" :key="scene.id" class="card p-4 mb-2">
        <div class="flex items-center justify-between">
          <div>
            <span class="font-medium text-sm">{{ scene.name }}</span>
            <span v-if="scene.location" class="text-xs text-ink-400 ml-2">{{ scene.location }}</span>
          </div>
          <button @click="deleteScene(scene.id)" class="text-red-400 hover:text-red-600 text-xs">删除</button>
        </div>
        <p v-if="scene.description" class="text-xs text-ink-500 mt-1">{{ scene.description }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const novelId = route.params.id

const storylines = ref([])
const arcs = ref([])
const scenes = ref([])
const characters = ref([])
const aiLoading = ref('')
const aiError = ref('')

const pendingStorylines = ref([])
const pendingArcs = ref([])
const pendingScenes = ref([])
const confirmingStorylines = ref(false)
const confirmingArcs = ref(false)
const confirmingScenes = ref(false)

function charName(id) {
  const c = characters.value.find(c => c.id === id)
  return c ? c.name : `角色#${id}`
}

async function load() {
  const [slRes, arcRes, scRes, charRes] = await Promise.all([
    fetch(`/api/v1/projects/${novelId}/storylines`),
    fetch(`/api/v1/projects/${novelId}/character-arcs`),
    fetch(`/api/v1/projects/${novelId}/scenes`),
    fetch(`/api/v1/projects/${novelId}/characters`),
  ])
  if (slRes.ok) storylines.value = await slRes.json()
  if (arcRes.ok) arcs.value = await arcRes.json()
  if (scRes.ok) scenes.value = await scRes.json()
  if (charRes.ok) characters.value = await charRes.json()
}

async function addStoryline() {
  const name = prompt('故事线名称')
  if (!name) return
  const type = prompt('类型 (main/sub/hidden)', 'main')
  await fetch(`/api/v1/projects/${novelId}/storylines`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, type: type || 'main', description: '' }),
  })
  await load()
}

async function deleteStoryline(id) {
  await fetch(`/api/v1/projects/${novelId}/storylines/${id}`, { method: 'DELETE' })
  await load()
}

async function addArc() {
  const charId = prompt('人物 ID')
  if (!charId) return
  const arcType = prompt('弧光类型 (growth/fall/flat/transformation)', 'growth')
  const desc = prompt('描述')
  await fetch(`/api/v1/projects/${novelId}/character-arcs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ character_id: parseInt(charId), arc_type: arcType || 'growth', description: desc || '' }),
  })
  await load()
}

async function deleteArc(id) {
  await fetch(`/api/v1/projects/${novelId}/character-arcs/${id}`, { method: 'DELETE' })
  await load()
}

async function addScene() {
  const name = prompt('场景名称')
  if (!name) return
  const location = prompt('地理位置')
  await fetch(`/api/v1/projects/${novelId}/scenes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, location: location || '', description: '' }),
  })
  await load()
}

async function deleteScene(id) {
  await fetch(`/api/v1/projects/${novelId}/scenes/${id}`, { method: 'DELETE' })
  await load()
}

async function aiGenerateStorylines() {
  aiLoading.value = 'storylines'
  aiError.value = ''
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/storylines/generate-ai`, { method: 'POST' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      aiError.value = data.detail || 'AI生成失败'
      return
    }
    const data = await res.json()
    const items = data.storylines || []
    if (items.length === 0) {
      aiError.value = 'AI未生成任何故事线，请先完善小说设定'
      return
    }
    // Items are already saved; show for review/edit
    pendingStorylines.value = items.map(sl => ({ id: sl.id, name: sl.name || '', type: sl.type || 'main', description: sl.description || '', key_events: sl.key_events || [] }))
    await load()
  } finally {
    aiLoading.value = ''
  }
}

async function confirmStorylines() {
  confirmingStorylines.value = true
  try {
    for (const sl of pendingStorylines.value) {
      if (!sl.id || !sl.name) continue
      await fetch(`/api/v1/projects/${novelId}/storylines/${sl.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: sl.name, type: sl.type, description: sl.description, key_events: sl.key_events, status: 'active' }),
      })
    }
    pendingStorylines.value = []
    await load()
  } finally {
    confirmingStorylines.value = false
  }
}

async function aiGenerateArcs() {
  aiLoading.value = 'arcs'
  aiError.value = ''
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/character-arcs/generate-ai`, { method: 'POST' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      aiError.value = data.detail || 'AI生成失败'
      return
    }
    const data = await res.json()
    const items = data.arcs || []
    if (items.length === 0) {
      aiError.value = 'AI未生成任何人物弧光，请先添加人物'
      return
    }
    pendingArcs.value = items.map(arc => ({
      id: arc.id,
      character_id: arc.character_id,
      arc_type: arc.arc_type || 'growth',
      description: arc.description || '',
      stages: arc.stages || [],
    }))
    await load()
  } finally {
    aiLoading.value = ''
  }
}

async function confirmArcs() {
  confirmingArcs.value = true
  try {
    for (const arc of pendingArcs.value) {
      if (!arc.id || !arc.character_id) continue
      await fetch(`/api/v1/projects/${novelId}/character-arcs/${arc.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ character_id: arc.character_id, arc_type: arc.arc_type, description: arc.description, stages: arc.stages }),
      })
    }
    pendingArcs.value = []
    await load()
  } finally {
    confirmingArcs.value = false
  }
}

async function aiGenerateScenes() {
  aiLoading.value = 'scenes'
  aiError.value = ''
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/scenes/generate-ai`, { method: 'POST' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      aiError.value = data.detail || 'AI生成失败'
      return
    }
    const data = await res.json()
    const items = data.scenes || []
    if (items.length === 0) {
      aiError.value = 'AI未生成任何场景，请先完善世界观设定'
      return
    }
    pendingScenes.value = items.map(sc => ({ id: sc.id, name: sc.name || '', location: sc.location || '', description: sc.description || '', appearances: sc.appearances || [] }))
    await load()
  } finally {
    aiLoading.value = ''
  }
}

async function confirmScenes() {
  confirmingScenes.value = true
  try {
    for (const sc of pendingScenes.value) {
      if (!sc.id || !sc.name) continue
      await fetch(`/api/v1/projects/${novelId}/scenes/${sc.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: sc.name, location: sc.location, description: sc.description, appearances: sc.appearances }),
      })
    }
    pendingScenes.value = []
    await load()
  } finally {
    confirmingScenes.value = false
  }
}

onMounted(load)
</script>
