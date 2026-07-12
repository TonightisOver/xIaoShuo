<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/30 backdrop-blur-sm" @click="$emit('close')"></div>
      <div class="relative bg-paper-50 border border-ink-200 rounded-2xl shadow-2xl p-6 max-w-4xl w-full mx-4 text-ink-600 grid grid-cols-1 md:grid-cols-5 gap-6 animate-fade-up">

        <!-- Left Side: Configurations (Col span 2) -->
        <div class="md:col-span-2 flex flex-col justify-between">
          <div>
            <h3 class="text-lg font-bold text-ink-700 mb-5 heading-serif">导出设置</h3>

            <div class="space-y-4">
              <div>
                <label class="block text-xs font-semibold text-ink-400 uppercase tracking-wide mb-1.5">导出格式</label>
                <div class="grid grid-cols-4 gap-2">
                  <button v-for="f in formats" :key="f.value"
                    @click="form.format = f.value"
                    type="button"
                    class="py-2 rounded-lg text-xs font-bold border transition-all text-center"
                    :class="form.format === f.value ? 'bg-vermilion-50 border-vermilion-200 text-vermilion-600 font-bold' : 'border-ink-200 text-ink-600 hover:border-ink-300'"
                  >{{ f.label }}</button>
                </div>
                <p v-if="form.format === 'mobi'" class="text-[10px] text-amber-600 mt-1.5 leading-relaxed">
                  💡 MOBI 导出需要在服务器配置 Calibre 环境。若无法使用，请导出 EPUB。
                </p>
              </div>

              <div>
                <label class="block text-xs font-semibold text-ink-400 uppercase tracking-wide mb-1.5">导出范围</label>
                <select v-model="form.scope" class="w-full bg-paper-100 border border-ink-200 rounded-lg px-3 py-2 text-xs text-ink-600 outline-none focus:border-vermilion-400">
                  <option value="full">全书</option>
                  <option value="volume">按卷</option>
                  <option value="range">按章节范围</option>
                </select>
              </div>

              <div v-if="form.scope === 'volume'">
                <label class="block text-xs font-semibold text-ink-400 uppercase tracking-wide mb-1.5">选择卷</label>
                <select v-model="form.volume_number" class="w-full bg-paper-100 border border-ink-200 rounded-lg px-3 py-2 text-xs text-ink-600 outline-none focus:border-vermilion-400">
                  <option v-for="v in volumes" :key="v.volume_number" :value="v.volume_number">
                    第{{ v.volume_number }}卷{{ v.title ? ' - ' + v.title : '' }}
                  </option>
                </select>
              </div>

              <div v-if="form.scope === 'range'" class="flex gap-3">
                <div class="flex-1">
                  <label class="block text-xs font-semibold text-ink-400 uppercase tracking-wide mb-1.5">起始章</label>
                  <input v-model.number="form.chapter_start" type="number" min="1" class="w-full bg-paper-100 border border-ink-200 rounded-lg px-3 py-2 text-xs text-ink-600 outline-none focus:border-vermilion-400" />
                </div>
                <div class="flex-1">
                  <label class="block text-xs font-semibold text-ink-400 uppercase tracking-wide mb-1.5">结束章</label>
                  <input v-model.number="form.chapter_end" type="number" min="1" class="w-full bg-paper-100 border border-ink-200 rounded-lg px-3 py-2 text-xs text-ink-600 outline-none focus:border-vermilion-400" />
                </div>
              </div>

              <div>
                <label class="block text-xs font-semibold text-ink-400 uppercase tracking-wide mb-1.5">排版模板</label>
                <select v-model="form.template" class="w-full bg-paper-100 border border-ink-200 rounded-lg px-3 py-2 text-xs text-ink-600 outline-none focus:border-vermilion-400">
                  <option value="default">通用模板 (双格缩进，默认空行)</option>
                  <option value="qidian">起点排版 (双格缩进，段间空行)</option>
                  <option value="fanqie">番茄小说 (双格缩进，无额外空行)</option>
                </select>
              </div>
            </div>
          </div>

          <div class="flex gap-3 justify-end mt-6 pt-4 border-t border-ink-200">
            <button @click="$emit('close')" type="button" class="px-4 py-2 text-xs font-medium text-ink-400 hover:text-ink-600 rounded-lg hover:bg-paper-100 transition-colors">
              取消
            </button>
            <button @click="doExport" :disabled="exporting" type="button" class="btn-primary px-5 py-2 text-xs font-bold transition-colors disabled:opacity-50">
              {{ exporting ? '正在构建图书...' : '开始导出' }}
            </button>
          </div>
        </div>

        <!-- Right Side: Live Preview Panel (Col span 3) -->
        <div class="md:col-span-3 border-l border-ink-200 pl-6 flex flex-col h-[400px]">
          <h4 class="text-sm font-bold text-ink-700 mb-3 flex items-center gap-2 heading-serif">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-vermilion-500">
              <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span>排版格式实时预览</span>
          </h4>

          <div v-if="previewLoading" class="flex-1 bg-paper-100 border border-ink-200 rounded-xl flex flex-col items-center justify-center gap-3">
            <div class="w-8 h-8 border-3 border-vermilion-500 border-t-transparent rounded-full animate-spin"></div>
            <span class="text-xs text-ink-400 font-medium">生成预览中...</span>
          </div>

          <div v-else class="flex-1 bg-paper-100 border border-ink-200 rounded-xl p-4 overflow-y-auto custom-scrollbar flex flex-col gap-3">
            <div class="border-b border-ink-200 pb-2">
              <span class="text-[10px] text-vermilion-500 font-bold uppercase tracking-wider">TOC Preview</span>
              <div class="flex flex-wrap gap-1.5 mt-1.5">
                <span v-for="(t, idx) in (previewData.toc || [])" :key="t" class="text-[10px] bg-ink-200 text-ink-600 px-2 py-0.5 rounded-full animate-fade-up-stagger" :style="{ animationDelay: `${Math.min(idx,8)*60}ms` }">{{ t }}</span>
                <span class="text-[10px] text-ink-300 pt-0.5">...</span>
              </div>
            </div>
            <div class="flex-1 text-xs text-ink-500 whitespace-pre-wrap leading-relaxed">
              <div class="font-bold text-ink-700 text-sm mb-2">{{ previewData.preview_title }}</div>
              {{ previewData.preview_content }}
            </div>
          </div>
        </div>

      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'

