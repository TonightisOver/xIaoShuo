<template>
  <div class="fixed inset-0 z-50 overflow-y-auto transition-all duration-300 custom-scrollbar-read" :class="[themeClasses[activeTheme]]">
    <div class="max-w-3xl mx-auto px-6 py-20 relative min-h-screen flex flex-col justify-between">
      <div>
        <div class="flex items-center justify-between pb-6 mb-12 border-b" :class="[activeTheme === 'dark' ? 'border-white/10' : 'border-black/5']">
          <span class="text-xs opacity-60 tracking-wider font-semibold">正在沉浸阅读《{{ chapter.novel?.title || '小说创作' }}》</span>
          <button @click="$emit('exit')" class="text-xs font-bold px-3 py-1 rounded-full border hover:scale-105 active:scale-95 transition-all" :class="[activeTheme === 'dark' ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5']">
            切换到编辑模式
          </button>
        </div>
        <h1 class="text-3xl md:text-4xl font-extrabold mb-10 text-center tracking-tight" :class="[activeFont === 'serif' ? 'font-serif' : 'font-sans']">
          {{ chapter.volume_number ? `第${chapter.volume_number}卷 · ` : '' }}第{{ chapter.chapter_number }}章：{{ chapter.title }}
        </h1>
        <div class="leading-loose tracking-wide whitespace-pre-line text-justify select-text focus:outline-none" :class="[activeFont === 'serif' ? 'font-serif' : 'font-sans']" :style="{ fontSize: fontSize + 'px', lineHeight: '2.0' }">
          {{ content }}
        </div>
      </div>
      <div class="flex items-center justify-between gap-6 mt-20 pt-8 border-t" :class="[activeTheme === 'dark' ? 'border-white/10' : 'border-black/5']">
        <button v-if="prevChapter" @click="$emit('go-to-chapter', prevChapter.chapter_number)" class="flex-1 py-4 px-6 rounded-2xl border text-sm font-semibold flex items-center justify-center gap-2 transition-all hover:scale-[1.02] active:scale-[0.98]" :class="[activeTheme === 'dark' ? 'border-white/10 hover:bg-white/5 text-slate-300' : 'border-black/10 hover:bg-black/5 text-slate-700']">← 上一章</button>
        <span v-else class="flex-1 text-center text-xs opacity-40 font-semibold py-4">已是第一章</span>
        <button v-if="nextChapter" @click="$emit('go-to-chapter', nextChapter.chapter_number)" class="flex-1 py-4 px-6 rounded-2xl border text-sm font-semibold flex items-center justify-center gap-2 transition-all hover:scale-[1.02] active:scale-[0.98]" :class="[activeTheme === 'dark' ? 'border-white/10 hover:bg-white/5 text-slate-300' : 'border-black/10 hover:bg-black/5 text-slate-700']">下一章 →</button>
        <span v-else class="flex-1 text-center text-xs opacity-40 font-semibold py-4">已是最后一章</span>
      </div>
    </div>

    <!-- 悬浮排版控制面板 -->
    <div class="fixed right-6 bottom-10 z-50 flex flex-col items-end gap-3">
      <div v-if="showSettings" class="bg-white rounded-xl border border-neutral-200 shadow-lg p-5 flex flex-col gap-4 w-72" :class="[activeTheme === 'dark' ? 'bg-neutral-900 text-slate-200 border-neutral-700' : '']">
        <div class="flex items-center justify-between border-b pb-2" :class="[activeTheme === 'dark' ? 'border-neutral-700' : 'border-neutral-200']">
          <span class="text-xs font-bold tracking-wider text-neutral-700">排版个性化设置</span>
          <button @click="$emit('update:show-settings', false)" class="text-xs text-neutral-400 hover:text-neutral-600">✕ 关闭</button>
        </div>
        <div class="flex flex-col gap-1.5">
          <span class="text-[11px] text-neutral-500 font-semibold">字号大小</span>
          <div class="flex items-center justify-between gap-2">
            <button @click="$emit('adjust-font-size', -2)" class="flex-1 py-1.5 rounded-lg border text-center font-bold text-sm transition-all border-neutral-200 hover:bg-neutral-50">A -</button>
            <span class="text-xs font-mono font-bold w-12 text-center text-neutral-700">{{ fontSize }}px</span>
            <button @click="$emit('adjust-font-size', 2)" class="flex-1 py-1.5 rounded-lg border text-center font-bold text-sm transition-all border-neutral-200 hover:bg-neutral-50">A +</button>
          </div>
        </div>
        <div class="flex flex-col gap-1.5">
          <span class="text-[11px] text-neutral-500 font-semibold">阅读字体</span>
          <div class="flex gap-2">
            <button @click="$emit('update:active-font', 'serif')" class="flex-1 py-1.5 rounded-lg border text-xs transition-all" :class="[activeFont === 'serif' ? 'border-accent-500 bg-accent-50 text-accent-700 font-bold' : 'border-neutral-200']">宋体 / 衬线</button>
            <button @click="$emit('update:active-font', 'sans')" class="flex-1 py-1.5 rounded-lg border text-xs transition-all" :class="[activeFont === 'sans' ? 'border-accent-500 bg-accent-50 text-accent-700 font-bold' : 'border-neutral-200']">系统 / 无衬线</button>
          </div>
        </div>
        <div class="flex flex-col gap-1.5">
          <span class="text-[11px] text-neutral-500 font-semibold">背景配色</span>
          <div class="grid grid-cols-4 gap-2">
            <button @click="$emit('update:active-theme', 'parchment')" class="h-9 rounded-lg border-2 flex items-center justify-center transition-all bg-[#f4ecd8] border-amber-900/10 relative" :class="[activeTheme === 'parchment' ? 'border-amber-600 scale-105' : '']" title="仿古羊皮纸"><span v-if="activeTheme === 'parchment'" class="text-xs">🌾</span></button>
            <button @click="$emit('update:active-theme', 'green')" class="h-9 rounded-lg border-2 flex items-center justify-center transition-all bg-[#dfedd6] border-emerald-900/10 relative" :class="[activeTheme === 'green' ? 'border-emerald-600 scale-105' : '']" title="温润护眼绿"><span v-if="activeTheme === 'green'" class="text-xs">🍃</span></button>
            <button @click="$emit('update:active-theme', 'dark')" class="h-9 rounded-lg border-2 flex items-center justify-center transition-all bg-[#0b0e14] border-slate-900 relative" :class="[activeTheme === 'dark' ? 'border-blue-500 scale-105' : '']" title="黑夜寂静"><span v-if="activeTheme === 'dark'" class="text-xs">🌌</span></button>
            <button @click="$emit('update:active-theme', 'white')" class="h-9 rounded-lg border-2 flex items-center justify-center transition-all bg-[#ffffff] border-slate-200 relative" :class="[activeTheme === 'white' ? 'border-slate-800 scale-105' : '']" title="极简雪花白"><span v-if="activeTheme === 'white'" class="text-xs">❄</span></button>
          </div>
        </div>
      </div>
      <button @click="$emit('update:show-settings', !showSettings)" class="w-12 h-12 rounded-full shadow-lg flex items-center justify-center text-xl transition-all active:scale-95 bg-accent-600 text-white hover:bg-accent-700">⚙</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  chapter: Object,
  content: String,
  prevChapter: Object,
  nextChapter: Object,
  activeTheme: String,
  activeFont: String,
  fontSize: Number,
  showSettings: Boolean,
})

const themeClasses = {
  parchment: 'bg-[#f4ecd8] text-[#3c2f1f]',
  green: 'bg-[#dfedd6] text-[#2c3d27]',
  dark: 'bg-[#0d0f14] text-[#a8b0c2]',
  white: 'bg-[#ffffff] text-[#111111]',
}

defineEmits(['exit', 'go-to-chapter', 'adjust-font-size', 'update:active-font', 'update:active-theme', 'update:show-settings'])
</script>

<style scoped>
.custom-scrollbar-read::-webkit-scrollbar { width: 8px; }
.custom-scrollbar-read::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar-read::-webkit-scrollbar-thumb { background: rgba(128, 128, 128, 0.2); border-radius: 9999px; }
.custom-scrollbar-read::-webkit-scrollbar-thumb:hover { background: rgba(128, 128, 128, 0.45); }
</style>
