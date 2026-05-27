<template>
  <!-- AI 改写 Modal -->
  <Teleport to="body">
    <div v-if="showRewriteModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="$emit('close-rewrite')">
      <div class="bg-white border border-neutral-200 rounded-xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden">
        <div class="px-6 py-4 border-b border-neutral-200 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-neutral-800 flex items-center gap-2">AI 改写</h3>
          <button @click="$emit('close-rewrite')" class="text-neutral-400 hover:text-neutral-600 transition-colors text-lg leading-none">✕</button>
        </div>
        <div v-if="!rewriteResult" class="p-6 space-y-4">
          <div>
            <div class="text-xs font-semibold text-neutral-500 mb-2">选中文本预览</div>
            <div class="bg-neutral-50 rounded-xl px-4 py-3 text-sm text-neutral-700 leading-relaxed border border-neutral-200 line-clamp-3">
              {{ selectionText.length > 100 ? selectionText.slice(0, 100) + '...' : selectionText }}
            </div>
          </div>
          <div>
            <div class="text-xs font-semibold text-neutral-500 mb-2">改写指令</div>
            <textarea :value="rewriteInstruction" @input="$emit('update:rewrite-instruction', $event.target.value)" class="input w-full resize-none" rows="3" placeholder="例如：改成更有张力的描写、增加环境渲染、调整节奏使其更紧凑..."></textarea>
          </div>
          <div v-if="rewriteError" class="text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{{ rewriteError }}</div>
          <div class="flex justify-end gap-3">
            <button @click="$emit('close-rewrite')" class="btn-secondary text-sm px-4 py-2">取消</button>
            <button @click="$emit('do-rewrite')" :disabled="rewriting || !rewriteInstruction.trim()" class="btn-primary text-sm px-5 py-2 flex items-center gap-2">
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
              <div class="text-xs font-semibold text-neutral-500 mb-2">原文</div>
              <div class="bg-neutral-50 rounded-xl px-4 py-3 text-sm text-neutral-600 leading-relaxed border border-neutral-200 max-h-48 overflow-y-auto custom-scrollbar">{{ rewriteResult.original }}</div>
            </div>
            <div>
              <div class="text-xs font-semibold text-accent-600 mb-2">AI 改写结果</div>
              <div class="bg-accent-50 rounded-xl px-4 py-3 text-sm text-neutral-800 leading-relaxed border border-accent-200 max-h-48 overflow-y-auto custom-scrollbar">{{ rewriteResult.rewritten }}</div>
            </div>
          </div>
          <div v-if="rewriteError" class="text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{{ rewriteError }}</div>
          <div class="flex justify-end gap-3">
            <button @click="$emit('reset-rewrite')" class="btn-secondary text-sm px-4 py-2">重新生成</button>
            <button @click="$emit('close-rewrite')" class="btn-secondary text-sm px-4 py-2">放弃</button>
            <button @click="$emit('accept-rewrite')" class="btn-primary text-sm px-5 py-2">采纳改写</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- 版本预览 Modal -->
  <Teleport to="body">
    <div v-if="previewVersionData" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="$emit('close-preview')">
      <div class="bg-white border border-neutral-200 rounded-xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden">
        <div class="px-6 py-4 border-b border-neutral-200 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-neutral-800">版本 v{{ previewVersionData.version_number }} 预览</h3>
          <button @click="$emit('close-preview')" class="text-neutral-400 hover:text-neutral-600 transition-colors text-lg leading-none">✕</button>
        </div>
        <div class="p-6 space-y-4">
          <div class="flex items-center gap-3 text-xs text-neutral-500">
            <span class="px-2 py-0.5 rounded-full font-medium" :class="{ 'bg-blue-50 text-blue-700': previewVersionData.source === 'ai_rewrite', 'bg-amber-50 text-amber-700': previewVersionData.source === 'rollback', 'bg-neutral-100 text-neutral-600': previewVersionData.source === 'manual', 'bg-emerald-50 text-emerald-700': previewVersionData.source === 'generation' }">{{ sourceLabel(previewVersionData.source) }}</span>
            <span>{{ previewVersionData.word_count }} 字</span>
            <span>{{ formatDate(previewVersionData.created_at) }}</span>
            <span v-if="previewVersionData.quality_score" class="text-amber-600">★ {{ previewVersionData.quality_score.toFixed(1) }}</span>
            <span v-if="previewVersionData.model_name" class="text-neutral-400">{{ previewVersionData.model_name }}</span>
          </div>
          <div class="bg-neutral-50 rounded-xl px-4 py-3 text-sm text-neutral-700 leading-relaxed border border-neutral-200 max-h-64 overflow-y-auto custom-scrollbar whitespace-pre-wrap">{{ previewVersionData.content }}</div>
          <div class="flex justify-end gap-3">
            <button @click="$emit('close-preview')" class="btn-secondary text-sm px-4 py-2">关闭</button>
            <button @click="$emit('activate', previewVersionData.version_number)" class="btn-secondary text-sm px-4 py-2 border-accent-200 text-accent-600 hover:bg-accent-50">设为正式版本</button>
            <button @click="$emit('rollback', previewVersionData.version_number)" class="btn-primary text-sm px-5 py-2">回滚到此版本</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  showRewriteModal: Boolean,
  rewriteInstruction: String,
  rewriting: Boolean,
  rewriteResult: Object,
  rewriteError: String,
  selectionText: String,
  previewVersionData: Object,
})

defineEmits([
  'close-rewrite', 'do-rewrite', 'accept-rewrite', 'reset-rewrite',
  'update:rewrite-instruction',
  'close-preview', 'rollback', 'activate',
])

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
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.1); border-radius: 9999px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(0, 0, 0, 0.2); }
</style>
