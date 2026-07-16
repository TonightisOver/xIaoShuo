<template>
  <!-- AI 改写 Modal -->
  <Teleport to="body">
    <div v-if="showRewriteModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="$emit('close-rewrite')">
      <div class="bg-paper-50 border border-ink-200 rounded-xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden text-ink-600 animate-fade-up">
        <div class="px-6 py-4 border-b border-ink-200 flex items-center justify-between">
          <h3 class="text-sm font-semibold flex items-center gap-2 text-vermilion-500 heading-serif">AI 改写</h3>
          <button @click="$emit('close-rewrite')" class="text-ink-400 hover:text-ink-600 transition-colors text-lg leading-none">✕</button>
        </div>
        <div v-if="!rewriteResult" class="p-6 space-y-4">
          <div>
            <div class="text-xs font-semibold text-ink-400 mb-2">选中文本预览</div>
            <div class="bg-paper-100 rounded-xl px-4 py-3 text-sm text-ink-500 leading-relaxed border border-ink-200 line-clamp-3">
              {{ selectionText.length > 100 ? selectionText.slice(0, 100) + '...' : selectionText }}
            </div>
          </div>
          <div>
            <div class="text-xs font-semibold text-ink-400 mb-2">改写指令</div>
            <textarea :value="rewriteInstruction" @input="$emit('update:rewrite-instruction', $event.target.value)" class="w-full bg-paper-100 border border-ink-200 focus:border-vermilion-500 rounded-xl p-3 text-sm text-ink-600 resize-none outline-none" rows="3" placeholder="例如：改成更有张力的描写、增加环境渲染、调整节奏使其更紧凑..."></textarea>
          </div>
          <div v-if="rewriteError" class="text-xs text-rose-400 bg-rose-950/20 border border-rose-900 rounded-lg px-3 py-2">{{ rewriteError }}</div>
          <div class="flex justify-end gap-3">
            <button @click="$emit('close-rewrite')" class="px-4 py-2 border border-ink-200 hover:bg-paper-100 rounded-lg text-sm text-ink-600 transition-colors">取消</button>
            <button @click="$emit('do-rewrite')" :disabled="rewriting || !rewriteInstruction.trim()" class="btn-primary px-5 py-2 text-white rounded-lg text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
              <svg v-if="rewriting" class="w-4 h-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
              <span>{{ rewriting ? '生成中...' : '生成改写' }}</span>
            </button>
          </div>
        </div>
        <div v-else class="p-6 space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <div class="text-xs font-semibold text-ink-400 mb-2">原文</div>
              <div class="bg-paper-100 rounded-xl px-4 py-3 text-sm text-ink-500 leading-relaxed border border-ink-200 max-h-48 overflow-y-auto custom-scrollbar">{{ rewriteResult.original }}</div>
            </div>
            <div>
              <div class="text-xs font-semibold text-vermilion-500 mb-2">AI 改写结果</div>
              <div class="bg-paper-100 rounded-xl px-4 py-3 text-sm text-ink-600 leading-relaxed border border-vermilion-200 max-h-48 overflow-y-auto custom-scrollbar">{{ rewriteResult.rewritten }}</div>
            </div>
          </div>
          <div v-if="rewriteError" class="text-xs text-rose-400 bg-rose-950/20 border border-rose-900 rounded-lg px-3 py-2">{{ rewriteError }}</div>
          <div class="flex justify-end gap-3">
            <button @click="$emit('reset-rewrite')" class="px-4 py-2 border border-ink-200 hover:bg-paper-100 text-ink-600 rounded-lg text-sm transition-colors">重新生成</button>
            <button @click="$emit('close-rewrite')" class="px-4 py-2 border border-ink-200 hover:bg-paper-100 text-ink-600 rounded-lg text-sm transition-colors">放弃</button>
            <button @click="$emit('accept-rewrite')" class="btn-primary px-5 py-2 text-white rounded-lg text-sm font-semibold transition-colors">采纳改写</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- 版本预览 Modal -->
  <Teleport to="body">
    <div v-if="previewVersionData" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="closePreview">
      <div class="bg-paper-50 border border-ink-200 rounded-xl shadow-xl w-full max-w-3xl mx-4 overflow-hidden text-ink-600 animate-fade-up">
        <div class="px-6 py-4 border-b border-ink-200 flex items-center justify-between">
          <h3 class="text-sm font-semibold heading-serif">版本 v{{ previewVersionData.version_number }} 预览</h3>
          <button @click="closePreview" class="text-ink-400 hover:text-ink-600 transition-colors text-lg leading-none">✕</button>
        </div>
        <div class="p-6 space-y-4">
          <div class="flex items-center justify-between text-xs text-ink-400">
            <div class="flex items-center gap-3">
              <span class="px-2 py-0.5 rounded-full font-medium" :class="{ 'bg-sky-50 text-sky-700 border border-sky-200': previewVersionData.source === 'ai_rewrite', 'bg-amber-50 text-amber-700 border border-amber-200': previewVersionData.source === 'rollback', 'bg-ink-100 text-ink-500 border border-ink-200': previewVersionData.source === 'manual', 'bg-emerald-50 text-emerald-700 border border-emerald-200': previewVersionData.source === 'generation' }">{{ sourceLabel(previewVersionData.source) }}</span>
              <span>{{ previewVersionData.word_count }} 字</span>
              <span>{{ formatDate(previewVersionData.created_at) }}</span>
              <span v-if="previewVersionData.quality_score" class="text-amber-400 font-semibold">★ {{ previewVersionData.quality_score.toFixed(1) }}</span>
              <span v-if="previewVersionData.model_name" class="text-ink-400">{{ previewVersionData.model_name }}</span>
            </div>
            <button @click="showDiff = !showDiff" class="px-2.5 py-1 bg-paper-100 border border-ink-200 hover:bg-paper-100 rounded text-vermilion-500 text-xs font-semibold transition-colors">
              {{ showDiff ? '显示纯文本' : '对比当前编辑器版本 (Diff)' }}
            </button>
          </div>

          <!-- Plain text preview -->
          <div v-if="!showDiff" class="bg-paper-100 rounded-xl px-4 py-3 text-sm text-ink-500 leading-relaxed border border-ink-200 max-h-80 overflow-y-auto custom-scrollbar whitespace-pre-wrap">{{ previewVersionData.content }}</div>

          <!-- Diff preview -->
          <div v-else class="bg-paper-100 rounded-xl border border-ink-200 max-h-80 overflow-y-auto custom-scrollbar text-xs font-mono p-4 space-y-1 leading-relaxed">
            <div
              v-for="(line, idx) in diffLines"
              :key="idx"
              :class="[
                'px-2 py-0.5 rounded whitespace-pre-wrap',
                line.type === 'added' ? 'bg-emerald-950/40 text-emerald-400 border-l-2 border-emerald-500' :
                line.type === 'removed' ? 'bg-rose-950/40 text-rose-400 border-l-2 border-rose-500' : 'text-ink-400'
              ]"
            >
              {{ line.type === 'added' ? '+ ' : line.type === 'removed' ? '- ' : '  ' }}{{ line.text }}
            </div>
          </div>

          <div class="flex justify-end gap-3">
            <button @click="closePreview" class="px-4 py-2 border border-ink-200 hover:bg-paper-100 text-ink-600 rounded-lg text-sm transition-colors">关闭</button>
            <button @click="$emit('activate', previewVersionData.version_number)" class="px-4 py-2 border border-vermilion-200 text-vermilion-500 hover:bg-vermilion-50 rounded-lg text-sm font-semibold transition-colors">设为正式版本</button>
            <button @click="$emit('rollback', previewVersionData.version_number)" class="btn-primary px-5 py-2 text-white rounded-lg text-sm font-semibold transition-colors">回滚到此版本</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { computeLineDiff } from '../utils/diff.js'

const props = defineProps({
  showRewriteModal: Boolean,
  rewriteInstruction: String,
  rewriting: Boolean,
  rewriteResult: Object,
  rewriteError: String,
  selectionText: String,
  previewVersionData: Object,
  activeContent: String, // Active content of the editor to perform diff comparison
})

const emit = defineEmits([
  'close-rewrite', 'do-rewrite', 'accept-rewrite', 'reset-rewrite',
  'update:rewrite-instruction',
  'close-preview', 'rollback', 'activate',
])

const showDiff = ref(false)

const diffLines = computed(() => {
  if (!props.previewVersionData || !props.activeContent) return []
  // Diff historical version (as new state) against active editor content (as old state)
  return computeLineDiff(props.activeContent, props.previewVersionData.content)
})

const closePreview = () => {
  showDiff.value = false
  emit('close-preview')
}

// Reset diff toggle when preview data changes
watch(() => props.previewVersionData, () => {
  showDiff.value = false
})

function sourceLabel(source) {
  return { manual: '手动', ai_rewrite: 'AI改写', rollback: '回滚', generation: '生成' }[source] || source
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 9999px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
</style>
