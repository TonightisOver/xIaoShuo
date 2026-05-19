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
          <button v-if="novel.status === 'draft' || novel.status === 'completed' || novel.status === 'failed'" @click="fullGenerate" class="btn-primary text-sm bg-emerald-600 hover:bg-emerald-700" :disabled="fullGenerating">
            {{ fullGenerating ? '启动中...' : '全功能生成' }}
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
        <div class="flex justify-between items-center mb-4">
          <h2 class="font-medium text-ink-800">概览</h2>
          <div class="flex gap-2">
            <button v-if="!editingOverview" @click="startEditOverview" class="btn-secondary text-xs">编辑</button>
            <template v-else>
              <button @click="saveOverview" class="btn-primary text-xs" :disabled="savingOverview">{{ savingOverview ? '保存中...' : '保存' }}</button>
              <button @click="cancelEditOverview" class="btn-secondary text-xs">取消</button>
            </template>
          </div>
        </div>
        <dl class="grid grid-cols-2 gap-4 text-sm">
          <div><dt class="text-ink-500">状态</dt><dd class="font-medium mt-1">{{ statusLabel }}</dd></div>
          <div><dt class="text-ink-500">类型</dt><dd class="font-medium mt-1">{{ novel.novel_type }}</dd></div>
          <div class="col-span-2">
            <dt class="text-ink-500">标题</dt>
            <dd class="mt-1">
              <input v-if="editingOverview" v-model="overviewForm.title" class="input text-sm w-full" maxlength="200" />
              <span v-else>{{ novel.title }}</span>
            </dd>
          </div>
          <div class="col-span-2">
            <dt class="text-ink-500">简介</dt>
            <dd class="mt-1">
              <textarea v-if="editingOverview" v-model="overviewForm.idea" class="input text-sm w-full min-h-[80px] resize-y" rows="5" maxlength="2000"></textarea>
              <span v-else class="whitespace-pre-wrap">{{ novel.idea }}</span>
            </dd>
          </div>
          <div><dt class="text-ink-500">人物数</dt><dd class="font-medium mt-1">{{ novel.characters_count }}</dd></div>
          <div><dt class="text-ink-500">世界观</dt><dd class="font-medium mt-1">{{ novel.world_setting ? '已设定' : '未设定' }}</dd></div>
        </dl>
        <p v-if="overviewSaved" class="text-xs text-emerald-600 mt-2">已保存</p>
        <p v-if="overviewError" class="text-xs text-red-500 mt-2">{{ overviewError }}</p>
      </div>

      <div v-if="activeTab === 'outlines'" class="card p-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="font-medium text-ink-800">大纲体系</h2>
          <router-link :to="`/novels/${novelId}/outlines`" class="btn-primary text-sm">编辑大纲</router-link>
        </div>
        <div v-if="outlineTree" class="space-y-4 text-sm">
          <div v-if="outlineTree.master">
            <h3 class="text-ink-500 text-xs uppercase mb-1">总纲</h3>
            <div class="p-3 bg-ink-50 rounded-lg">
              <p v-if="outlineTree.master.content?.premise" class="font-medium">{{ outlineTree.master.content.premise }}</p>
              <p v-if="outlineTree.master.content?.main_conflict" class="text-ink-600 mt-1">冲突：{{ outlineTree.master.content.main_conflict }}</p>
              <p v-if="outlineTree.master.content?.ending" class="text-ink-600">结局：{{ outlineTree.master.content.ending }}</p>
            </div>
          </div>
          <div v-if="outlineTree.volumes?.length">
            <h3 class="text-ink-500 text-xs uppercase mt-4 mb-2">卷纲（{{ outlineTree.volumes.length }} 卷）</h3>
            <div v-for="vol in outlineTree.volumes" :key="vol.id" class="ml-2 mb-2 border-l-2 border-ink-200 pl-3">
              <p class="font-medium">卷{{ vol.volume_number }}：{{ vol.content?.title || '未命名' }}</p>
              <p class="text-ink-500 text-xs">{{ vol.content?.summary || '' }}</p>
              <p v-if="vol.chapters?.length" class="text-ink-400 text-xs mt-1">{{ vol.chapters.length }} 章</p>
            </div>
          </div>
          <p v-if="!outlineTree.master && !outlineTree.volumes?.length" class="text-ink-400">暂无大纲数据</p>
        </div>
        <p v-else class="text-sm text-ink-500">在大纲编辑器中管理总纲、卷纲、章纲三级结构。</p>
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

      <div v-if="activeTab === 'power-systems'" class="space-y-3">
        <div class="flex justify-between items-center">
          <h2 class="font-medium text-ink-800">力量体系</h2>
        </div>
        <div v-if="powerSystems.length === 0" class="card p-6 text-center text-ink-400">暂无力量体系</div>
        <div v-for="ps in powerSystems" :key="ps.id" class="card p-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="font-medium">{{ ps.name }}</span>
          </div>
          <p v-if="ps.description" class="text-sm text-ink-600 mb-2">{{ ps.description }}</p>
          <div v-if="ps.levels?.length" class="space-y-1 mt-2">
            <div v-for="(lvl, i) in ps.levels" :key="i" class="flex items-start gap-2 text-xs py-1 border-b border-ink-100 last:border-0">
              <span class="font-medium text-primary-700 shrink-0">{{ lvl.name }}</span>
              <span class="text-ink-600">{{ lvl.description }}</span>
              <span v-if="lvl.breakthrough" class="text-ink-400 ml-auto shrink-0">突破: {{ lvl.breakthrough }}</span>
            </div>
          </div>
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
        <div v-if="storylinesData" class="space-y-4 text-sm">
          <div v-if="storylinesData.storylines?.length">
            <h3 class="text-ink-500 text-xs uppercase mb-2">故事线（{{ storylinesData.storylines.length }}）</h3>
            <div v-for="sl in storylinesData.storylines" :key="sl.id" class="ml-2 mb-2 border-l-2 border-primary-200 pl-3">
              <span class="font-medium">{{ sl.name }}</span>
              <span :class="sl.type === 'main' ? 'badge bg-primary-50 text-primary-700 ml-2' : sl.type === 'hidden' ? 'badge bg-amber-50 text-amber-700 ml-2' : 'badge bg-ink-100 text-ink-600 ml-2'">{{ sl.type === 'main' ? '主线' : sl.type === 'hidden' ? '暗线' : '副线' }}</span>
              <p v-if="sl.description" class="text-ink-500 text-xs mt-1">{{ sl.description }}</p>
            </div>
          </div>
          <div v-if="storylinesData.character_arcs?.length">
            <h3 class="text-ink-500 text-xs uppercase mt-4 mb-2">人物弧光（{{ storylinesData.character_arcs.length }}）</h3>
            <div v-for="arc in storylinesData.character_arcs" :key="arc.id" class="ml-2 mb-1 pl-3 border-l-2 border-emerald-200">
              <span :class="arc.arc_type === 'growth' ? 'text-emerald-700' : arc.arc_type === 'fall' ? 'text-red-700' : 'text-ink-700'" class="text-xs font-medium">{{ arc.arc_type === 'growth' ? '成长' : arc.arc_type === 'fall' ? '堕落' : '转变' }}</span>
              <span class="text-xs text-ink-600 ml-1">{{ arc.description || '' }}</span>
            </div>
          </div>
          <div v-if="storylinesData.scenes?.length">
            <h3 class="text-ink-500 text-xs uppercase mt-4 mb-2">场景（{{ storylinesData.scenes.length }}）</h3>
            <div v-for="sc in storylinesData.scenes" :key="sc.id" class="inline-block mr-2 mb-2 px-2 py-1 bg-ink-50 rounded text-xs">
              <span class="font-medium">{{ sc.name }}</span>
              <span v-if="sc.location" class="text-ink-400 ml-1">{{ sc.location }}</span>
            </div>
          </div>
          <p v-if="!storylinesData.storylines?.length && !storylinesData.character_arcs?.length && !storylinesData.scenes?.length" class="text-ink-400">暂无故事线数据</p>
        </div>
        <p v-else class="text-sm text-ink-500">在故事线管理器中创建和编辑故事线、人物弧光、场景，以及它们之间的关联关系。</p>
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
const powerSystems = ref([])
const storylinesData = ref(null)
const outlineTree = ref(null)
const loading = ref(true)
const generating = ref(false)
const fullGenerating = ref(false)
const activeTab = ref('overview')
const showRangeDialog = ref(false)

