<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/30 backdrop-blur-sm" @click="$emit('close')"></div>
      <div class="relative bg-white rounded-2xl shadow-2xl p-6 w-[420px] mx-4 border border-neutral-200">
        <h3 class="text-lg font-bold text-neutral-900 mb-5">导出小说</h3>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-neutral-700 mb-1.5">导出格式</label>
            <div class="flex gap-2">
              <button v-for="f in formats" :key="f.value"
                @click="form.format = f.value"
                class="flex-1 py-2 px-3 rounded-lg text-sm font-medium border transition-all"
                :class="form.format === f.value ? 'bg-accent-50 border-accent-300 text-accent-700' : 'border-neutral-200 text-neutral-600 hover:border-neutral-300'"
              >{{ f.label }}</button>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-neutral-700 mb-1.5">导出范围</label>
            <select v-model="form.scope" class="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm focus:border-accent-400 focus:ring-1 focus:ring-accent-400 outline-none">
              <option value="full">全书</option>
              <option value="volume">按卷</option>
              <option value="range">按章节范围</option>
            </select>
          </div>

          <div v-if="form.scope === 'volume'">
            <label class="block text-sm font-medium text-neutral-700 mb-1.5">选择卷</label>
            <select v-model="form.volume_number" class="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm focus:border-accent-400 focus:ring-1 focus:ring-accent-400 outline-none">
              <option v-for="v in volumes" :key="v.volume_number" :value="v.volume_number">
                第{{ v.volume_number }}卷{{ v.title ? ' - ' + v.title : '' }}
              </option>
            </select>
          </div>

          <div v-if="form.scope === 'range'" class="flex gap-3">
            <div class="flex-1">
              <label class="block text-sm font-medium text-neutral-700 mb-1.5">起始章</label>
              <input v-model.number="form.chapter_start" type="number" min="1" class="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm focus:border-accent-400 outline-none" />
            </div>
            <div class="flex-1">
              <label class="block text-sm font-medium text-neutral-700 mb-1.5">结束章</label>
              <input v-model.number="form.chapter_end" type="number" min="1" class="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm focus:border-accent-400 outline-none" />
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-neutral-700 mb-1.5">排版模板</label>
            <select v-model="form.template" class="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm focus:border-accent-400 focus:ring-1 focus:ring-accent-400 outline-none">
              <option value="default">通用模板</option>
              <option value="qidian">起点中文网</option>
              <option value="fanqie">番茄小说</option>
              <option value="custom">自定义</option>
            </select>
          </div>
        </div>

        <div class="flex gap-3 justify-end mt-6 pt-4 border-t border-neutral-100">
          <button @click="$emit('close')" class="px-4 py-2 text-sm font-medium text-neutral-600 hover:text-neutral-800 rounded-lg hover:bg-neutral-100 transition-colors">
            取消
          </button>
          <button @click="doExport" :disabled="exporting" class="px-5 py-2 text-sm font-semibold text-white bg-accent-600 hover:bg-accent-700 rounded-lg transition-colors disabled:opacity-50">
            {{ exporting ? '导出中...' : '导出' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive } from 'vue'

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
