<template>
  <div class="flex flex-col h-full">
    <div v-if="!workspace || !workspace.blueprint" class="flex-1 flex items-center justify-center p-8">
      <div class="text-center space-y-3">
        <p class="text-ink-400 text-sm">该章节尚无蓝图</p>
        <button @click="$emit('generate', selectedChapter)" data-generate-btn class="btn-primary text-sm">生成蓝图</button>
      </div>
    </div>
    <div v-else class="flex-1 overflow-auto p-4 space-y-4">
      <!-- 状态条 -->
      <div class="flex items-center justify-between text-xs text-ink-500">
        <div class="flex items-center gap-2">
          <span>版本 {{ workspace.control?.version ?? '—' }}</span>
          <span class="text-ink-300">|</span>
          <span>{{ statusLabel }}</span>
          <span v-if="locked" class="text-vermilion-600">·已锁定</span>
        </div>
        <span>{{ updatedAt }}</span>
      </div>

      <!-- 冲突提示 -->
      <div v-if="conflict" class="p-3 rounded-lg bg-vermilion-50 border border-vermilion-200 text-sm">
        <p class="text-vermilion-700 font-medium">版本冲突：服务端已更新到 v{{ conflict.current_version }}</p>
        <p class="text-ink-500 mt-1">本地草稿已保留，可刷新、比较或重新应用修改。</p>
        <div class="flex gap-2 mt-2">
          <button @click="$emit('discard')" class="btn-secondary text-xs">丢弃草稿</button>
          <button @click="$emit('refresh')" class="btn-secondary text-xs">刷新版本</button>
        </div>
      </div>

      <!-- dirty 提示 -->
      <div v-if="dirty" class="text-xs text-amber-600">有未保存修改</div>

      <div class="grid grid-cols-2 gap-4">
        <label class="block">
          <span class="text-xs text-ink-500">章节类型</span>
          <select v-model="localChapterType" :disabled="readonly"
                  @change="onUpdate('chapter_type', localChapterType)"
                  data-field-chapter_type class="input text-sm w-full">
            <option v-for="o in options.chapter_type" :key="o" :value="o">{{ o }}</option>
          </select>
        </label>
        <label class="block">
          <span class="text-xs text-ink-500">节奏</span>
          <select v-model="localPacing" :disabled="readonly"
                  @change="onUpdate('pacing_target', localPacing)"
                  data-field-pacing_target class="input text-sm w-full">
            <option v-for="o in options.pacing_target" :key="o" :value="o">{{ o }}</option>
          </select>
        </label>
      </div>

      <label class="block">
        <span class="text-xs text-ink-500">情节目标</span>
        <textarea v-model="localPlotGoal" :disabled="readonly"
                  @input="onUpdate('plot_goal', localPlotGoal)"
                  data-field-plot_goal rows="2" class="input text-sm w-full"></textarea>
      </label>

      <label class="block">
        <span class="text-xs text-ink-500">钩子设计</span>
        <textarea v-model="localHook" :disabled="readonly"
                  @input="onUpdate('hook_design', localHook)" rows="2"
                  class="input text-sm w-full"></textarea>
      </label>

      <!-- foreshadow_actions 列表编辑器 -->
      <div>
        <span class="text-xs text-ink-500">伏笔动作</span>
        <div v-for="(fa, idx) in localForeshadow" :key="idx" class="flex gap-2 mt-1">
          <select v-model="fa.action" :disabled="readonly" data-foreshadow-action
                  class="input text-sm flex-1">
            <option v-for="o in options.foreshadow_action" :key="o" :value="o">{{ o }}</option>
          </select>
          <input v-model="fa.target" :disabled="readonly" placeholder="对象"
                 class="input text-sm flex-1" />
          <button @click="removeForeshadow(idx)" :disabled="readonly"
                  class="btn-secondary text-xs">删</button>
        </div>
        <button @click="addForeshadow" :disabled="readonly"
                data-add-foreshadow class="btn-secondary text-xs mt-1">+ 添加伏笔</button>
      </div>

      <label class="block">
        <span class="text-xs text-ink-500">悬念结尾</span>
        <textarea v-model="localCliffhanger" :disabled="readonly"
                  @input="onUpdate('cliffhanger', localCliffhanger)" rows="2"
                  class="input text-sm w-full"></textarea>
      </label>

      <!-- key_characters 多选 -->
      <div>
        <span class="text-xs text-ink-500">关键角色</span>
        <div class="flex flex-wrap gap-2 mt-1">
          <label v-for="c in availableCharacters" :key="c.id"
                 class="flex items-center gap-1 text-xs text-ink-600">
            <input type="checkbox" :value="c.name" :checked="localKeyChars.includes(c.name)"
                   :disabled="readonly" @change="toggleChar($event, c.name)" />
            {{ c.name }}
          </label>
        </div>
      </div>

      <label class="block">
        <span class="text-xs text-ink-500">目标字数</span>
        <input type="number" v-model.number="localWordTarget" :disabled="readonly"
               @change="onUpdate('word_target', localWordTarget)" min="2000" max="6000"
               data-field-word_target class="input text-sm w-full" />
      </label>

      <div class="flex gap-2 pt-2">
        <button @click="onSave" :disabled="readonly || saving || !dirty"
                data-save-btn class="btn-primary text-sm flex-1">保存</button>
        <button @click="$emit('discard')" :disabled="!dirty" class="btn-secondary text-sm">放弃</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  workspace: { type: Object, default: null },
  options: { type: Object, default: () => ({ chapter_type: [], pacing_target: [], foreshadow_action: [] }) },
  draft: { type: Object, default: null },
  dirty: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  conflict: { type: Object, default: null },
  selectedChapter: { type: [Number, null], default: null },
})
const emit = defineEmits(['update', 'save', 'discard', 'refresh', 'generate'])

