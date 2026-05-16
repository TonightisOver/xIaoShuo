<template>
  <div class="max-w-4xl mx-auto px-6 py-10">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-ink-900">大纲管理</h1>
      <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm">返回</router-link>
    </div>

    <!-- Master Outline -->
    <div class="card p-6 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-medium text-ink-800">总纲</h2>
        <div class="flex gap-2">
          <button @click="saveMaster" class="btn-primary text-xs" :disabled="savingMaster">保存</button>
          <button @click="generateVolumes" class="btn-secondary text-xs" :disabled="generatingVols">
            {{ generatingVols ? '生成中...' : '生成卷纲' }}
          </button>
        </div>
      </div>
      <div class="space-y-3">
        <div>
          <label class="text-xs text-ink-500">核心前提</label>
          <textarea v-model="master.premise" class="input text-sm mt-1 min-h-[60px]" placeholder="故事的核心设定和前提"></textarea>
        </div>
        <div>
          <label class="text-xs text-ink-500">主要冲突</label>
          <textarea v-model="master.main_conflict" class="input text-sm mt-1 min-h-[60px]" placeholder="推动故事发展的核心矛盾"></textarea>
        </div>
        <div>
          <label class="text-xs text-ink-500">结局走向</label>
          <textarea v-model="master.ending" class="input text-sm mt-1" placeholder="故事的结局方向"></textarea>
        </div>
        <div>
          <label class="text-xs text-ink-500">主题</label>
          <input v-model="master.themes_text" class="input text-sm mt-1" placeholder="用逗号分隔，如：成长,友情,正义" />
        </div>
      </div>
      <p v-if="masterSaved" class="text-xs text-emerald-600 mt-2">已保存</p>
    </div>

    <!-- Volume Outlines -->
    <div class="space-y-4">
      <h2 class="font-medium text-ink-800">卷纲</h2>
      <div v-if="volumes.length === 0" class="card p-6 text-center text-ink-400">
        暂无卷纲，请先编辑总纲后点击"生成卷纲"
      </div>
      <div v-for="vol in volumes" :key="vol.id" class="card p-5">
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-medium text-sm">卷{{ vol.volume_number }}：{{ vol.content?.title || '未命名' }}</h3>
          <button @click="generateChapters(vol.volume_number)" class="btn-secondary text-xs" :disabled="generatingChs === vol.volume_number">
            {{ generatingChs === vol.volume_number ? '生成中...' : '生成章纲' }}
          </button>
        </div>
        <p v-if="vol.content?.summary" class="text-sm text-ink-600 mb-2">{{ vol.content.summary }}</p>
        <p v-if="vol.content?.goal" class="text-xs text-ink-500">目标：{{ vol.content.goal }}</p>
        <p v-if="vol.content?.climax" class="text-xs text-ink-500">高潮：{{ vol.content.climax }}</p>

        <!-- Chapter outlines under this volume -->
        <div v-if="chaptersByVolume[vol.volume_number]" class="mt-3 ml-4 space-y-1 border-l-2 border-ink-200 pl-3">
          <div v-for="ch in chaptersByVolume[vol.volume_number]" :key="ch.id" class="text-xs text-ink-600">
            <span class="font-medium">第{{ ch.chapter_number }}章：{{ ch.content?.title || '' }}</span>
            <span v-if="ch.content?.turning_point" class="text-ink-400 ml-2">转折：{{ ch.content.turning_point }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const novelId = route.params.id

const master = ref({ premise: '', main_conflict: '', ending: '', themes_text: '' })
const volumes = ref([])
const chapters = ref([])
const savingMaster = ref(false)
const masterSaved = ref(false)
const generatingVols = ref(false)
const generatingChs = ref(null)

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
    }
    volumes.value = data.volumes || []
    chapters.value = data.unassigned_chapters || []
    // Also get chapter outlines
    const chRes = await fetch(`/api/v1/projects/${novelId}/outlines`)
    if (chRes.ok) {
      const chData = await chRes.json()
      // Flatten all chapter outlines from volumes
      const allChs = []
      for (const vol of chData.volumes || []) {
        for (const ch of vol.chapters || []) {
          allChs.push(ch)
        }
      }
      chapters.value = allChs
    }
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

onMounted(load)
</script>
