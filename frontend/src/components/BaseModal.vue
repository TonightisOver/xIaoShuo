<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="onCancel">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/20 backdrop-blur-sm"></div>
      <!-- Modal -->
      <div class="relative bg-paper-50 rounded-xl shadow-xl w-full max-w-md mx-4 border border-ink-200 overflow-hidden animate-fade-up">
        <!-- Header -->
        <div v-if="title" class="px-6 py-4 border-b border-ink-200 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-ink-700 flex items-center gap-2 heading-serif">
            <slot name="title-icon"></slot>
            {{ title }}
          </h3>
          <button
            v-if="closable"
            @click="onCancel"
            class="text-ink-400 hover:text-ink-600 transition-colors p-1 rounded-lg hover:bg-paper-100"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <!-- Body -->
        <div class="px-6 py-5">
          <slot />
        </div>
        <!-- Footer -->
        <div v-if="$slots.footer" class="px-6 py-4 border-t border-ink-200 flex justify-end gap-3">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  closable: { type: Boolean, default: true },
})

const emit = defineEmits(['cancel', 'confirm'])

function onCancel() {
  if (props.closable) {
    emit('cancel')
  }
}
</script>
