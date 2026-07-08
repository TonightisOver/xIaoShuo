<template>
  <div class="timeline-view">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-base font-bold text-neutral-800">跨章节实体演化时间线</h2>
      <div v-if="selectedEntity" class="text-xs text-neutral-500">
        已选实体：
        <span class="font-bold text-purple-600">{{ selectedEntity.name }}</span>
        <button @click="selectedEntity = null" class="ml-1.5 text-neutral-400 hover:text-neutral-600">✕</button>
      </div>
    </div>

    <!-- Entity selector chips -->
    <div v-if="!selectedEntity && entities.length" class="flex flex-wrap gap-2 mb-4">
      <button
        v-for="entity in entities"
        :key="entity.id"
        @click="selectedEntity = entity"
        class="text-xs py-1 px-3 rounded-lg border transition-all font-medium"
        :class="entity.entity_type === 'character'
          ? 'border-blue-200 text-blue-600 hover:bg-blue-50'
          : entity.entity_type === 'location'
            ? 'border-emerald-200 text-emerald-600 hover:bg-emerald-50'
            : entity.entity_type === 'event'
              ? 'border-orange-200 text-orange-600 hover:bg-orange-50'
              : 'border-purple-200 text-purple-600 hover:bg-purple-50'"
      >
        {{ entity.name }}
        <span class="opacity-50 text-[10px] ml-1">{{ typeLabel(entity.entity_type) }}</span>
      </button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-16">
      <div class="w-8 h-8 rounded-full border-4 border-purple-500/10 border-t-purple-600 animate-spin"></div>
    </div>

    <div v-else-if="!entities.length" class="text-center py-12 text-neutral-400 text-sm bg-neutral-50 rounded-xl border border-neutral-200">
      暂无实体演化数据。请先生成章节内容后触发知识抽取。
    </div>

    <div v-else-if="!selectedEntity" class="text-center py-8 text-neutral-400 text-sm">
      请选择一个实体以查看跨章节演化时间线。
    </div>

    <div v-else class="card p-6 rounded-xl bg-white shadow-sm">
      <!-- Entity header -->
      <div class="flex items-center gap-3 mb-6 pb-4 border-b border-neutral-200">
        <span
          class="w-4 h-4 rounded-full shrink-0"
          :style="{ background: getEntityColor(selectedEntity.entity_type) }"
        ></span>
        <div>
          <p class="font-bold text-neutral-900 text-sm">{{ selectedEntity.name }}</p>
          <p class="text-[11px] text-neutral-400">
            实体类型：{{ typeLabel(selectedEntity.entity_type) }}
            <span v-if="selectedEntity.first_chapter || selectedEntity.last_chapter">
              · 第{{ selectedEntity.first_chapter || '?' }}章 ~ 第{{ selectedEntity.last_chapter || '?' }}章
            </span>
          </p>
        </div>
      </div>

      <!-- Loading states -->
      <div v-if="statesLoading" class="flex items-center justify-center py-12">
        <div class="w-6 h-6 rounded-full border-3 border-purple-500/10 border-t-purple-600 animate-spin"></div>
      </div>

      <div v-else-if="stateEvents.length === 0" class="text-center py-8 text-neutral-400 text-xs">
        该实体尚无跨章节演化轨迹记录。前往知识图谱页面触发抽取后可在此查看。
      </div>

      <!-- Timeline Canvas -->
      <div v-else class="relative overflow-x-auto">
        <svg
          ref="timelineSvg"
          class="w-full"
          :viewBox="`0 0 ${svgWidth} 140`"
          :width="svgWidth"
          height="140"
        >
          <!-- Background axis line -->
          <line
            :x1="axisStartX + 12"
            :y1="axisY"
            :x2="axisEndX - 12"
            :y2="axisY"
            stroke="#d4d4d8"
            stroke-width="2"
            stroke-linecap="round"
          />

          <!-- Chapter markers and labels -->
          <g v-for="ch in chapterTicks" :key="'tick' + ch.num">
            <line
              :x1="ch.x"
              :y1="axisY - 5"
              :x2="ch.x"
              :y2="axisY + 5"
              stroke="#a1a1aa"
              stroke-width="1.5"
            />
            <text
              :x="ch.x"
              :y="axisY + 18"
              text-anchor="middle"
              fill="#a1a1aa"
              font-size="10"
              font-weight="500"
            >
              Ch.{{ ch.num }}
            </text>
          </g>

          <!-- State event nodes -->
          <g v-for="(sn, i) in stateEvents" :key="sn.id">
            <!-- Connector line from axis to event card -->
            <line
              :x1="stateX(sn.chapter_number)"
              :y1="axisY"
              :x2="stateX(sn.chapter_number)"
              :y2="cardY(i)"
              stroke="#c4b5fd"
              stroke-width="1"
              stroke-dasharray="3,3"
            />

            <!-- Circle marker on axis -->
            <circle
              :cx="stateX(sn.chapter_number)"
              :cy="axisY"
              r="6"
              :fill="getEntityColor(selectedEntity.entity_type)"
              stroke="#ffffff"
              stroke-width="2"
              class="cursor-pointer"
            >
              <title>
                {{ sn.chapter_number ? '第 ' + sn.chapter_number + ' 章' : '' }}
                {{ formatDate(sn.created_at) }}
              </title>
            </circle>

            <!-- Event card -->
            <foreignObject
              :x="stateX(sn.chapter_number) - 90"
              :y="cardY(i) - 16"
              width="180"
              height="48"
            >
              <div class="rounded-lg border border-neutral-200 bg-neutral-50 px-2.5 py-1.5 text-[11px] shadow-xs"
                :style="{ borderLeft: '3px solid ' + getEntityColor(selectedEntity.entity_type) }"
              >
                <p class="font-bold text-neutral-700">
                  <template v-if="Object.keys(sn.attributes).length">
                    {{ getFirstValue(sn.attributes) }}
                  </template>
                  <template v-else class="text-neutral-400 italic">无记录</template>
                </p>
                <p v-if="sn.attributes" class="text-[10px] text-neutral-400 mt-0.5 truncate">
                  {{ extraAttrs(sn.attributes) }}
                </p>
              </div>
            </foreignObject>
          </g>
        </svg>
      </div>

      <!-- Conflict markers -->
      <div v-if="conflicts.length" class="mt-6 pt-4 border-t border-red-100">
        <h3 class="text-xs font-bold text-red-600 flex items-center gap-1.5 mb-3">
          <span class="w-2 h-2 rounded-full bg-red-500 inline-block"></span>
          一致性冲突（{{ conflicts.length }}）
        </h3>
        <div class="space-y-2">
          <div
            v-for="c in conflicts"
            :key="c.id"
            class="p-3 rounded-lg bg-red-50 border border-red-100 text-xs"
          >
            <span class="font-bold text-red-700">第 {{ c.chapter_number }} 章</span>
            <span class="text-red-600" v-if="c.detail">：{{ c.detail }}</span>
            <span class="text-red-600" v-else>：检测到属性冲突</span>
          </div>
        </div>
      </div>

      <!-- Legend -->
      <div class="flex flex-wrap gap-4 mt-4 px-4 py-2 rounded-lg bg-neutral-50 border border-neutral-200 text-xs text-neutral-500">
        <span class="flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 12 12">
            <circle cx="6" cy="6" r="5" :fill="getEntityColor(selectedEntity?.entity_type || 'character')" stroke="white" stroke-width="1.5" />
          </svg>
          状态快照
        </span>
        <span class="flex items-center gap-1.5">
          <svg width="16" height="4" viewBox="0 0 16 4">
            <line x1="2" y1="2" x2="14" y2="2" stroke="#c4b5fd" stroke-width="1.5" stroke-dasharray="2,2" />
          </svg>
          演替路径
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-3 h-3 inline-block rounded-full bg-red-400"></span>
          一致性冲突
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-4 h-0.5 inline-block bg-red-300"></span>
          冲突关联
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps({
  novelId: { type: String, required: true },
})

