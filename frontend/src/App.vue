<template>
  <div class="min-h-screen flex flex-col">
    <header class="bg-white border-b border-ink-200 sticky top-0 z-50">
      <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <router-link to="/" class="flex items-center gap-2">
          <span class="text-xl font-bold text-primary-700">xIaoShuo</span>
          <span class="text-sm text-ink-500">AI 创作平台</span>
        </router-link>
        <nav class="flex items-center gap-4">
          <router-link to="/" class="text-ink-600 hover:text-primary-600 transition-colors text-sm font-medium">
            任务列表
          </router-link>
          <router-link to="/create" class="btn-primary text-sm">
            开始创作
          </router-link>
        </nav>
      </div>
    </header>

    <main class="flex-1">
      <router-view />
    </main>

    <footer class="border-t border-ink-200 py-6">
      <div class="max-w-6xl mx-auto px-6 text-center text-sm text-ink-500">
        xIaoShuo &copy; 2026 &middot; Powered by DeepSeek + LangGraph
      </div>
    </footer>
  </div>
</template>
