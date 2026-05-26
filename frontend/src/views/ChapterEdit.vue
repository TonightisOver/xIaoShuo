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
      <div v-if="isReadMode" class="fixed inset-0 z-50 overflow-y-auto transition-all duration-300 custom-scrollbar-read" :class="[themeClasses[activeTheme]]">
        <!-- 阅读器正文容器 -->
        <div class="max-w-3xl mx-auto px-6 py-20 relative min-h-screen flex flex-col justify-between">
          <div>
            <!-- 返回与状态条 -->
            <div class="flex items-center justify-between pb-6 mb-12 border-b" :class="[activeTheme === 'dark' ? 'border-white/10' : 'border-black/5']">
              <span class="text-xs opacity-60 tracking-wider font-semibold">正在沉浸阅读《{{ chapter.novel?.title || '小说创作' }}》</span>
              <button @click="toggleReadMode" class="text-xs font-bold px-3 py-1 rounded-full border hover:scale-105 active:scale-95 transition-all" :class="[activeTheme === 'dark' ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5']">
                切换到编辑模式
              </button>
            </div>

            <!-- 章节标题 -->
            <h1 class="text-3xl md:text-4xl font-extrabold mb-10 text-center tracking-tight" :class="[activeFont === 'serif' ? 'font-serif' : 'font-sans']">
              {{ chapter.volume_number ? `第${chapter.volume_number}卷 · ` : '' }}第{{ chapter.chapter_number }}章：{{ chapter.title }}
            </h1>

            <!-- 章节正文 -->
            <div
              class="leading-loose tracking-wide whitespace-pre-line text-justify select-text focus:outline-none"
              :class="[activeFont === 'serif' ? 'font-serif' : 'font-sans']"
              :style="{ fontSize: fontSize + 'px', lineHeight: '2.0' }"
            >
              {{ content }}
            </div>
          </div>

          <!-- 阅读底栏上一章下一章导航 -->
          <div class="flex items-center justify-between gap-6 mt-20 pt-8 border-t" :class="[activeTheme === 'dark' ? 'border-white/10' : 'border-black/5']">
            <button
              v-if="prevChapter"
              @click="goToChapter(prevChapter.chapter_number)"
              class="flex-1 py-4 px-6 rounded-2xl border text-sm font-semibold flex items-center justify-center gap-2 transition-all hover:scale-[1.02] active:scale-[0.98]"
              :class="[activeTheme === 'dark' ? 'border-white/10 hover:bg-white/5 text-slate-300' : 'border-black/10 hover:bg-black/5 text-slate-700']"
            >
              ← 上一章
            </button>
            <span v-else class="flex-1 text-center text-xs opacity-40 font-semibold py-4">已是第一章</span>

            <button
              v-if="nextChapter"
              @click="goToChapter(nextChapter.chapter_number)"
              class="flex-1 py-4 px-6 rounded-2xl border text-sm font-semibold flex items-center justify-center gap-2 transition-all hover:scale-[1.02] active:scale-[0.98]"
              :class="[activeTheme === 'dark' ? 'border-white/10 hover:bg-white/5 text-slate-300' : 'border-black/10 hover:bg-black/5 text-slate-700']"
            >
              下一章 →
            </button>
            <span v-else class="flex-1 text-center text-xs opacity-40 font-semibold py-4">已是最后一章</span>
          </div>
        </div>

        <!-- ==================== 2. 悬浮排版控制面板 (Floating Settings Panel) ==================== -->
        <div class="fixed right-6 bottom-10 z-50 flex flex-col items-end gap-3">
          <!-- 展开后的设置面板 -->
          <div v-if="showSettings" class="bg-white rounded-xl border border-neutral-200 shadow-lg p-5 flex flex-col gap-4 w-72"
               :class="[activeTheme === 'dark' ? 'bg-neutral-900 text-slate-200 border-neutral-700' : '']">

            <div class="flex items-center justify-between border-b pb-2" :class="[activeTheme === 'dark' ? 'border-neutral-700' : 'border-neutral-200']">
              <span class="text-xs font-bold tracking-wider text-neutral-700">排版个性化设置</span>
              <button @click="showSettings = false" class="text-xs text-neutral-400 hover:text-neutral-600">✕ 关闭</button>
            </div>

            <!-- 字号调节 -->
            <div class="flex flex-col gap-1.5">
              <span class="text-[11px] text-neutral-500 font-semibold">字号大小</span>
              <div class="flex items-center justify-between gap-2">
                <button @click="adjustFontSize(-2)" class="flex-1 py-1.5 rounded-lg border text-center font-bold text-sm transition-all border-neutral-200 hover:bg-neutral-50">A -</button>
                <span class="text-xs font-mono font-bold w-12 text-center text-neutral-700">{{ fontSize }}px</span>
                <button @click="adjustFontSize(2)" class="flex-1 py-1.5 rounded-lg border text-center font-bold text-sm transition-all border-neutral-200 hover:bg-neutral-50">A +</button>
              </div>
            </div>

            <!-- 字体切换 -->
            <div class="flex flex-col gap-1.5">
              <span class="text-[11px] text-neutral-500 font-semibold">阅读字体</span>
              <div class="flex gap-2">
                <button @click="activeFont = 'serif'" class="flex-1 py-1.5 rounded-lg border text-xs transition-all"
                        :class="[activeFont === 'serif' ? 'border-accent-500 bg-accent-50 text-accent-700 font-bold' : 'border-neutral-200']">宋体 / 衬线</button>
                <button @click="activeFont = 'sans'" class="flex-1 py-1.5 rounded-lg border text-xs transition-all"
                        :class="[activeFont === 'sans' ? 'border-accent-500 bg-accent-50 text-accent-700 font-bold' : 'border-neutral-200']">系统 / 无衬线</button>
              </div>
            </div>

            <!-- 四大护眼背景主题 -->
            <div class="flex flex-col gap-1.5">
              <span class="text-[11px] text-neutral-500 font-semibold">背景配色</span>
              <div class="grid grid-cols-4 gap-2">
                <button @click="activeTheme = 'parchment'" class="h-9 rounded-lg border-2 flex items-center justify-center transition-all bg-[#f4ecd8] border-amber-900/10 relative"
                        :class="[activeTheme === 'parchment' ? 'border-amber-600 scale-105' : '']" title="仿古羊皮纸">
                  <span v-if="activeTheme === 'parchment'" class="text-xs">🌾</span>
                </button>
                <button @click="activeTheme = 'green'" class="h-9 rounded-lg border-2 flex items-center justify-center transition-all bg-[#dfedd6] border-emerald-900/10 relative"
                        :class="[activeTheme === 'green' ? 'border-emerald-600 scale-105' : '']" title="温润护眼绿">
                  <span v-if="activeTheme === 'green'" class="text-xs">🍃</span>
                </button>
                <button @click="activeTheme = 'dark'" class="h-9 rounded-lg border-2 flex items-center justify-center transition-all bg-[#0b0e14] border-slate-900 relative"
                        :class="[activeTheme === 'dark' ? 'border-blue-500 scale-105' : '']" title="黑夜寂静">
                  <span v-if="activeTheme === 'dark'" class="text-xs">🌌</span>
                </button>
                <button @click="activeTheme = 'white'" class="h-9 rounded-lg border-2 flex items-center justify-center transition-all bg-[#ffffff] border-slate-200 relative"
                        :class="[activeTheme === 'white' ? 'border-slate-800 scale-105' : '']" title="极简雪花白">
                  <span v-if="activeTheme === 'white'" class="text-xs">❄</span>
                </button>
              </div>
            </div>
          </div>

          <!-- 设置开关按钮 -->
          <button @click="showSettings = !showSettings" class="w-12 h-12 rounded-full shadow-lg flex items-center justify-center text-xl transition-all active:scale-95 bg-accent-600 text-white hover:bg-accent-700">
            ⚙
          </button>
        </div>
      </div>

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
            <button @click="save" class="btn-primary text-sm flex items-center gap-1.5" :disabled="saving">
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
          </div>
        </div>
      </div>
    </template>
  </div>

  <!-- ==================== AI 改写 Modal ==================== -->
  <Teleport to="body">
    <div v-if="showRewriteModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="closeRewriteModal">
      <div class="bg-white border border-neutral-200 rounded-xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden">
        <div class="px-6 py-4 border-b border-neutral-200 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-neutral-800 flex items-center gap-2">AI 改写</h3>
          <button @click="closeRewriteModal" class="text-neutral-400 hover:text-neutral-600 transition-colors text-lg leading-none">✕</button>
        </div>

        <!-- 未生成结果时：输入面板 -->
        <div v-if="!rewriteResult" class="p-6 space-y-4">
          <div>
            <div class="text-xs font-semibold text-neutral-500 mb-2">选中文本预览</div>
            <div class="bg-neutral-50 rounded-xl px-4 py-3 text-sm text-neutral-700 leading-relaxed border border-neutral-200 line-clamp-3">
              {{ selectionText.length > 100 ? selectionText.slice(0, 100) + '...' : selectionText }}
            </div>
          </div>
          <div>
            <div class="text-xs font-semibold text-neutral-500 mb-2">改写指令</div>
            <textarea
              v-model="rewriteInstruction"
              class="input w-full resize-none"
              rows="3"
              placeholder="例如：改成更有张力的描写、增加环境渲染、调整节奏使其更紧凑..."
            ></textarea>
          </div>
          <div v-if="rewriteError" class="text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{{ rewriteError }}</div>
          <div class="flex justify-end gap-3">
            <button @click="closeRewriteModal" class="btn-secondary text-sm px-4 py-2">取消</button>
            <button @click="doRewrite" :disabled="rewriting || !rewriteInstruction.trim()" class="btn-primary text-sm px-5 py-2 flex items-center gap-2">
              <svg v-if="rewriting" class="w-4 h-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
              <span>{{ rewriting ? '生成中...' : '生成改写' }}</span>
            </button>
          </div>
        </div>

        <!-- 生成结果面板 -->
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
            <button @click="rewriteResult = null; rewriteError = ''" class="btn-secondary text-sm px-4 py-2">重新生成</button>
            <button @click="closeRewriteModal" class="btn-secondary text-sm px-4 py-2">放弃</button>
            <button @click="acceptRewrite" class="btn-primary text-sm px-5 py-2">采纳改写</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ==================== 版本预览 Modal ==================== -->
  <Teleport to="body">
    <div v-if="previewVersionData" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="previewVersionData = null">
      <div class="bg-white border border-neutral-200 rounded-xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden">
        <div class="px-6 py-4 border-b border-neutral-200 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-neutral-800">版本 v{{ previewVersionData.version_number }} 预览</h3>
          <button @click="previewVersionData = null" class="text-neutral-400 hover:text-neutral-600 transition-colors text-lg leading-none">✕</button>
        </div>
        <div class="p-6 space-y-4">
          <div class="flex items-center gap-3 text-xs text-neutral-500">
            <span class="px-2 py-0.5 rounded-full font-medium"
              :class="{
                'bg-blue-50 text-blue-700': previewVersionData.source === 'ai_rewrite',
                'bg-amber-50 text-amber-700': previewVersionData.source === 'rollback',
                'bg-neutral-100 text-neutral-600': previewVersionData.source === 'manual',
                'bg-emerald-50 text-emerald-700': previewVersionData.source === 'generation',
              }"
            >{{ sourceLabel(previewVersionData.source) }}</span>
            <span>{{ previewVersionData.word_count }} 字</span>
            <span>{{ formatDate(previewVersionData.created_at) }}</span>
            <span v-if="previewVersionData.quality_score" class="text-amber-600">★ {{ previewVersionData.quality_score.toFixed(1) }}</span>
            <span v-if="previewVersionData.model_name" class="text-neutral-400">{{ previewVersionData.model_name }}</span>
          </div>
          <div class="bg-neutral-50 rounded-xl px-4 py-3 text-sm text-neutral-700 leading-relaxed border border-neutral-200 max-h-64 overflow-y-auto custom-scrollbar whitespace-pre-wrap">
            {{ previewVersionData.content }}
          </div>
          <div class="flex justify-end gap-3">
            <button @click="previewVersionData = null" class="btn-secondary text-sm px-4 py-2">关闭</button>
            <button @click="doActivate(previewVersionData.version_number)" class="btn-secondary text-sm px-4 py-2 border-accent-200 text-accent-600 hover:bg-accent-50">设为正式版本</button>
            <button @click="doRollback(previewVersionData.version_number)" class="btn-primary text-sm px-5 py-2">回滚到此版本</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const novelId = computed(() => route.params.id)