const editingOverview = ref(false)
const savingOverview = ref(false)
const overviewSaved = ref(false)
const overviewError = ref('')
const overviewForm = ref({ title: '', idea: '' })

function startEditOverview() {
  overviewForm.value = { title: novel.value.title || '', idea: novel.value.idea || '' }
  editingOverview.value = true
  overviewSaved.value = false
  overviewError.value = ''
}

function cancelEditOverview() {
  editingOverview.value = false
}

async function saveOverview() {
  savingOverview.value = true
  overviewError.value = ''
  try {
    const res = await fetch(`/api/v1/projects/${novelId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: overviewForm.value.title, idea: overviewForm.value.idea }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      overviewError.value = data.detail || '保存失败'
      return
    }
    novel.value = { ...novel.value, ...overviewForm.value }
    editingOverview.value = false
    overviewSaved.value = true
    setTimeout(() => { overviewSaved.value = false }, 2000)
  } finally {
    savingOverview.value = false
  }
}

const unassignedChapters = computed(() =>
  chapters.value.filter(c => !c.volume_number)
)

const tabs = [
  { id: 'overview', label: '概览' },
  { id: 'outlines', label: '大纲' },
  { id: 'world', label: '世界观' },
  { id: 'power-systems', label: '力量体系' },
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
    const [nRes, wRes, cRes, chRes, convRes, volRes, psRes, slRes, olRes] = await Promise.all([
      fetch(`/api/v1/projects/${novelId}`),
      fetch(`/api/v1/projects/${novelId}/world`),
      fetch(`/api/v1/projects/${novelId}/characters`),
      fetch(`/api/v1/projects/${novelId}/chapters`),
      fetch(`/api/v1/projects/${novelId}/conversations`),
      fetch(`/api/v1/projects/${novelId}/volumes`),
      fetch(`/api/v1/projects/${novelId}/power-systems`),
      fetch(`/api/v1/projects/${novelId}/relations`),
      fetch(`/api/v1/projects/${novelId}/outlines`),
    ])
    if (nRes.ok) novel.value = await nRes.json()
    if (wRes.ok) world.value = await wRes.json()
    if (cRes.ok) characters.value = await cRes.json()
    if (chRes.ok) chapters.value = await chRes.json()
    if (convRes.ok) conversations.value = await convRes.json()
    if (volRes.ok) volumes.value = await volRes.json()
    if (psRes.ok) powerSystems.value = await psRes.json()
    if (slRes.ok) storylinesData.value = await slRes.json()
    if (olRes.ok) outlineTree.value = await olRes.json()
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

async function fullGenerate() {
  fullGenerating.value = true
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/generate-full`, { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      router.push(`/task/${data.task_id}`)
    }
  } finally {
    fullGenerating.value = false
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
