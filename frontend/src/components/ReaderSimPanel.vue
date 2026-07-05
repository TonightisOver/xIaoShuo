<template>
  <div class="card p-5 mt-6">
    <div class="flex items-center justify-between mb-4">
      <h3 class="font-medium text-neutral-800 text-sm">读者视角模拟</h3>
      <button @click="startSimulation" class="btn-primary text-xs" :disabled="simulating">
        {{ simulating ? '模拟中...' : '开始模拟' }}
      </button>
    </div>

    <!-- Persona Selection -->
    <div class="flex flex-wrap gap-2 mb-4">
      <label v-for="p in personas" :key="p.id"
        class="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border cursor-pointer transition-all"
        :class="selectedPersonas.includes(p.id) ? 'border-accent-300 bg-accent-50 text-accent-700' : 'border-neutral-200 text-neutral-600 hover:bg-neutral-50'">
        <input type="checkbox" :value="p.id" v-model="selectedPersonas" class="sr-only" />
        <span class="w-2 h-2 rounded-full" :class="personaDot(p.id)"></span>
        {{ p.name }}
      </label>
    </div>

    <!-- Loading -->
    <div v-if="simulating" class="text-center py-8">
      <div class="inline-block w-6 h-6 border-2 border-accent-300 border-t-accent-600 rounded-full animate-spin"></div>
      <p class="text-xs text-neutral-500 mt-2">正在模拟读者反馈，请稍候...</p>
    </div>

    <!-- Results -->
    <div v-if="currentResults.length > 0" class="space-y-3">
      <div v-for="r in currentResults" :key="r.persona_id"
        class="border border-neutral-200 rounded-lg p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="font-medium text-sm text-neutral-800">{{ r.persona_name }}</span>
          <span v-if="r.engagement_score != null"
            class="text-xs font-bold px-2 py-0.5 rounded-full"
            :class="scoreClass(r.engagement_score)">
            {{ (r.engagement_score * 100).toFixed(0) }}分
          </span>
          <span v-else-if="r.error" class="text-xs text-red-500">失败</span>
        </div>

        <template v-if="!r.error">
          <!-- Tags row -->
          <div class="flex flex-wrap gap-1.5 mb-2">
            <span class="tag" :class="pacingClass(r.pacing_assessment)">
              {{ pacingLabel(r.pacing_assessment) }}
            </span>
            <span class="tag" :class="charClass(r.character_consistency)">
              {{ charLabel(r.character_consistency) }}
            </span>
            <span v-if="r.would_continue_reading" class="tag bg-emerald-50 text-emerald-700">想追更</span>
            <span v-else class="tag bg-red-50 text-red-700">可能弃书</span>
          </div>

          <!-- Satisfaction / Pain points -->
          <div v-if="r.satisfaction_points?.length" class="mb-1.5">
            <span class="text-[11px] text-neutral-500">亮点：</span>
            <span v-for="(s, i) in r.satisfaction_points" :key="i" class="text-xs text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded mr-1">{{ s }}</span>
          </div>
          <div v-if="r.pain_points?.length" class="mb-2">
            <span class="text-[11px] text-neutral-500">不足：</span>
            <span v-for="(s, i) in r.pain_points" :key="i" class="text-xs text-red-700 bg-red-50 px-1.5 py-0.5 rounded mr-1">{{ s }}</span>
          </div>

          <!-- Overall comment -->
          <p class="text-xs text-neutral-600 italic border-l-2 border-neutral-200 pl-2 mt-2">
            "{{ r.overall_comment }}"
          </p>
        </template>
        <p v-else class="text-xs text-red-500">{{ r.error }}</p>
      </div>
    </div>

    <!-- History -->
    <div v-if="history.length > 0" class="mt-4 border-t border-neutral-200 pt-3">
      <button @click="showHistory = !showHistory" class="text-xs text-neutral-500 hover:text-neutral-700 font-medium">
        {{ showHistory ? '收起历史' : `查看历史 (${history.length})` }}
      </button>
      <div v-if="showHistory" class="mt-2 space-y-1">
        <div v-for="h in history" :key="h.id" @click="loadSimulation(h.id)"
          class="text-xs text-neutral-600 px-2 py-1.5 rounded hover:bg-neutral-50 cursor-pointer flex justify-between">
          <span>{{ h.personas_used?.length || 0 }}个视角 · {{ h.duration_ms ? (h.duration_ms / 1000).toFixed(1) + 's' : '...' }}</span>
          <span class="text-neutral-400">{{ formatTime(h.created_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  novelId: { type: String, required: true },
  chapterNumber: { type: Number, required: true },
})

const personas = [
  { id: 'hardcore_fan', name: '核心粉丝' },
  { id: 'casual_reader', name: '路人读者' },
  { id: 'critic', name: '专业评论家' },
  { id: 'veteran_reader', name: '网文老白' },
]

const selectedPersonas = ref(personas.map(p => p.id))
const simulating = ref(false)
const currentResults = ref([])
const history = ref([])
const showHistory = ref(false)

async function startSimulation() {
  simulating.value = true
  currentResults.value = []
  try {
    const res = await fetch(`/api/v1/projects/${props.novelId}/chapters/${props.chapterNumber}/reader-simulation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ personas: selectedPersonas.value }),
    })
    if (!res.ok) { simulating.value = false; return }
    const data = await res.json()
    await pollResult(data.simulation_id)
  } catch {
    simulating.value = false
  }
}

async function pollResult(simId) {
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 2000))
    const res = await fetch(`/api/v1/projects/${props.novelId}/reader-simulations/${simId}`)
    if (!res.ok) continue
    const data = await res.json()
    if (data.status === 'completed' || data.status === 'failed') {
      currentResults.value = data.results || []
      simulating.value = false
      await loadHistory()
      return
    }
  }
  simulating.value = false
}

async function loadHistory() {
  const res = await fetch(`/api/v1/projects/${props.novelId}/chapters/${props.chapterNumber}/reader-simulations`)
  if (res.ok) {
    const data = await res.json()
    history.value = data.simulations || []
  }
}

async function loadSimulation(simId) {
  const res = await fetch(`/api/v1/projects/${props.novelId}/reader-simulations/${simId}`)
  if (res.ok) {
    const data = await res.json()
    currentResults.value = data.results || []
  }
}

function personaDot(id) {
  const map = { hardcore_fan: 'bg-purple-500', casual_reader: 'bg-blue-500', critic: 'bg-amber-500', veteran_reader: 'bg-emerald-500' }
  return map[id] || 'bg-neutral-400'
}

function scoreClass(score) {
  if (score >= 0.7) return 'bg-emerald-100 text-emerald-700'
  if (score >= 0.4) return 'bg-amber-100 text-amber-700'
  return 'bg-red-100 text-red-700'
}

function pacingClass(p) {
  if (p === 'good') return 'bg-emerald-50 text-emerald-700'
  if (p === 'too_slow') return 'bg-amber-50 text-amber-700'
  return 'bg-blue-50 text-blue-700'
}

function pacingLabel(p) {
  const map = { good: '节奏适中', too_slow: '节奏偏慢', too_fast: '节奏偏快' }
  return map[p] || p
}

function charClass(c) {
  if (c === 'consistent') return 'bg-emerald-50 text-emerald-700'
  if (c === 'minor_issues') return 'bg-amber-50 text-amber-700'
  return 'bg-red-50 text-red-700'
}

function charLabel(c) {
  const map = { consistent: '人物一致', minor_issues: '轻微违和', ooc: '人物OOC' }
  return map[c] || c
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(loadHistory)
</script>

<style scoped>
.tag {
  @apply text-[11px] px-1.5 py-0.5 rounded font-medium;
}
</style>