const chapterNum = computed(() => route.params.num)

const chapter = ref(null)
const content = ref('')
const allChapters = ref([])
const allVolumes = ref([])
const saving = ref(false)
const saved = ref(false)
const regenerating = ref(false)

// Reading Mode state
const isReadMode = ref(false)
const showSettings = ref(false)
const fontSize = ref(20) // Default 20px
const activeFont = ref('serif') // Default 宋体 (serif)
const activeTheme = ref('parchment') // Default parchment

// AI Rewrite state
const textareaRef = ref(null)
const selectionText = ref('')
const selectionStart = ref(0)
const selectionEnd = ref(0)
const showRewriteModal = ref(false)
const rewriteInstruction = ref('')
const rewriting = ref(false)
const rewriteResult = ref(null) // { original, rewritten }
const rewriteError = ref('')

// Version history state
const versions = ref([])
const showVersionHistory = ref(false)
const previewVersionData = ref(null)

const themeClasses = {
  parchment: 'bg-[#f4ecd8] text-[#3c2f1f]',
  green: 'bg-[#dfedd6] text-[#2c3d27]',
  dark: 'bg-[#0d0f14] text-[#a8b0c2]',
  white: 'bg-[#ffffff] text-[#111111]',
}

const contentLength = computed(() => content.value.length)

