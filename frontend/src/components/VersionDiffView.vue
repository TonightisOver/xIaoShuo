<template>
  <div class="space-y-4">
    <div v-if="loading" class="flex flex-col items-center justify-center rounded-lg border border-neutral-200 bg-white py-12">
      <div class="h-8 w-8 animate-spin rounded-full border-2 border-accent-200 border-t-accent-600"></div>
      <p class="mt-3 text-sm text-neutral-500">正在加载版本差异...</p>
    </div>

    <div v-else-if="error" class="rounded-lg border border-rose-200 bg-rose-50 p-5 text-center">
      <h3 class="text-sm font-semibold text-rose-700">加载差异失败</h3>
      <p class="mt-1 text-xs text-rose-600">{{ error }}</p>
      <button
        type="button"
        class="mt-4 rounded-md border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-700 transition-colors hover:bg-rose-100"
        @click="fetchCompare"
      >
        重试
      </button>
    </div>

    <template v-else-if="compareData">
      <div class="grid gap-3 md:grid-cols-2">
        <VersionMetaCard title="基准版本" :version="compareData.v1" />
        <VersionMetaCard title="对比版本" :version="compareData.v2" highlighted />
      </div>

      <div class="overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm">
        <div class="flex items-center justify-between border-b border-neutral-200 bg-neutral-50 px-4 py-2">
          <span class="font-mono text-xs font-semibold text-neutral-600">统一差异</span>
          <span class="text-xs text-neutral-500">
            <span class="font-mono font-semibold text-emerald-600">+</span> 新增
            <span class="mx-1 text-neutral-300">/</span>
            <span class="font-mono font-semibold text-rose-600">-</span> 删除
          </span>
        </div>

        <div ref="scrollRoot" class="max-h-[70vh] overflow-auto" @scroll="onScroll">
          <table class="w-full border-collapse font-mono text-xs">
            <tbody>
              <tr
                v-for="line in visibleLines"
                :key="`${line._index}-${line.leftNumber}-${line.rightNumber}`"
                class="border-b border-neutral-100 last:border-b-0"
                :class="lineRowClass(line.type)"
              >
                <td class="w-14 select-none border-r border-neutral-200 bg-black/[0.02] px-2 py-1 text-right text-[11px] text-neutral-400">
                  {{ line.leftNumber }}
                </td>
                <td class="w-14 select-none border-r border-neutral-200 bg-black/[0.02] px-2 py-1 text-right text-[11px] text-neutral-400">
                  {{ line.rightNumber }}
                </td>
                <td class="w-8 select-none px-2 py-1 text-center font-semibold" :class="markerClass(line.type)">
                  {{ lineMarker(line.type) }}
                </td>
                <td class="whitespace-pre-wrap break-words px-2 py-1 leading-relaxed text-neutral-800">
                  {{ line.content }}
                </td>
              </tr>
              <tr v-if="parsedLines.length === 0">
                <td colspan="4" class="px-4 py-10 text-center text-sm text-neutral-400">
                  未返回行级差异。
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, onUnmounted, ref, watch } from 'vue'
import { formatDate, formatNumber, sourceClass, sourceLabel } from '../utils/versionHelpers.js'

// Windowed rendering state: avoid rendering thousands of <tr> for huge diffs
const scrollRoot = ref(null)
const scrollTop = ref(0)
const VIEWPORT_HEIGHT = 600 // matches max-h-[70vh] when 70vh ~ 600px
const ROW_HEIGHT = 28 // matches `py-1 + text-xs` line height
const OVERSCAN = 20

const visibleLines = computed(() => {
  if (parsedLines.value.length <= 200) {
    // Small diff: render all, no virtualization needed
    return parsedLines.value.map((l, i) => ({ ...l, _index: i }))
  }
  const start = Math.max(0, Math.floor(scrollTop.value / ROW_HEIGHT) - OVERSCAN)
  const visible = Math.ceil(VIEWPORT_HEIGHT / ROW_HEIGHT) + OVERSCAN * 2
  const end = Math.min(parsedLines.value.length, start + visible)
  return parsedLines.value
    .slice(start, end)
    .map((l, i) => ({ ...l, _index: start + i }))
})

function onScroll(event) {
  scrollTop.value = event.target.scrollTop
}

const props = defineProps({
  novelId: {
    type: String,
    required: true,
  },
  chapterNumber: {
    type: Number,
    required: true,
  },
  v1: {
    type: Number,
    required: true,
  },
  v2: {
    type: Number,
    required: true,
  },
})

const compareData = ref(null)
const loading = ref(false)
const error = ref('')
const abortController = ref(null)

const VersionMetaCard = defineComponent({
  props: {
    title: {
      type: String,
      required: true,
    },
    version: {
      type: Object,
      default: null,
    },
    highlighted: {
      type: Boolean,
      default: false,
    },
  },
  setup(cardProps) {
    return () => h(
      'div',
      {
        class: [
          'rounded-lg border p-4',
          cardProps.highlighted ? 'border-accent-200 bg-accent-50' : 'border-neutral-200 bg-white',
        ],
      },
      [
        h('div', { class: 'mb-2 text-xs font-semibold text-neutral-500' }, cardProps.title),
        h('div', { class: 'flex items-center justify-between gap-3' }, [
          h('span', { class: 'text-sm font-bold text-neutral-900' }, `v${cardProps.version?.version_number ?? '-'}`),
          h('span', { class: ['rounded-full px-2 py-0.5 text-[10px] font-semibold', sourceClass(cardProps.version?.source)] }, sourceLabel(cardProps.version?.source)),
        ]),
        h('div', { class: 'mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-neutral-500' }, [
          h('span', null, `${formatNumber(cardProps.version?.word_count)} 字`),
          h('span', null, formatDate(cardProps.version?.created_at)),
        ]),
      ],
    )
  },
})

