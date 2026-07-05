<template>
  <div>
    <div class="flex items-center justify-between mb-1">
      <span class="text-sm text-neutral-600">{{ percentage }}%</span>
    </div>
    <div class="h-2 bg-neutral-200 rounded-full overflow-hidden">
      <div
        class="h-full bg-gradient-to-r from-accent-500 to-accent-400 rounded-full transition-all duration-500"
        :style="{ width: percentage + '%' }"
      ></div>
    </div>
  </div>
</template>

<script setup>
defineProps({ percentage: { type: Number, default: 0 } })
</script>