function toggleReadMode() {
  isReadMode.value = !isReadMode.value
  showSettings.value = false
}

function adjustFontSize(delta) {
  fontSize.value = Math.max(14, Math.min(32, fontSize.value + delta))
}

// --- Selection detection ---

function onSelectionChange() {
  const el = textareaRef.value
  if (!el) return
  const start = el.selectionStart
  const end = el.selectionEnd
  if (start !== end) {
    selectionText.value = content.value.slice(start, end)
    selectionStart.value = start
    selectionEnd.value = end
  } else {
    selectionText.value = ''
  }
}

// --- AI Rewrite ---

function openRewriteModal() {
  rewriteInstruction.value = ''
  rewriteResult.value = null
  rewriteError.value = ''
  showRewriteModal.value = true
}

function closeRewriteModal() {
  showRewriteModal.value = false
  rewriteResult.value = null
  rewriteError.value = ''
}

async function doRewrite() {
  if (!rewriteInstruction.value.trim()) return
  rewriting.value = true
  rewriteError.value = ''
  try {
    const res = await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}/rewrite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        full_content: content.value,
        selected_text: selectionText.value,
        selection_start: selectionStart.value,
        selection_end: selectionEnd.value,
        instruction: rewriteInstruction.value,
      }),
    })

    if (res.status === 504) {
      rewriteError.value = 'AI 改写超时，请稍后重试'
    } else if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      rewriteError.value = data.detail || '改写失败，请重试'
    } else {
      const data = await res.json()
      rewriteResult.value = { original: data.original_text, rewritten: data.rewritten_text }
    }
  } catch (e) {
    rewriteError.value = '网络错误，请重试'
  } finally {
    rewriting.value = false
  }
}

