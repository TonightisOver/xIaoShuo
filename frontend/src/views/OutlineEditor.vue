<template>
  <div class="max-w-4xl mx-auto px-6 py-10">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-neutral-900">大纲管理</h1>
      <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm">返回</router-link>
    </div>

    <!-- Master Outline -->
    <div class="card p-6 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-medium text-neutral-800">总纲</h2>
        <div class="flex gap-2">
          <button @click="aiGenerateMaster" class="btn-secondary text-xs" :disabled="generatingMaster">
            {{ generatingMaster ? 'AI生成中...' : 'AI生成' }}
          </button>
          <button @click="saveMaster" class="btn-primary text-xs" :disabled="savingMaster">保存</button>
          <button @click="generateVolumes" class="btn-secondary text-xs" :disabled="generatingVols">
            {{ generatingVols ? '生成中...' : '生成卷纲' }}
          </button>
        </div>
      </div>
      <div class="space-y-3">
        <div>
          <label class="text-xs text-neutral-500">核心前提</label>
          <textarea v-model="master.premise" class="input text-sm mt-1 min-h-[60px]" placeholder="故事的核心设定和前提"></textarea>
        </div>
        <div>
          <label class="text-xs text-neutral-500">主要冲突</label>
          <textarea v-model="master.main_conflict" class="input text-sm mt-1 min-h-[60px]" placeholder="推动故事发展的核心矛盾"></textarea>
        </div>
        <div>
          <label class="text-xs text-neutral-500">结局走向</label>
          <textarea v-model="master.ending" class="input text-sm mt-1" placeholder="故事的结局方向"></textarea>
        </div>
        <div>
          <label class="text-xs text-neutral-500">主题</label>
          <input v-model="master.themes_text" class="input text-sm mt-1" placeholder="用逗号分隔，如：成长,友情,正义" />
        </div>
      </div>
      <p v-if="masterSaved" class="text-xs text-emerald-600 mt-2">已保存</p>
      <p v-if="analyzing" class="text-xs text-amber-600 mt-2">正在分析影响范围...</p>
    </div>

    <!-- Sync Suggestions Panel -->
    <div v-if="suggestions.length > 0" class="card p-5 mb-6 border-l-4 border-amber-400">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-medium text-neutral-800">同步建议 ({{ suggestions.length }})</h2>
        <div class="flex gap-2">
          <button @click="batchAction('accept')" class="btn-primary text-xs">全部接受</button>
          <button @click="batchAction('reject')" class="btn-secondary text-xs">全部忽略</button>
        </div>
      </div>
      <div class="space-y-2 max-h-60 overflow-y-auto">
        <div v-for="s in suggestions" :key="s.id" class="flex items-start gap-3 p-2 rounded bg-neutral-50">
          <span :class="severityClass(s.severity)" class="text-xs px-1.5 py-0.5 rounded font-medium shrink-0">
            {{ s.severity }}
          </span>
          <div class="flex-1 min-w-0">
            <p class="text-sm text-neutral-700">第{{ s.affected_chapter }}章 · {{ impactLabel(s.impact_type) }}</p>
            <p class="text-xs text-neutral-500 mt-0.5 truncate">{{ s.suggestion }}</p>
          </div>
          <div class="flex gap-1 shrink-0">
            <button @click="acceptOne(s.id)" class="text-emerald-600 hover:text-emerald-800 text-xs">接受</button>
            <button @click="rejectOne(s.id)" class="text-neutral-400 hover:text-neutral-600 text-xs">忽略</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Sync Status -->
    <div v-if="syncStatus.length > 0" class="card p-5 mb-6">
      <h2 class="font-medium text-neutral-800 mb-3">章节同步状态</h2>
      <div class="flex flex-wrap gap-2">
        <span v-for="st in syncStatus" :key="st.chapter_number"
          class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded"
          :class="syncStatusClass(st.outline_status)">
          <span class="w-1.5 h-1.5 rounded-full" :class="syncDotClass(st.outline_status)"></span>
          第{{ st.chapter_number }}章
        </span>
      </div>
    </div>

    <!-- Volume Outlines -->
    <div class="space-y-4">
      <h2 class="font-medium text-neutral-800">卷纲</h2>
      <div v-if="volumes.length === 0" class="card p-6 text-center text-neutral-400">
        暂无卷纲，请先编辑总纲后点击"生成卷纲"
      </div>
      <div v-for="vol in volumes" :key="vol.id" class="card p-5">
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-medium text-sm">卷{{ vol.volume_number }}：{{ vol.content?.title || '未命名' }}</h3>
          <div class="flex gap-2">
            <button @click="generateChapters(vol.volume_number)" class="btn-secondary text-xs" :disabled="generatingChs === vol.volume_number">
              {{ generatingChs === vol.volume_number ? '生成中...' : '生成章纲' }}
            </button>
            <button v-if="chaptersByVolume[vol.volume_number]" @click="generateVolumeContent(vol.volume_number)" class="btn-primary text-xs">
              生成本卷章节
            </button>
          </div>
        </div>
        <p v-if="vol.content?.summary" class="text-sm text-neutral-600 mb-2">{{ vol.content.summary }}</p>
        <p v-if="vol.content?.goal" class="text-xs text-neutral-500">目标：{{ vol.content.goal }}</p>
        <p v-if="vol.content?.climax" class="text-xs text-neutral-500">高潮：{{ vol.content.climax }}</p>

        <!-- Chapter outlines under this volume -->
        <div v-if="chaptersByVolume[vol.volume_number]" class="mt-3 ml-4 space-y-1 border-l-2 border-neutral-200 pl-3">
          <div v-for="ch in chaptersByVolume[vol.volume_number]" :key="ch.id" class="text-xs text-neutral-600">
            <span class="font-medium">第{{ ch.chapter_number }}章：{{ ch.content?.title || '' }}</span>
            <span v-if="ch.content?.turning_point" class="text-neutral-400 ml-2">转折：{{ ch.content.turning_point }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const novelId = route.params.id

const master = ref({ premise: '', main_conflict: '', ending: '', themes_text: '' })
const volumes = ref([])
const chapters = ref([])
const savingMaster = ref(false)
const masterSaved = ref(false)
const generatingVols = ref(false)
const generatingChs = ref(null)
const generatingMaster = ref(false)
const analyzing = ref(false)
const suggestions = ref([])
const syncStatus = ref([])
const previousMaster = ref(null)

const chaptersByVolume = computed(() => {
  const map = {}
  for (const ch of chapters.value) {
    const vn = ch.volume_number || 0
    if (!map[vn]) map[vn] = []
    map[vn].push(ch)
  }
  return map
})

async function load() {
  const res = await fetch(`/api/v1/projects/${novelId}/outlines`)
  if (res.ok) {
    const data = await res.json()
    if (data.master?.content) {
      const c = data.master.content
      master.value = {
        premise: c.premise || '',
        main_conflict: c.main_conflict || '',
        ending: c.ending || '',
        themes_text: (c.themes || []).join(', '),
      }
      previousMaster.value = { ...master.value }
    }
    volumes.value = data.volumes || []
    // Collect chapter outlines preserving volume_number
    const allChs = []
    for (const vol of data.volumes || []) {
      for (const ch of vol.chapters || []) {
        allChs.push({ ...ch, volume_number: vol.volume_number })
      }
    }
    chapters.value = allChs
  }
  await Promise.all([loadSyncStatus(), loadSuggestions()])
}

async function aiGenerateMaster() {
  generatingMaster.value = true
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/outlines/generate-master`, { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      const c = data.content || {}
      master.value = {
        premise: c.premise || '',
        main_conflict: c.main_conflict || '',
        ending: c.ending || '',
        themes_text: (c.themes || []).join(', '),
      }
      masterSaved.value = false
    }
  } finally {
    generatingMaster.value = false
  }
}

async function saveMaster() {
  savingMaster.value = true
  masterSaved.value = false
  const body = {
    premise: master.value.premise,
    main_conflict: master.value.main_conflict,
    ending: master.value.ending,
    themes: master.value.themes_text.split(',').map(t => t.trim()).filter(Boolean),
  }
  await fetch(`/api/v1/projects/${novelId}/outlines/master`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  savingMaster.value = false
  masterSaved.value = true
  setTimeout(() => { masterSaved.value = false }, 2000)

  if (previousMaster.value) {
    const oldC = previousMaster.value
    const newC = master.value
    const changed = oldC.premise !== newC.premise || oldC.main_conflict !== newC.main_conflict || oldC.ending !== newC.ending
    if (changed) {
      await analyzeImpact(
        { premise: oldC.premise, main_conflict: oldC.main_conflict, ending: oldC.ending },
        { premise: newC.premise, main_conflict: newC.main_conflict, ending: newC.ending }
      )
    }
  }
  previousMaster.value = { ...master.value }
}

async function generateVolumes() {
  generatingVols.value = true
  const res = await fetch(`/api/v1/projects/${novelId}/outlines/generate-volumes`, { method: 'POST' })
  if (res.ok) {
    await load()
  }
  generatingVols.value = false
}

async function generateChapters(volNum) {
  generatingChs.value = volNum
  const res = await fetch(`/api/v1/projects/${novelId}/outlines/generate-chapters/${volNum}`, { method: 'POST' })
  if (res.ok) {
    await load()
  }
  generatingChs.value = null
}

async function generateVolumeContent(volNum) {
  const res = await fetch(`/api/v1/projects/${novelId}/generate-volume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ volume_number: volNum }),
  })
  if (res.ok) {
    const data = await res.json()
    router.push(`/task/${data.task_id}`)
  }
}

