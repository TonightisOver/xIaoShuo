<template>
  <div class="max-w-7xl mx-auto px-6 py-10 transition-all duration-300">
    <div v-if="!chapter" class="text-center py-20">
      <div class="max-w-sm mx-auto">
        <div class="w-16 h-16 bg-neutral-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-8 h-8 text-neutral-400">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        </div>
        <h3 class="text-neutral-900 font-semibold text-base mb-2">章节暂时无法访问</h3>
        <p class="text-neutral-500 text-sm mb-6 leading-relaxed">该章节可能正在重新生成中，或生成过程中出现了异常。</p>
        <div class="flex items-center justify-center gap-3">
          <button @click="load" class="btn-secondary text-sm px-4 py-2 flex items-center gap-1.5">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            <span>刷新重试</span>
          </button>
          <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm px-4 py-2">
            返回章节列表
          </router-link>
        </div>
      </div>
    </div>

    <template v-else>
      <!-- ==================== 1. 阅读模式 (Immersive Read Mode) ==================== -->
      <ChapterReadMode
        v-if="isReadMode"
        :chapter="chapter"
        :content="content"
        :prev-chapter="prevChapter"
        :next-chapter="nextChapter"
        :active-theme="activeTheme"
        :active-font="activeFont"
        :font-size="fontSize"
        :show-settings="showSettings"
        @exit="toggleReadMode"
        @go-to-chapter="goToChapter"
        @adjust-font-size="adjustFontSize"
        @update:active-font="activeFont = $event"
        @update:active-theme="activeTheme = $event"
        @update:show-settings="showSettings = $event"
      />

      <!-- ==================== 3. 编辑模式 (Standard Edit Mode) ==================== -->
      <div v-else>
        <!-- Top header layout -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <div class="flex items-center gap-2 mb-1.5">
              <router-link :to="`/novels/${novelId}`" class="text-xs text-accent-600 hover:text-accent-700 font-semibold flex items-center gap-1 group">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                </svg>
                返回作品详情
              </router-link>
            </div>
            <h1 class="text-2xl font-extrabold text-neutral-900">
              {{ chapter.volume_number ? `第${chapter.volume_number}卷 · ` : '' }}第{{ chapter.chapter_number }}章：{{ chapter.title }}
            </h1>
            <p class="text-xs text-neutral-500 mt-2 flex items-center gap-2 font-medium">
              <span>{{ contentLength }} 字</span>
              <span class="text-neutral-300">|</span>
              <span>共 {{ sortedChapters.length }} 章</span>
            </p>
          </div>
          <div class="flex items-center gap-3">
            <button @click="toggleReadMode" class="btn-secondary text-sm flex items-center gap-1.5 px-4 py-2">
              沉浸阅读
            </button>
            <button @click="regenerate" class="btn-secondary text-sm flex items-center gap-1.5" :disabled="regenerating">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4" :class="{'animate-spin': regenerating}">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              <span>{{ regenerating ? '生成中...' : '重新生成' }}</span>
            </button>
            <button @click="deleteChapter" class="text-rose-500 hover:text-rose-400 text-sm px-3 py-2 transition-colors font-medium">删除</button>
            <button @click="saveAndRefresh" class="btn-primary text-sm flex items-center gap-1.5" :disabled="saving">
              <span>{{ saving ? '保存中...' : '保存修改' }}</span>
            </button>
          </div>
        </div>

        <!-- Main Layout: Sidebar & Content Editor -->
        <div class="grid grid-cols-1 lg:grid-cols-4 gap-8">
          <!-- Directory Sidebar -->
          <div class="lg:col-span-1">
            <div class="bg-white rounded-xl border border-neutral-200 p-4 sticky top-24 max-h-[calc(100vh-12rem)] flex flex-col">
              <h2 class="text-sm font-bold text-neutral-900 mb-4 pb-2.5 border-b border-neutral-200 flex items-center justify-between">
                <span class="flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-accent-600">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
                  </svg>
                  <span>目录导航</span>
                </span>
                <span class="text-[10px] bg-neutral-100 text-neutral-500 px-2 py-0.5 rounded-full font-semibold">TOC</span>
              </h2>

              <div class="overflow-y-auto flex-1 space-y-4 pr-1.5 custom-scrollbar">
                <div v-for="group in groupedChapters" :key="group.title" class="space-y-1.5">
                  <div class="text-[11px] font-bold text-neutral-400 tracking-wider uppercase pl-1 pt-2 pb-1 border-b border-neutral-100">
                    {{ group.title }}
                  </div>
                  <div
                    v-for="ch in group.chapters"
                    :key="ch.chapter_number"
                    @click="goToChapter(ch.chapter_number)"
                    :class="[
                      'px-3 py-2.5 rounded-lg text-xs cursor-pointer transition-all duration-200 flex items-center justify-between',
                      ch.chapter_number === parseInt(chapterNum)
                        ? 'bg-accent-50 text-accent-700 border border-accent-200 font-semibold'
                        : 'text-neutral-600 hover:bg-neutral-50 border border-transparent'
                    ]"
                  >
                    <span class="truncate pr-2">第{{ ch.chapter_number }}章：{{ ch.title }}</span>
                    <span class="text-[10px] text-neutral-400 font-mono shrink-0">{{ ch.content ? ch.content.length : 0 }}字</span>
                  </div>
                </div>
              </div>

              <!-- Version History Collapsible -->
              <div class="mt-4 border-t border-neutral-200 pt-3">
                <button
                  @click="showVersionHistory = !showVersionHistory"
                  class="w-full flex items-center justify-between text-xs font-bold text-neutral-500 hover:text-neutral-700 transition-colors py-1"
                >
                  <span class="flex items-center gap-1.5">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-3.5 h-3.5 text-accent-600">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    版本历史
                    <span class="text-[10px] bg-neutral-100 text-neutral-500 px-1.5 py-0.5 rounded-full">{{ versions.length }}</span>
                  </span>
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3 h-3 transition-transform" :class="showVersionHistory ? 'rotate-180' : ''">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                  </svg>
                </button>
                <div v-if="showVersionHistory" class="mt-2 space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar">
                  <div v-if="versions.length === 0" class="text-[11px] text-neutral-400 text-center py-2">暂无版本记录</div>
                  <div
                    v-for="ver in versions"
                    :key="ver.version_number"
                    @click="previewVersion(ver)"
                    class="px-2.5 py-2 rounded-lg text-[11px] cursor-pointer transition-all border border-transparent hover:bg-neutral-50 hover:border-neutral-200"
                    :class="{ 'border-accent-200 bg-accent-50': ver.is_active }"
                  >
                    <div class="flex items-center justify-between">
                      <span class="font-semibold text-neutral-700 flex items-center gap-1">
                        v{{ ver.version_number }}
                        <span v-if="ver.is_active" class="text-[9px] bg-accent-50 text-accent-700 px-1 py-0.5 rounded">活跃</span>
                      </span>
                      <span class="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                        :class="{
                          'bg-blue-50 text-blue-700': ver.source === 'ai_rewrite',
                          'bg-amber-50 text-amber-700': ver.source === 'rollback',
                          'bg-neutral-100 text-neutral-600': ver.source === 'manual',
                          'bg-emerald-50 text-emerald-700': ver.source === 'generation',
                        }"
                      >{{ sourceLabel(ver.source) }}</span>
                    </div>
                    <div class="text-neutral-500 mt-0.5 flex items-center gap-2">
                      <span>{{ ver.word_count }} 字 · {{ formatDate(ver.created_at) }}</span>
                      <span v-if="ver.quality_score" class="text-amber-600">★ {{ ver.quality_score.toFixed(1) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Editor Area -->
          <div class="lg:col-span-3 space-y-6">
            <!-- AI Rewrite Bubble Button -->
            <div
              v-if="selectionText"
              class="flex justify-end"
            >
              <button
                @click="openRewriteModal"
                class="btn-secondary text-sm flex items-center gap-1.5 px-4 py-2"
              >
                AI 改写
              </button>
            </div>

            <div class="flex justify-end mb-2 gap-2">
              <button @click="showReaderSim = !showReaderSim" class="btn-secondary text-xs flex items-center gap-1 px-3 py-1.5">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-3.5 h-3.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
                </svg>
                <span>读者模拟</span>
              </button>
              <button @click="copyContent" class="btn-secondary text-xs flex items-center gap-1 px-3 py-1.5">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-3.5 h-3.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                </svg>
                <span>{{ copied ? '已复制' : '复制正文' }}</span>
              </button>
            </div>

            <div class="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden">
              <textarea
                ref="textareaRef"
                v-model="content"
                @mouseup="onSelectionChange"
                @keyup="onSelectionChange"
                class="w-full min-h-[600px] p-6 md:p-8 text-base leading-relaxed font-sans bg-transparent text-neutral-900 resize-y border-0 focus:outline-none focus:ring-0 focus:border-0"
                placeholder="开始书写或重新生成章节正文..."
              ></textarea>
            </div>

            <!-- Bottom Navigation -->
            <div class="flex flex-col sm:flex-row items-center justify-between gap-4 py-6 border-t border-neutral-200">
              <div class="w-full sm:w-auto">
                <button
                  v-if="prevChapter"
                  @click="goToChapter(prevChapter.chapter_number)"
                  class="w-full btn-secondary text-sm flex items-center justify-center gap-2 group py-3 px-5"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4 group-hover:-translate-x-0.5 transition-transform text-accent-600">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                  </svg>
                  <span>上一章：{{ prevChapter.title }}</span>
                </button>
                <span v-else class="text-xs text-neutral-400 font-semibold block text-center sm:text-left py-2">已是第一章</span>
              </div>

              <div class="order-first sm:order-none">
                <p v-if="saved" class="text-sm text-emerald-600 font-semibold flex items-center justify-center gap-1.5">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor" class="w-4 h-4">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  <span>内容已保存（{{ contentLength }} 字）</span>
                </p>
              </div>

              <div class="w-full sm:w-auto">
                <button
                  v-if="nextChapter"
                  @click="goToChapter(nextChapter.chapter_number)"
                  class="w-full btn-secondary text-sm flex items-center justify-center gap-2 group py-3 px-5"
                >
                  <span>下一章：{{ nextChapter.title }}</span>
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4 group-hover:translate-x-0.5 transition-transform text-accent-600">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                </button>
                <span v-else class="text-xs text-neutral-400 font-semibold block text-center sm:text-right py-2">已是最后一章</span>
              </div>
            </div>

            <!-- Reader Simulation Panel -->
            <ReaderSimPanel v-if="showReaderSim" :novel-id="novelId" :chapter-number="parseInt(chapterNum)" />
          </div>
        </div>
      </div>
    </template>
  </div>

  <!-- ==================== AI 改写 + 版本预览 Modals ==================== -->
  <ChapterModals
    :show-rewrite-modal="showRewriteModal"
    :rewrite-instruction="rewriteInstruction"
    :rewriting="rewriting"
    :rewrite-result="rewriteResult"
    :rewrite-error="rewriteError"
    :selection-text="selectionText"
    :preview-version-data="previewVersionData"
    @close-rewrite="closeRewriteModal"
    @do-rewrite="doRewrite"
    @accept-rewrite="acceptRewrite"
    @reset-rewrite="rewriteResult = null; rewriteError = ''"
    @update:rewrite-instruction="rewriteInstruction = $event"
    @close-preview="previewVersionData = null"
    @rollback="doRollback"
    @activate="doActivate"
  />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ReaderSimPanel from '../components/ReaderSimPanel.vue'
import ChapterModals from '../components/ChapterModals.vue'
import ChapterReadMode from '../components/ChapterReadMode.vue'
import { useChapterContent } from '../composables/useChapterContent.js'
import { useChapterRewrite } from '../composables/useChapterRewrite.js'
import { useChapterVersions } from '../composables/useChapterVersions.js'
import { useChapterNavigation } from '../composables/useChapterNavigation.js'

const route = useRoute()
const router = useRouter()
const novelId = computed(() => route.params.id)
const chapterNum = computed(() => route.params.num)

const { chapter, content, saving, saved, regenerating, load, save, regenerate, deleteChapter } = useChapterContent(novelId, chapterNum)
const { showRewriteModal, rewriteInstruction, rewriting, rewriteResult, rewriteError, selectionText, selectionStart, selectionEnd, openRewriteModal, closeRewriteModal, doRewrite } = useChapterRewrite(novelId, chapterNum, content)
const { versions, showVersionHistory, previewVersionData, loadVersions, previewVersion } = useChapterVersions(novelId, chapterNum)
const { sortedChapters, groupedChapters, prevChapter, nextChapter, loadAllChapters, loadVolumes, goToChapter } = useChapterNavigation(novelId, chapterNum)

// --- UI state ---
const isReadMode = ref(false)
const showSettings = ref(false)
const fontSize = ref(20)
const activeFont = ref('serif')
const activeTheme = ref('parchment')
const copied = ref(false)
const showReaderSim = ref(false)
const textareaRef = ref(null)

const themeClasses = { parchment: 'bg-[#f4ecd8] text-[#3c2f1f]', green: 'bg-[#dfedd6] text-[#2c3d27]', dark: 'bg-[#0d0f14] text-[#a8b0c2]', white: 'bg-[#ffffff] text-[#111111]' }
const contentLength = computed(() => content.value.length)

function toggleReadMode() { isReadMode.value = !isReadMode.value; showSettings.value = false }
function adjustFontSize(delta) { fontSize.value = Math.max(14, Math.min(32, fontSize.value + delta)) }

function onSelectionChange() {
  const el = textareaRef.value
  if (!el) return
  const start = el.selectionStart; const end = el.selectionEnd
  if (start !== end) { selectionText.value = content.value.slice(start, end); selectionStart.value = start; selectionEnd.value = end }
  else { selectionText.value = '' }
}

async function acceptRewrite() {
  if (!rewriteResult.value) return
  const newContent = content.value.slice(0, selectionStart.value) + rewriteResult.value.rewritten + content.value.slice(selectionEnd.value)
  content.value = newContent
  showRewriteModal.value = false
  selectionText.value = ''
  await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}/versions`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: newContent, source: 'ai_rewrite', rewrite_instruction: rewriteInstruction.value }),
  })
  await loadVersions()
}

async function doRollback(versionNumber) {
  if (!confirm(`确定回滚到版本 v${versionNumber}？当前未保存的内容将丢失。`)) return
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}/versions/${versionNumber}/rollback`, { method: 'POST' })
  if (res.ok) { previewVersionData.value = null; await load(); await loadVersions() }
}

async function doActivate(versionNumber) {
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}/versions/${versionNumber}/activate`, { method: 'POST' })
  if (res.ok) { previewVersionData.value = null; await load(); await loadVersions() }
}

async function saveAndRefresh() { await save(); loadAllChapters() }
async function copyContent() {
  try { await navigator.clipboard.writeText(content.value); copied.value = true; setTimeout(() => { copied.value = false }, 2000) }
  catch { /* clipboard API not available */ }
}

function sourceLabel(source) { return { manual: '手动', ai_rewrite: 'AI改写', rollback: '回滚', generation: '生成' }[source] || source }
function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

watch(novelId, (newId) => { if (newId) { loadAllChapters(); loadVolumes() } }, { immediate: true })
watch([novelId, chapterNum], () => { load(); loadVersions() }, { immediate: true })
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 9999px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
.custom-scrollbar-read::-webkit-scrollbar {
  width: 8px;
}
.custom-scrollbar-read::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar-read::-webkit-scrollbar-thumb {
  background: rgba(128, 128, 128, 0.2);
  border-radius: 9999px;
}
.custom-scrollbar-read::-webkit-scrollbar-thumb:hover {
  background: rgba(128, 128, 128, 0.45);
}
</style>