async function acceptRewrite() {
  if (!rewriteResult.value) return
  // Replace selected text in content
  const newContent = content.value.slice(0, selectionStart.value) + rewriteResult.value.rewritten + content.value.slice(selectionEnd.value)
  content.value = newContent
  closeRewriteModal.value = false
  showRewriteModal.value = false
  selectionText.value = ''

  // Save version
  await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}/versions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content: newContent,
      source: 'ai_rewrite',
      rewrite_instruction: rewriteInstruction.value,
    }),
  })
  await loadVersions()
}

// --- Version History ---

async function loadVersions() {
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}/versions`)
  if (res.ok) {
    versions.value = await res.json()
  }
}

async function previewVersion(ver) {
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}/versions/${ver.version_number}`)
  if (res.ok) {
    previewVersionData.value = await res.json()
  }
}

async function doRollback(versionNumber) {
  if (!confirm(`确定回滚到版本 v${versionNumber}？当前未保存的内容将丢失。`)) return
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}/versions/${versionNumber}/rollback`, {
    method: 'POST',
  })
  if (res.ok) {
    previewVersionData.value = null
    await load()
    await loadVersions()
  }
}

async function doActivate(versionNumber) {
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}/versions/${versionNumber}/activate`, {
    method: 'POST',
  })
  if (res.ok) {
    previewVersionData.value = null
    await load()
    await loadVersions()
  }
}

