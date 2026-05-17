<template>
  <div class="max-w-5xl mx-auto px-6 py-10">
    <div v-if="loading" class="text-center py-20 text-ink-500">加载中...</div>
    <div v-else-if="!novel" class="text-center py-20">
      <p class="text-ink-400 text-lg mb-4">小说不存在</p>
      <router-link to="/" class="btn-secondary">返回书架</router-link>
    </div>

    <template v-else>
      <div class="flex items-start justify-between mb-6">
        <div>
          <h1 class="text-2xl font-bold text-ink-900">{{ novel.title }}</h1>
          <p class="text-ink-500 text-sm mt-1">{{ novel.novel_type }} · {{ (novel.target_words / 10000).toFixed(0) }}万字</p>
        </div>
        <div class="flex gap-2">
          <button v-if="novel.status === 'draft' || novel.status === 'completed' || novel.status === 'failed'" @click="generate" class="btn-primary text-sm" :disabled="generating">
            {{ generating ? '启动中...' : (novel.status === 'draft' ? '开始生成' : '重新生成') }}
          </button>
          <router-link to="/" class="btn-secondary text-sm">返回</router-link>
        </div>
      </div>

      <!-- Tabs -->
      <div class="border-b border-ink-200 mb-6">
        <nav class="flex gap-6">
          <button v-for="tab in tabs" :key="tab.id"
            :class="['pb-3 text-sm font-medium border-b-2 transition-colors', activeTab === tab.id ? 'border-primary-600 text-primary-700' : 'border-transparent text-ink-500 hover:text-ink-700']"
            @click="activeTab = tab.id"
          >{{ tab.label }}</button>
        </nav>
      </div>

      <!-- Tab Content -->
      <div v-if="activeTab === 'overview'" class="card p-6">
        <dl class="grid grid-cols-2 gap-4 text-sm">
          <div><dt class="text-ink-500">状态</dt><dd class="font-medium mt-1">{{ statusLabel }}</dd></div>
          <div><dt class="text-ink-500">类型</dt><dd class="font-medium mt-1">{{ novel.novel_type }}</dd></div>
          <div class="col-span-2"><dt class="text-ink-500">创意</dt><dd class="mt-1">{{ novel.idea }}</dd></div>
          <div><dt class="text-ink-500">人物数</dt><dd class="font-medium mt-1">{{ novel.characters_count }}</dd></div>
          <div><dt class="text-ink-500">世界观</dt><dd class="font-medium mt-1">{{ novel.world_setting ? '已设定' : '未设定' }}</dd></div>
        </dl>
      </div>

      <div v-if="activeTab === 'outlines'" class="card p-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="font-medium text-ink-800">大纲体系</h2>
          <router-link :to="`/novels/${novelId}/outlines`" class="btn-primary text-sm">编辑大纲</router-link>
        </div>
        <p class="text-sm text-ink-500">在大纲编辑器中管理总纲、卷纲、章纲三级结构。</p>
      </div>

      <div v-if="activeTab === 'world'" class="card p-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="font-medium text-ink-800">世界观设定</h2>
          <router-link :to="`/novels/${novelId}/world`" class="btn-secondary text-sm">编辑</router-link>
        </div>
        <div v-if="world" class="space-y-4 text-sm">
          <div v-if="world.background"><h3 class="text-ink-500 text-xs uppercase">世界背景</h3><p class="mt-1 whitespace-pre-wrap">{{ world.background }}</p></div>
          <div v-if="world.geography"><h3 class="text-ink-500 text-xs uppercase">地理环境</h3><p class="mt-1 whitespace-pre-wrap">{{ world.geography }}</p></div>
          <div v-if="world.culture"><h3 class="text-ink-500 text-xs uppercase">文化体系</h3><p class="mt-1 whitespace-pre-wrap">{{ world.culture }}</p></div>
          <div v-if="world.rules"><h3 class="text-ink-500 text-xs uppercase">世界规则</h3><p class="mt-1 whitespace-pre-wrap">{{ world.rules }}</p></div>
          <p v-if="!world.background && !world.rules" class="text-ink-400">暂无世界观设定</p>
        </div>
      </div>

      <div v-if="activeTab === 'characters'" class="space-y-3">
        <div class="flex justify-between items-center">
          <h2 class="font-medium text-ink-800">人物列表</h2>
          <router-link :to="`/novels/${novelId}/characters`" class="btn-secondary text-sm">管理人物</router-link>
        </div>
        <div v-if="characters.length === 0" class="card p-6 text-center text-ink-400">暂无人物</div>
        <div v-for="char in characters" :key="char.id" class="card p-4">
          <div class="flex items-center gap-2 mb-1">
            <span class="font-medium">{{ char.name }}</span>
            <span v-if="char.role" class="badge bg-ink-100 text-ink-600">{{ char.role }}</span>
          </div>
          <p v-if="char.description" class="text-sm text-ink-600">{{ char.description }}</p>
        </div>
      </div>

      <div v-if="activeTab === 'chapters'" class="space-y-4">
        <div class="flex justify-between items-center">
          <h2 class="font-medium text-ink-800">章节与卷</h2>
          <button @click="showRangeDialog = true" class="btn-secondary text-sm">按范围生成</button>
        </div>

        <!-- Volume List -->
        <VolumeList
          v-if="volumes.length"
          :volumes="volumes"
          :chapters="chapters"
          :novel-id="novelId"
          @generate-volume="handleGenerateVolume"
        />

        <!-- Chapters without volume (legacy) -->
        <div v-if="unassignedChapters.length" class="space-y-1">
          <h3 v-if="volumes.length" class="text-sm text-ink-500 mt-4">未分卷章节</h3>
          <router-link v-for="ch in unassignedChapters" :key="ch.id"
            :to="`/novels/${novelId}/chapters/${ch.chapter_number}`"
            class="card p-3 block hover:bg-ink-50 transition-colors"
          >
            <div class="flex justify-between items-center">
              <span class="font-medium text-sm">第{{ ch.chapter_number }}章：{{ ch.title }}</span>
              <span class="text-xs text-ink-400">{{ ch.word_count }} 字</span>
            </div>
          </router-link>
        </div>

        <div v-if="!volumes.length && !chapters.length" class="card p-6 text-center text-ink-400">
          暂无章节，请先生成小说
        </div>

        <ChapterRangeDialog
          :visible="showRangeDialog"
          @close="showRangeDialog = false"
          @generate="handleGenerateChapters"
        />
      </div>

      <div v-if="activeTab === 'storylines'" class="card p-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="font-medium text-ink-800">故事线 / 人物弧光 / 场景</h2>
          <div class="flex gap-2">
            <router-link :to="`/novels/${novelId}/graph`" class="btn-secondary text-sm">查看图谱</router-link>
            <router-link :to="`/novels/${novelId}/storylines`" class="btn-primary text-sm">管理故事线</router-link>
          </div>
        </div>
        <p class="text-sm text-ink-500">在故事线管理器中创建和编辑故事线、人物弧光、场景，以及它们之间的关联关系。</p>
      </div>

      <div v-if="activeTab === 'conversations'" class="space-y-3">
        <div class="flex justify-between items-center">
          <h2 class="font-medium text-ink-800">创作对话</h2>
          <button @click="startConversation" class="btn-primary text-sm">新建对话</button>
        </div>
        <div v-if="conversations.length === 0" class="card p-6 text-center text-ink-400">暂无对话，开始一次创作讨论吧</div>
        <router-link v-for="conv in conversations" :key="conv.id"
          :to="`/novels/${novelId}/conversations/${conv.id}`"
          class="card p-4 block hover:bg-ink-50 transition-colors"
        >
          <div class="flex justify-between items-center">
            <span class="font-medium text-sm">{{ conv.topic }}</span>
            <span :class="conv.status === 'active' ? 'badge-running' : 'badge-completed'">
              {{ conv.status === 'active' ? '进行中' : '已结束' }}
            </span>
          </div>
        </router-link>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VolumeList from '../components/VolumeList.vue'
