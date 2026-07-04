<template>
  <div v-if="visible" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-white rounded-xl p-6 w-80 shadow-xl">
      <h3 class="font-bold text-neutral-900 mb-4">按范围生成章节</h3>
      <div class="space-y-3">
        <div>
          <label class="text-sm text-neutral-600">起始章节</label>
          <input type="number" v-model.number="start" min="1" class="input mt-1" />
        </div>
        <div>
          <label class="text-sm text-neutral-600">结束章节</label>
          <input type="number" v-model.number="end" :min="start" class="input mt-1" />
        </div>
      </div>
      <div class="flex gap-3 mt-5">
        <button @click="submit" class="btn-primary flex-1" :disabled="!valid">开始生成</button>
        <button @click="$emit('close')" class="btn-secondary flex-1">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

defineProps({ visible: Boolean })
const emit = defineEmits(['close', 'generate'])

const start = ref(1)
const end = ref(3)

const valid = computed(() => start.value >= 1 && end.value >= start.value)

function submit() {
  if (valid.value) {
    emit('generate', { chapter_start: start.value, chapter_end: end.value })
  }
}
</script>