const loading = ref(false)
const statesLoading = ref(false)
const entities = ref([])
const selectedEntity = ref(null)
const stateEvents = ref([])
const conflicts = ref([])
const timelineSvg = ref(null)

const axisY = 30
const svgWidth = computed(() => Math.max(800, (chapterTicks.value.length + 1) * 80 + 80))

const axisStartX = computed(() => 60)
const axisEndX = computed(() => svgWidth.value - 60)

function typeLabel(type) {
  return { character: '人物', location: '地点', event: '事件', item: '物品', unknown: '其他' }[type] || type
}

function getEntityColor(type) {
  return {
    character: '#3b82f6',
    location: '#10b981',
    event: '#f97316',
    item: '#8b5cf6',
    unknown: '#a3a3a3',
  }[type] || '#a3a3a3'
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
  })
}

function getFirstValue(attrs) {
  if (!attrs) return '无记录'
  const vals = Object.values(attrs)
  return vals.length ? String(vals[0]) : '无记录'
}

function extraAttrs(attrs) {
  if (!attrs) return ''
  const entries = Object.entries(attrs)
  if (entries.length <= 1) return ''
  return entries.slice(1).map(([k, v]) => `${k}:${v}`).join(' · ')
}

async function fetchEntities() {
  loading.value = true
  try {
    const res = await fetch(`/api/v1/projects/${props.novelId}/knowledge-graph/entities`)
    if (res.ok) {
      entities.value = await res.json()
    }
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

async function fetchHistory(entityId) {
  statesLoading.value = true
  try {
    const res = await fetch(`/api/v1/projects/${props.novelId}/knowledge-graph/entities/${entityId}/history`)
    if (res.ok) {
      stateEvents.value = await res.json()
    } else {
      stateEvents.value = []
    }
  } catch {
    stateEvents.value = []
  } finally {
    statesLoading.value = false
  }
}

async function fetchConflicts(entityId) {
  try {
    const res = await fetch(`/api/v1/projects/${props.novelId}/knowledge-graph/conflicts`)
    if (res.ok) {
      const all = await res.json()
      conflicts.value = all.filter(
        (c) => c.conflicts && c.conflicts.some((cc) => cc.entity_id === entityId),
      )
    }
  } catch {
    conflicts.value = []
  }
}

const chapterTicks = computed(() => {
  if (!stateEvents.value.length) return []
  const chapters = stateEvents.value.map((e) => e.chapter_number)
  const unique = [...new Set(chapters)].sort((a, b) => a - b)
  const span = unique.length
  const margin = 60
  const usable = svgWidth.value - margin * 2
  return unique.map((num, i) => ({
    num,
    x: margin + (span > 1 ? (i / (span - 1)) * usable : usable / 2),
  }))
})

function stateX(chapterNumber) {
  const tick = chapterTicks.value.find((t) => t.num === chapterNumber)
  if (tick) return tick.x
  if (!chapterTicks.value.length) return svgWidth.value / 2
  const usable = svgWidth.value - 60 * 2
  const minCh = chapterTicks.value[0].num
  const maxCh = chapterTicks.value[chapterTicks.value.length - 1].num
  const span = Math.max(maxCh - minCh, 1)
  return 60 + ((chapterNumber - minCh) / span) * usable
}

function cardY(index) {
  const perState = 52
  const offset = 50
  if (index % 2 === 0) return offset
  return offset + perState
}

watch(
  () => selectedEntity.value,
  (ent) => {
    if (ent) {
      fetchHistory(ent.id)
      fetchConflicts(ent.id)
    } else {
      stateEvents.value = []
      conflicts.value = []
    }
  },
)

onMounted(fetchEntities)
</script>