function sourceLabel(source) {
  const map = { manual: '手动', ai_rewrite: 'AI改写', rollback: '回滚', generation: '生成' }
  return map[source] || source
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// --- Data loading ---

async function load() {
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}`)
  if (res.ok) {
    chapter.value = await res.json()
    content.value = chapter.value.content || ''
  } else {
    chapter.value = null
    content.value = ''
  }
}

async function loadAllChapters() {
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters`)
  if (res.ok) {
    allChapters.value = await res.json()
  }
}

async function loadVolumes() {
  const res = await fetch(`/api/v1/projects/${novelId.value}/volumes`)
  if (res.ok) {
    allVolumes.value = await res.json()
  } else {
    allVolumes.value = []
  }
}

const sortedChapters = computed(() => {
  return [...allChapters.value].sort((a, b) => a.chapter_number - b.chapter_number)
})

const groupedChapters = computed(() => {
  const groups = []
  const sorted = sortedChapters.value

  if (allVolumes.value.length === 0) {
    groups.push({
      title: '正文目录',
      chapters: sorted
    })
    return groups
  }

  const volMap = new Map()
  for (const vol of allVolumes.value) {
    volMap.set(vol.volume_number, vol)
  }

  const volumeGroups = {}
  const unassigned = []

  for (const ch of sorted) {
    const volNum = ch.volume_number
    if (volNum && volMap.has(volNum)) {
      if (!volumeGroups[volNum]) {
        volumeGroups[volNum] = []
      }
      volumeGroups[volNum].push(ch)
    } else {
      unassigned.push(ch)
    }
  }

  const sortedVolNums = Object.keys(volumeGroups).map(Number).sort((a, b) => a - b)
  for (const volNum of sortedVolNums) {
    const vol = volMap.get(volNum)
    groups.push({
      volume_number: volNum,
      title: `第${volNum}卷 · ${vol.title || '未命名'}`,
      chapters: volumeGroups[volNum]
    })
  }

  if (unassigned.length > 0) {
    groups.push({
      title: '未分卷章节',
      chapters: unassigned
    })
  }

  return groups
})

const currentIdx = computed(() => {
  if (!chapter.value) return -1
  return sortedChapters.value.findIndex(c => c.chapter_number === chapter.value.chapter_number)
})

const prevChapter = computed(() => {
  const idx = currentIdx.value
  if (idx > 0) return sortedChapters.value[idx - 1]
  return null
})

const nextChapter = computed(() => {
  const idx = currentIdx.value
  if (idx !== -1 && idx < sortedChapters.value.length - 1) return sortedChapters.value[idx + 1]
  return null
})

function goToChapter(num) {
  router.push(`/novels/${novelId.value}/chapters/${num}`)
}

async function save() {
  saving.value = true
  saved.value = false
  await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: content.value, title: chapter.value.title }),
  })
  saving.value = false
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)

  // Reload all chapters to update word counts in sidebar
  loadAllChapters()
}

async function regenerate() {
  if (!confirm('重新生成将覆盖当前内容，确定吗？')) return
  regenerating.value = true
  try {
    const res = await fetch(`/api/v1/projects/${novelId.value}/generate-chapters`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chapter_start: parseInt(chapterNum.value), chapter_end: parseInt(chapterNum.value) }),
    })

    if (res.ok) {
      const data = await res.json()
      router.push(`/task/${data.task_id}`)
    } else {
      const err = await res.json().catch(() => ({ detail: '请求失败' }))
      alert(`重新生成失败: ${err.detail || res.statusText}`)
    }
  } catch (e) {
    alert(`重新生成失败: 网络错误`)
  }
  regenerating.value = false
}

async function deleteChapter() {
  if (!confirm('确定删除本章？此操作不可恢复。')) return
  await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}`, { method: 'DELETE' })
  router.push(`/novels/${novelId.value}`)
}

// Watch novelId to load both chapters and volumes
watch(novelId, (newId) => {
  if (newId) {
    loadAllChapters()
    loadVolumes()
  }
}, { immediate: true })

// Watch route params changes to load the correct chapter content
watch([novelId, chapterNum], () => {
  load()
  loadVersions()
}, { immediate: true })
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
