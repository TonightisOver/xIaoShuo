<template>
  <div class="relative py-2 pl-6">
    <div class="absolute bottom-4 left-2.5 top-4 w-px bg-neutral-200"></div>

    <div v-if="versions.length === 0" class="py-6 text-center text-xs text-neutral-400">
      暂无版本记录
    </div>

    <div v-for="version in versions" :key="version.version_number" class="relative pb-4 last:pb-0">
      <div
        class="absolute -left-[19px] top-3 h-3 w-3 rounded-full border-2 bg-white transition-colors"
        :class="isActive(version)
          ? 'border-accent-600 bg-accent-600 ring-4 ring-accent-100'
          : 'border-neutral-300'"
      ></div>

      <button
        type="button"
        class="w-full rounded-lg border p-3 text-left transition-colors"
        :class="isActive(version)
          ? 'border-accent-200 bg-accent-50 shadow-sm'
          : 'border-neutral-200 bg-white hover:border-neutral-300 hover:bg-neutral-50'"
        @click="emit('preview', version)"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold text-neutral-900">v{{ version.version_number }}</span>
              <span
                v-if="isActive(version)"
                class="rounded-full bg-accent-100 px-1.5 py-0.5 text-[10px] font-semibold text-accent-700"
              >
                当前
              </span>
            </div>
            <div class="mt-1 text-[11px] text-neutral-500">{{ formatDate(version.created_at) }}</div>
          </div>

          <span
            class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
            :class="sourceClass(version.source)"
          >
            {{ sourceLabel(version.source) }}
          </span>
        </div>

        <div class="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-neutral-500">
          <span>{{ formatNumber(version.word_count) }} 字</span>
          <span v-if="version.quality_score != null" class="font-semibold text-amber-600">
            评分 {{ formatScore(version.quality_score) }}
          </span>
          <span v-if="version.model_name" class="truncate text-neutral-400">{{ version.model_name }}</span>
        </div>

        <div
          v-if="version.rewrite_instruction || version.user_notes"
          class="mt-2 line-clamp-2 rounded-md border border-neutral-100 bg-white/70 px-2 py-1.5 text-[11px] leading-relaxed text-neutral-500"
        >
          {{ version.rewrite_instruction || version.user_notes }}
        </div>
      </button>

      <div v-if="!isActive(version)" class="mt-2 flex justify-end gap-2">
        <button
          type="button"
          class="rounded-md border border-accent-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-accent-600 transition-colors hover:bg-accent-50"
          @click="emit('activate', version.version_number)"
        >
          激活
        </button>
        <button
          type="button"
          class="rounded-md bg-accent-600 px-2.5 py-1 text-[11px] font-semibold text-white transition-colors hover:bg-accent-700"
          @click="emit('rollback', version.version_number)"
        >
          回滚
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { formatDate, formatNumber, sourceClass, sourceLabel } from '../utils/versionHelpers.js'

const props = defineProps({
  versions: {
    type: Array,
    default: () => [],
  },
  currentVersion: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits(['preview', 'activate', 'rollback'])

function isActive(version) {
  if (props.currentVersion != null) {
    return version.version_number === props.currentVersion
  }
  return Boolean(version.is_active)
}

function formatScore(value) {
  const score = Number(value)
  if (Number.isNaN(score)) return value
  return score.toFixed(1)
}
</script>
