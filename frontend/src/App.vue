<template>
  <div class="min-h-screen flex flex-col">
    <header class="bg-slate-950/50 backdrop-blur-lg border-b border-slate-900 sticky top-0 z-50">
      <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <router-link to="/" class="flex items-center gap-2.5">
          <span class="text-2xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-indigo-400">xIaoShuo</span>
          <span class="text-xs bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded-md font-medium border border-purple-500/20">AI 创作平台</span>
        </router-link>
        <nav class="flex items-center gap-6">
          <router-link to="/tasks" class="text-slate-300 hover:text-purple-400 transition-colors text-sm font-semibold">
            任务列表
          </router-link>
          <router-link to="/create" class="btn-primary text-sm flex items-center gap-1.5 shadow-sm">
            <span>开始创作</span>
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          </router-link>
        </nav>
      </div>
    </header>

    <main class="flex-1">
      <router-view />
    </main>

    <footer class="border-t border-slate-900/60 bg-slate-950/20 py-8 mt-12">
      <div class="max-w-6xl mx-auto px-6 text-center text-sm text-slate-500">
        xIaoShuo &copy; 2026 &middot; Powered by DeepSeek + LangGraph
      </div>
    </footer>
  </div>
</template>
