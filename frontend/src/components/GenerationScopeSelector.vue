<template>
  <div class="card p-4 space-y-3" data-generation-scope-selector>
    <h3 class="heading-serif text-lg">生成范围</h3>

    <div class="flex flex-wrap items-center gap-3">
      <label class="text-sm text-ink-600">模式</label>
      <select
        v-model="form.mode"
        data-mode-select
        class="input text-sm"
      >
        <option value="chapters">章节范围</option>
        <option value="volume">单卷</option>
        <option value="single">单章</option>
        <option value="continue">从某章继续</option>
      </select>
    </div>

    <div v-if="form.mode === 'chapters' || form.mode === 'continue'" class="flex items-center gap-2">
      <label class="text-sm text-ink-600">起始章</label>
      <input
        type="number"
        min="1"
        data-input="chapter_start"
        v-model.number="form.chapter_start"
        class="input w-24 text-sm"
      />
      <template v-if="form.mode === 'chapters'">
        <label class="text-sm text-ink-600">结束章</label>
        <input
          type="number"
          min="1"
          data-input="chapter_end"
          v-model.number="form.chapter_end"
          class="input w-24 text-sm"
        />
      </template>
    </div>

    <div v-if="form.mode === 'volume'" class="flex items-center gap-2">
      <label class="text-sm text-ink-600">卷号</label>
      <input
        type="number"
        min="1"
        data-input="volume_number"
        v-model.number="form.volume_number"
        class="input w-24 text-sm"
      />
    </div>

    <div v-if="form.mode === 'single'" class="flex items-center gap-2">
      <label class="text-sm text-ink-600">章号</label>
      <input
        type="number"
        min="1"
        data-input="chapter_number"
        v-model.number="form.chapter_number"
        class="input w-24 text-sm"
      />
    </div>

    <div class="flex items-center gap-2">
      <label class="text-sm text-ink-600 flex items-center gap-1">
        <input type="checkbox" v-model="form.respect_locked" /> 跳过已锁定
      </label>
      <label class="text-sm text-ink-600 flex items-center gap-1">
        <input type="checkbox" v-model="form.skip_confirmed" /> 跳过已确认
      </label>
    </div>

    <div class="flex items-center gap-2 pt-1">
      <button
        type="button"
        data-preview-btn
        class="btn-secondary text-sm"
        :disabled="previewing"
        @click="runPreview"
      >
        {{ previewing ? '预览中...' : '预览影响' }}
      </button>
      <button
        type="button"
        data-plan-btn
        class="btn-primary text-sm"
        @click="emitPlan"
      >
        生成范围
      </button>
    </div>

    <div v-if="preview" class="text-sm text-ink-600 space-y-1 border-t border-ink-100 pt-2">
      <p data-preview-result>预计 {{ preview.estimated_chapters }} 章 · 约 {{ Math.round(preview.estimated_tokens) }} tokens</p>
      <p v-if="preview.skipped_locked || preview.skipped_confirmed" class="text-xs text-ink-400">
        跳过 锁定 {{ preview.skipped_locked }} · 已确认 {{ preview.skipped_confirmed }}
      </p>
    </div>

    <p v-if="error" class="text-sm text-rose-600">{{ error }}</p>
  </div>
</template>

<script setup>
/**
 * GenerationScopeSelector —— 生成范围选择 + 预览。
 *
 * props.novelId
 * 预览：POST /api/v1/projects/{novelId}/creative-control/generate-scope/preview
 * emit plan(payload): { mode, chapter_start, chapter_end, volume_number, chapter_number,
 *                       respect_locked, skip_confirmed }
 */
import { reactive, ref } from 'vue'

const props = defineProps({
  novelId: { type: [String, Number], required: true },
})

const emit = defineEmits(['plan'])

const form = reactive({
  mode: 'chapters',
  chapter_start: 1,
  chapter_end: 3,
  volume_number: 1,
  chapter_number: 1,
  respect_locked: true,
  skip_confirmed: false,
})

const previewing = ref(false)
const preview = ref(null)
const error = ref('')

function buildPayload() {
  const p = {
    mode: form.mode,
    respect_locked: form.respect_locked,
    skip_confirmed: form.skip_confirmed,
  }
  if (form.mode === 'chapters') {
    p.chapter_start = form.chapter_start
    p.chapter_end = form.chapter_end
  } else if (form.mode === 'continue') {
    p.chapter_start = form.chapter_start
  } else if (form.mode === 'volume') {
    p.volume_number = form.volume_number
  } else if (form.mode === 'single') {
    p.chapter_number = form.chapter_number
  }
  return p
}

async function runPreview() {
  error.value = ''
  previewing.value = true
  try {
    const token = (typeof localStorage !== 'undefined' && localStorage.getItem('session_token')) || null
    const headers = { 'Content-Type': 'application/json' }
    if (token) headers['x-session-token'] = token
    const res = await fetch(
      `/api/v1/projects/${props.novelId}/creative-control/generate-scope/preview`,
      { method: 'POST', headers, body: JSON.stringify(buildPayload()) },
    )
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || '预览失败')
    }
    preview.value = await res.json()
  } catch (e) {
    error.value = e.message || '预览失败'
    preview.value = null
  } finally {
    previewing.value = false
  }
}

function emitPlan() {
  emit('plan', buildPayload())
}
</script>
