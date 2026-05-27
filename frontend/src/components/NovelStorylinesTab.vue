<template>
  <div class="card p-6">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-neutral-800 font-semibold text-sm">核心脉络（故事线 / 弧光 / 场景）</h2>
      <div class="flex gap-2">
        <router-link :to="`/novels/${novelId}/graph`" class="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-accent-600">
            <path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
          </svg>
          <span>查看知识图谱</span>
        </router-link>
        <router-link :to="`/novels/${novelId}/storylines`" class="btn-primary text-xs py-1.5 px-3 flex items-center gap-1">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" />
          </svg>
          <span>故事线管理器</span>
        </router-link>
      </div>
    </div>
    <div v-if="storylinesData" class="space-y-6 text-sm">
      <div v-if="storylinesData.storylines?.length">
        <h3 class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-3">故事线分布</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div v-for="sl in storylinesData.storylines" :key="sl.id" class="p-4 rounded-xl bg-neutral-50 border border-neutral-200 flex flex-col justify-between hover:border-neutral-300 transition-colors">
            <div>
              <div class="flex items-center justify-between gap-2 mb-2">
                <span class="font-bold text-neutral-900">{{ sl.name }}</span>
                <span :class="sl.type === 'main' ? 'bg-accent-50 text-accent-600 border border-accent-200 text-[9px] px-2 py-0.5 rounded-full font-bold' : sl.type === 'hidden' ? 'bg-amber-50 text-amber-600 border border-amber-200 text-[9px] px-2 py-0.5 rounded-full font-bold' : 'bg-neutral-100 text-neutral-600 text-[9px] px-2 py-0.5 rounded-full font-bold border border-neutral-200'">{{ sl.type === 'main' ? '主线' : sl.type === 'hidden' ? '暗线' : '支线' }}</span>
              </div>
              <p v-if="sl.description" class="text-neutral-500 text-xs mt-1.5 leading-relaxed">{{ sl.description }}</p>
            </div>
          </div>
        </div>
      </div>
      <div v-if="storylinesData.character_arcs?.length">
        <h3 class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-3">人物弧光轨迹</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div v-for="arc in storylinesData.character_arcs" :key="arc.id" class="p-3.5 rounded-xl bg-neutral-50 border border-neutral-200 hover:border-neutral-300 transition-colors flex items-start gap-3">
            <span :class="arc.arc_type === 'growth' ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : arc.arc_type === 'fall' ? 'bg-rose-50 text-rose-600 border-rose-200' : 'bg-blue-50 text-blue-600 border-blue-200'" class="shrink-0 text-[9px] px-2 py-0.5 rounded-md border font-bold">{{ arc.arc_type === 'growth' ? '成长' : arc.arc_type === 'fall' ? '沉沦' : '蜕变' }}</span>
            <p class="text-neutral-700 text-xs leading-relaxed">{{ arc.description || '无具体弧光轨迹描述' }}</p>
          </div>
        </div>
      </div>
      <div v-if="storylinesData.scenes?.length">
        <h3 class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-2.5">生成创作场景</h3>
        <div class="flex flex-wrap gap-2">
          <div v-for="sc in storylinesData.scenes" :key="sc.id" class="px-3 py-1.5 bg-neutral-50 border border-neutral-200 rounded-xl text-xs font-medium text-neutral-700">
            <span class="font-bold text-neutral-900">{{ sc.name }}</span>
            <span v-if="sc.location" class="text-accent-600 font-semibold ml-1.5 font-mono">@{{ sc.location }}</span>
          </div>
        </div>
      </div>
      <p v-if="!storylinesData.storylines?.length && !storylinesData.character_arcs?.length && !storylinesData.scenes?.length" class="text-neutral-500 py-6 text-center">暂无脉络数据生成。</p>
    </div>
    <p v-else class="text-neutral-500 py-6 text-center">系统将在故事线管理器中创建并建立您的故事线、人物弧光和创作场景之间的关联映射。</p>
  </div>
</template>

<script setup>
defineProps({
  novelId: String,
  storylinesData: Object,
})
</script>
