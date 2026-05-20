<template>
  <div class="min-h-screen flex flex-col">
    <!-- Premium translucent Apple-style light header -->
    <header class="bg-white/80 backdrop-blur-lg border-b border-[#e5e5ea] sticky top-0 z-50 shadow-sm">
      <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <router-link to="/" class="flex items-center gap-2.5 hover:opacity-90 transition-opacity select-none">
          <span class="text-2xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-indigo-600">xIaoShuo</span>
          <span class="text-[10px] bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full font-bold border border-purple-100">AI 创作平台</span>
        </router-link>
        <nav class="flex items-center gap-6">
          <router-link to="/tasks" class="text-gray-600 hover:text-purple-600 transition-colors text-sm font-semibold">
            任务大厅
          </router-link>
          <router-link to="/create" class="btn-primary text-sm flex items-center gap-1.5 shadow-sm">
            <span>开启创作</span>
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.8" stroke="currentColor" class="w-3.5 h-3.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          </router-link>
        </nav>
      </div>
    </header>

    <main class="flex-1">
      <router-view />
    </main>

    <!-- Sleek Apple-style clean footer -->
    <footer class="border-t border-[#e5e5ea] bg-white/40 py-8 mt-12">
      <div class="max-w-6xl mx-auto px-6 text-center text-xs md:text-sm text-[#86868b]">
        xIaoShuo &copy; 2026 &middot; Powered by DeepSeek + LangGraph
      </div>
    </footer>
  </div>
</template>

<script setup>
// Application Root Component
</script>