const locked = computed(() => props.workspace?.control?.locked)
const readonly = computed(() => !!locked.value)
const statusLabel = computed(() => props.workspace?.control?.control_status || '—')
const updatedAt = computed(() => props.workspace?.blueprint?.updated_at || '—')
const availableCharacters = computed(() => props.workspace?.available_characters || [])

// 本地表单状态（跟随 draft）
const localChapterType = ref('')
const localPacing = ref('')
const localPlotGoal = ref('')
const localHook = ref('')
const localCliffhanger = ref('')
const localWordTarget = ref(3000)
const localForeshadow = ref([])
const localKeyChars = ref([])

watch(() => props.draft, (d) => {
  if (!d) return
  localChapterType.value = d.chapter_type || ''
  localPacing.value = d.pacing_target || ''
  localPlotGoal.value = d.plot_goal || ''
  localHook.value = d.hook_design || ''
  localCliffhanger.value = d.cliffhanger || ''
  localWordTarget.value = d.word_target || 3000
  localForeshadow.value = (d.foreshadow_actions || []).map(fa =>
    typeof fa === 'string' ? { action: '', target: fa } : { action: fa.action || '', target: fa.target || '' }
  )
  localKeyChars.value = [...(d.key_characters || [])]
}, { immediate: true, deep: true })

function onUpdate(field, value) { emit('update', field, value) }
function onSave() { emit('save') }
function addForeshadow() {
  localForeshadow.value.push({ action: '', target: '' })
  emit('update', 'foreshadow_actions', localForeshadow.value.map(f => ({ action: f.action, target: f.target })))
}
function removeForeshadow(idx) {
  localForeshadow.value.splice(idx, 1)
  emit('update', 'foreshadow_actions', localForeshadow.value.map(f => ({ action: f.action, target: f.target })))
}
function toggleChar(e, name) {
  const next = new Set(localKeyChars.value)
  if (e.target.checked) next.add(name); else next.delete(name)
  localKeyChars.value = [...next]
  emit('update', 'key_characters', localKeyChars.value)
}
</script>
