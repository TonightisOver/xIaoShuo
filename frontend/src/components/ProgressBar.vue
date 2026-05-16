<template>
  <div>
    <div class="flex items-center justify-between mb-1">
      <span class="text-sm text-ink-600">{{ percentage }}%</span>
    </div>
    <div class="h-2 bg-ink-200 rounded-full overflow-hidden">
      <div
        class="h-full bg-gradient-to-r from-primary-500 to-primary-400 rounded-full transition-all duration-500"
        :style="{ width: percentage + '%' }"
      ></div>
    </div>
  </div>
</template>

<script setup>
defineProps({ percentage: { type: Number, default: 0 } })
</script>