const props = defineProps({
  visible: Boolean,
  novelId: String,
  novelTitle: String,
  volumes: { type: Array, default: () => [] }
})

const emit = defineEmits(['close'])

const formats = [
  { value: 'txt', label: 'TXT' },
  { value: 'epub', label: 'EPUB' },
  { value: 'docx', label: 'DOCX' },
  { value: 'mobi', label: 'MOBI' },
]

const form = reactive({
  format: 'epub',
  scope: 'full',
  volume_number: null,
  chapter_start: 1,
  chapter_end: 10,
  template: 'default',
})

const exporting = ref(false)
const previewLoading = ref(false)
const previewData = ref({ preview_title: '', preview_content: '', toc: [] })

// Fetch real-time formatting preview when template changes
const fetchPreview = async () => {
  if (!props.novelId || !props.visible) return
  previewLoading.value = true
  try {
    const res = await fetch(`/api/v1/novels/${props.novelId}/export-preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        format: form.format,
        scope: form.scope,
        template: form.template,
      })
    })
    if (res.ok) {
      previewData.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to load format preview', e)
  } finally {
    previewLoading.value = false
  }
}

// Watch template settings to reload layout preview
watch(() => form.template, fetchPreview)
watch(() => props.visible, (newVal) => {
  if (newVal) {
    if (props.volumes && props.volumes.length > 0 && !form.volume_number) {
      form.volume_number = props.volumes[0].volume_number
    }
    fetchPreview()
  }
})

async function doExport() {
  exporting.value = true
  try {
    const body = {
      format: form.format,
      scope: form.scope,
      template: form.template,
    }
    if (form.scope === 'volume') body.volume_number = form.volume_number
    if (form.scope === 'range') {
      body.chapter_start = form.chapter_start
      body.chapter_end = form.chapter_end
    }

    const res = await fetch(`/api/v1/novels/${props.novelId}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    if (!res.ok) {
      const err = await res.json()
      alert(err.detail || '导出失败')
      return
    }

    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const title = props.novelTitle || '小说'
    a.href = url
    a.download = `${title}.${form.format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    emit('close')
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 9999px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
</style>