async function loadSyncStatus() {
  const res = await fetch(`/api/v1/projects/${novelId}/outlines/sync/status`)
  if (res.ok) {
    const data = await res.json()
    syncStatus.value = data.chapters || []
  }
}

async function loadSuggestions() {
  const res = await fetch(`/api/v1/projects/${novelId}/outlines/sync/suggestions?status=pending`)
  if (res.ok) {
    const data = await res.json()
    suggestions.value = data.suggestions || []
  }
}

async function analyzeImpact(oldContent, newContent) {
  analyzing.value = true
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/outlines/sync/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: 'master', old_content: oldContent, new_content: newContent }),
    })
    if (res.ok) {
      await loadSuggestions()
    }
  } finally {
    analyzing.value = false
  }
}

async function acceptOne(id) {
  await fetch(`/api/v1/projects/${novelId}/outlines/sync/suggestions/${id}/accept`, { method: 'PUT' })
  suggestions.value = suggestions.value.filter(s => s.id !== id)
  await loadSyncStatus()
}

async function rejectOne(id) {
  await fetch(`/api/v1/projects/${novelId}/outlines/sync/suggestions/${id}/reject`, { method: 'PUT' })
  suggestions.value = suggestions.value.filter(s => s.id !== id)
}

async function batchAction(action) {
  const ids = suggestions.value.map(s => s.id)
  await fetch(`/api/v1/projects/${novelId}/outlines/sync/suggestions/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids, action }),
  })
  suggestions.value = []
  if (action === 'accept') await loadSyncStatus()
}

function severityClass(sev) {
  if (sev === 'high') return 'bg-red-100 text-red-700'
  if (sev === 'medium') return 'bg-amber-100 text-amber-700'
  return 'bg-blue-100 text-blue-700'
}

function impactLabel(type) {
  const map = { plot_conflict: '情节冲突', character_inconsistency: '人物矛盾', setting_contradiction: '设定矛盾', pacing_shift: '节奏偏移' }
  return map[type] || type
}

function syncStatusClass(status) {
  if (status === 'completed') return 'bg-emerald-50 text-emerald-700'
  if (status === 'deviated') return 'bg-red-50 text-red-700'
  return 'bg-neutral-50 text-neutral-600'
}

function syncDotClass(status) {
  if (status === 'completed') return 'bg-emerald-500'
  if (status === 'deviated') return 'bg-red-500'
  return 'bg-neutral-400'
}

onMounted(load)
</script>
