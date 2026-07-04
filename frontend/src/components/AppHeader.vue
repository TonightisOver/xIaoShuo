<template>
  <header class="bg-white border-b border-neutral-200 sticky top-0 z-50">
    <div class="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
      <router-link to="/" class="flex items-center gap-2 hover:opacity-80 transition-opacity select-none">
        <span class="text-lg font-bold text-neutral-900">xIaoShuo</span>
        <span class="text-[10px] bg-neutral-100 text-neutral-500 px-1.5 py-0.5 rounded font-medium">AI 创作平台</span>
      </router-link>
      <nav class="flex items-center gap-5">
        <router-link
          to="/tasks"
          class="text-sm text-neutral-500 hover:text-neutral-900 transition-colors font-medium"
        >
          任务大厅
        </router-link>
        <router-link
          to="/settings/llm"
          class="text-sm text-neutral-500 hover:text-neutral-900 transition-colors font-medium"
        >
          模型配置
        </router-link>
        <router-link
          to="/inspiration"
          class="text-sm text-neutral-500 hover:text-neutral-900 transition-colors font-medium"
        >
          灵感向导
        </router-link>
        <router-link to="/create" class="btn-primary text-sm flex items-center gap-1.5">
          <span>开启创作</span>
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
        </router-link>
      </nav>
    </div>
  </header>
</template>

<script setup>
</script>
