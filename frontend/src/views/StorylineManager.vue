<template>
  <div class="max-w-4xl mx-auto px-6 py-10">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-ink-900">故事线管理</h1>
      <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm">返回</router-link>
    </div>

    <!-- Storylines -->
    <section class="mb-8">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-medium text-ink-800">故事线</h2>
        <div class="flex gap-2">
          <button @click="aiGenerateStorylines" class="btn-secondary text-xs" :disabled="aiLoading">AI 生成</button>
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
          <button @click="aiGenerateArcs" class="btn-secondary text-xs" :disabled="aiLoading">AI 生成</button>
          <button @click="addArc" class="btn-primary text-xs">手动添加</button>
        </div>
      </div>
      <div v-if="arcs.length === 0" class="card p-4 text-center text-ink-400 text-sm">暂无人物弧光</div>
      <div v-for="arc in arcs" :key="arc.id" class="card p-4 mb-2">
        <div class="flex items-center justify-between">
          <div>
            <span class="badge bg-amber-50 text-amber-700 mr-2">{{ arc.arc_type }}</span>
            <span class="font-medium text-sm">角色#{{ arc.character_id }}</span>
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
          <button @click="aiGenerateScenes" class="btn-secondary text-xs" :disabled="aiLoading">AI 生成</button>
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
const aiLoading = ref(false)

async function load() {
  const [slRes, arcRes, scRes] = await Promise.all([
    fetch(`/api/v1/projects/${novelId}/storylines`),
    fetch(`/api/v1/projects/${novelId}/character-arcs`),
    fetch(`/api/v1/projects/${novelId}/scenes`),
  ])
  if (slRes.ok) storylines.value = await slRes.json()
  if (arcRes.ok) arcs.value = await arcRes.json()
  if (scRes.ok) scenes.value = await scRes.json()
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
  aiLoading.value = true
  await fetch(`/api/v1/projects/${novelId}/storylines/generate-ai`, { method: 'POST' })
  await load()
  aiLoading.value = false
}

async function aiGenerateArcs() {
  aiLoading.value = true
  await fetch(`/api/v1/projects/${novelId}/character-arcs/generate-ai`, { method: 'POST' })
  await load()
  aiLoading.value = false
}

async function aiGenerateScenes() {
  aiLoading.value = true
  await fetch(`/api/v1/projects/${novelId}/scenes/generate-ai`, { method: 'POST' })
  await load()
  aiLoading.value = false
}

onMounted(load)
</script>