import ChapterRangeDialog from '../components/ChapterRangeDialog.vue'

const route = useRoute()
const router = useRouter()
const novelId = route.params.id

const novel = ref(null)
const world = ref(null)
const characters = ref([])
const chapters = ref([])
const volumes = ref([])
const conversations = ref([])
const loading = ref(true)
const generating = ref(false)
const activeTab = ref('overview')
const showRangeDialog = ref(false)

const unassignedChapters = computed(() =>
  chapters.value.filter(c => !c.volume_number)
)

const tabs = [
  { id: 'overview', label: '概览' },
  { id: 'outlines', label: '大纲' },
  { id: 'world', label: '世界观' },
  { id: 'characters', label: '人物' },
  { id: 'chapters', label: '章节' },
  { id: 'storylines', label: '故事线' },
  { id: 'conversations', label: '创作对话' },
]

const statusLabel = computed(() => {
  const map = { draft: '草稿', generating: '生成中', completed: '已完成', failed: '失败' }
  return map[novel.value?.status] || novel.value?.status
})

async function fetchAll() {
  loading.value = true
  try {
    const [nRes, wRes, cRes, chRes, convRes, volRes] = await Promise.all([
      fetch(`/api/v1/projects/${novelId}`),
      fetch(`/api/v1/projects/${novelId}/world`),
      fetch(`/api/v1/projects/${novelId}/characters`),
      fetch(`/api/v1/projects/${novelId}/chapters`),
      fetch(`/api/v1/projects/${novelId}/conversations`),
      fetch(`/api/v1/projects/${novelId}/volumes`),
    ])
    if (nRes.ok) novel.value = await nRes.json()
    if (wRes.ok) world.value = await wRes.json()
    if (cRes.ok) characters.value = await cRes.json()
    if (chRes.ok) chapters.value = await chRes.json()
    if (convRes.ok) conversations.value = await convRes.json()
    if (volRes.ok) volumes.value = await volRes.json()
  } finally {
    loading.value = false
  }
}

async function generate() {
  generating.value = true
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/generate`, { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      router.push(`/task/${data.task_id}`)
    }
  } finally {
    generating.value = false
  }
}

async function startConversation() {
  const topic = prompt('对话主题（如：讨论主角设定、情节走向）')
  if (!topic) return
  const res = await fetch(`/api/v1/projects/${novelId}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  })
  if (res.ok) {
    const data = await res.json()
    router.push(`/novels/${novelId}/conversations/${data.id}`)
  }
}

async function handleGenerateVolume(volumeNumber) {
  const res = await fetch(`/api/v1/projects/${novelId}/generate-volume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ volume_number: volumeNumber }),
  })
  if (res.ok) {
    const data = await res.json()
    router.push(`/task/${data.task_id}`)
  }
}

async function handleGenerateChapters({ chapter_start, chapter_end }) {
  showRangeDialog.value = false
  const res = await fetch(`/api/v1/projects/${novelId}/generate-chapters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chapter_start, chapter_end }),
  })
  if (res.ok) {
    const data = await res.json()
    router.push(`/task/${data.task_id}`)
  }
}

onMounted(fetchAll)
</script>
