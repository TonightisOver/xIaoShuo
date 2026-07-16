<template>
  <div
    ref="textContainer"
    class="relative overflow-y-auto max-h-[480px] rounded-xl border border-ink-200 bg-paper-50 p-5 scroll-smooth"
  >
    <pre class="whitespace-pre-wrap break-words text-sm md:text-[15px] leading-relaxed font-serif text-ink-700 m-0">{{ text }}<span
      v-if="isStreaming"
      class="inline-block w-[2px] h-[1.1em] bg-vermilion-500 align-middle ml-0.5 animate-blink"
    ></span></pre>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  isStreaming: { type: Boolean, default: false },
})

const textContainer = ref(null)

watch(
  () => props.text,
  () => {
    nextTick(() => {
      if (textContainer.value) {
        textContainer.value.scrollTop = textContainer.value.scrollHeight
      }
    })
  }
)
</script>

<style scoped>
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.animate-blink {
  animation: blink 1s step-end infinite;
}
</style>