async function fetchCompare() {
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
  }

  if (!props.novelId || props.chapterNumber == null || props.v1 == null || props.v2 == null) {
    loading.value = false
    return
  }

  const controller = new AbortController()
  abortController.value = controller
  loading.value = true
  error.value = ''

  try {
    const params = new URLSearchParams({
      v1: String(props.v1),
      v2: String(props.v2),
    })
    const res = await fetch(`/api/v1/projects/${encodeURIComponent(props.novelId)}/chapters/${props.chapterNumber}/versions/compare?${params}`, {
      signal: controller.signal,
    })

    if (!res.ok) {
      let message = `请求失败，状态码 ${res.status}`
      try {
        const payload = await res.json()
        message = payload.detail || payload.message || message
      } catch {
        const text = await res.text()
        if (text) message = text
      }
      throw new Error(message)
    }

    const data = await res.json()
    if (abortController.value !== controller) return
    compareData.value = data
  } catch (err) {
    if (controller.signal.aborted) return
    compareData.value = null
    error.value = err instanceof Error ? err.message : '未知错误'
  } finally {
    if (abortController.value === controller) {
      loading.value = false
      abortController.value = null
    }
  }
}

const parsedLines = computed(() => {
  const diffLines = compareData.value?.diff_lines
  if (!Array.isArray(diffLines)) return []

  const output = []
  let leftLine = 0
  let rightLine = 0

  for (const rawLine of diffLines) {
    const line = normalizeDiffLine(rawLine)

    if (line.type === 'header') {
      const range = parseUnifiedRange(line.content)
      if (range) {
        leftLine = range.leftStart - 1
        rightLine = range.rightStart - 1
      }
      output.push({ ...line, leftNumber: '...', rightNumber: '...' })
      continue
    }

    if (line.leftNumber == null && line.type !== 'added') leftLine += 1
    if (line.rightNumber == null && line.type !== 'removed') rightLine += 1

    output.push({
      type: line.type,
      content: line.content,
      leftNumber: line.leftNumber ?? (line.type === 'added' ? '' : leftLine),
      rightNumber: line.rightNumber ?? (line.type === 'removed' ? '' : rightLine),
    })
  }

  return output
})

watch(
  () => [props.novelId, props.chapterNumber, props.v1, props.v2],
  fetchCompare,
  { immediate: true },
)

onUnmounted(() => {
  abortController.value?.abort()
})

function normalizeDiffLine(rawLine) {
  if (typeof rawLine === 'string') {
    return normalizeStringLine(rawLine)
  }

  const type = normalizeType(rawLine?.type || rawLine?.op || rawLine?.tag)
  const content = rawLine?.text ?? rawLine?.content ?? rawLine?.line ?? ''

  return {
    type,
    content: stripMarker(String(content), type),
    leftNumber: rawLine?.v1_line ?? rawLine?.left_line ?? rawLine?.old_line ?? null,
    rightNumber: rawLine?.v2_line ?? rawLine?.right_line ?? rawLine?.new_line ?? null,
  }
}

function normalizeStringLine(line) {
  if (line.startsWith('@@')) {
    return { type: 'header', content: line }
  }
  if (line.startsWith('+') && !line.startsWith('+++')) {
    return { type: 'added', content: line.slice(1) }
  }
  if (line.startsWith('-') && !line.startsWith('---')) {
    return { type: 'removed', content: line.slice(1) }
  }
  return { type: 'normal', content: line.startsWith(' ') ? line.slice(1) : line }
}

function normalizeType(type) {
  const value = String(type || '').toLowerCase()
  if (['add', 'added', 'insert', 'inserted', '+'].includes(value)) return 'added'
  if (['delete', 'deleted', 'remove', 'removed', '-'].includes(value)) return 'removed'
  if (['header', 'hunk'].includes(value)) return 'header'
  return 'normal'
}

function stripMarker(content, type) {
  if ((type === 'added' && content.startsWith('+')) || (type === 'removed' && content.startsWith('-'))) {
    return content.slice(1)
  }
  return content.startsWith(' ') ? content.slice(1) : content
}

function parseUnifiedRange(line) {
  const match = line.match(/@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@/)
  if (!match) return null
  return {
    leftStart: Number(match[1]),
    rightStart: Number(match[2]),
  }
}

function lineRowClass(type) {
  const classes = {
    added: 'bg-emerald-50 hover:bg-emerald-100/70',
    removed: 'bg-rose-50 hover:bg-rose-100/70',
    header: 'bg-neutral-100 text-neutral-500',
    normal: 'hover:bg-neutral-50',
  }
  return classes[type] || classes.normal
}

function markerClass(type) {
  const classes = {
    added: 'text-emerald-700',
    removed: 'text-rose-700',
    header: 'text-neutral-400',
    normal: 'text-neutral-300',
  }
  return classes[type] || classes.normal
}

function lineMarker(type) {
  if (type === 'added') return '+'
  if (type === 'removed') return '-'
  return ''
}

</script>
