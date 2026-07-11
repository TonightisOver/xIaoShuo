<template>
  <div class="max-w-5xl mx-auto px-6 py-10 bg-neutral-50 min-h-screen">
    <div v-if="loading" class="flex flex-col items-center justify-center py-32 space-y-4">
      <div class="w-10 h-10 border-4 border-accent-600 border-t-transparent rounded-full animate-spin"></div>
      <p class="text-sm text-neutral-500 font-medium">作品数据加载中...</p>
    </div>

    <div v-else-if="!novel" class="text-center py-20 card p-8">
      <p class="text-neutral-500 text-lg mb-4">该小说不存在或已被移除</p>
      <router-link to="/" class="btn-secondary">返回书架</router-link>
    </div>

    <template v-else>
      <!-- Top header layout -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div class="flex items-center gap-2 mb-1.5">
            <router-link to="/" class="text-xs text-accent-600 hover:text-accent-700 font-semibold flex items-center gap-1 group">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
              返回书架
            </router-link>
          </div>
          <h1 class="text-3xl font-extrabold text-neutral-900 tracking-tight">{{ novel.title }}</h1>
          <p class="text-xs text-neutral-500 mt-2 flex items-center gap-2 font-medium">
            <span class="bg-neutral-100 text-neutral-700 px-2 py-0.5 rounded-md border border-neutral-200">{{ novel.novel_type }}</span>
            <span class="text-neutral-300">|</span>
            <span>{{ (novel.target_words / 10000).toFixed(0) }}万字创作目标</span>
          </p>
        </div>

        <div class="flex items-center gap-3">
          <!-- Action Buttons (Shown when not generating) -->
          <button
            v-if="novel.status === 'draft' || novel.status === 'completed' || novel.status === 'failed'"
            @click="generate"
            class="btn-secondary text-sm flex items-center gap-1.5"
            :disabled="generating"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4 text-accent-600">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
            </svg>
            <span>{{ generating ? '启动中...' : (novel.status === 'draft' ? '分步生成' : '重新分步生成') }}</span>
          </button>

          <button
            v-if="novel.status === 'draft' || novel.status === 'completed' || novel.status === 'failed'"
            @click="fullGenerate"
            class="btn-primary text-sm flex items-center gap-1.5"
            :disabled="fullGenerating"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
            </svg>
            <span>{{ fullGenerating ? '启动中...' : '一键全功能生成' }}</span>
          </button>

          <router-link to="/" class="btn-secondary text-sm">返回书架</router-link>

          <router-link
            :to="`/novels/${novelId}/foreshadows`"
            class="btn-secondary text-sm flex items-center gap-1.5"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4 text-accent-600">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.091-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.091L9 5.25l.813 2.846a4.5 4.5 0 003.091 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.091zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.456-2.456L14.25 6l1.035-.259a3.375 3.375 0 002.456-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
            </svg>
            <span>伏笔追踪</span>
          </router-link>

          <router-link
            :to="`/novels/${novelId}/knowledge-graph`"
            class="btn-secondary text-sm flex items-center gap-1.5"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-purple-600">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m14.559 0A8.965 8.965 0 0012 3.5a8.965 8.965 0 00-7.716 4.082m14.559 0A8.973 8.973 0 0112 20.5a8.973 8.973 0 01-7.716-4.082" />
            </svg>
            <span>知识图谱</span>
          </router-link>

          <button
            @click="showExportDialog = true"
            class="btn-secondary text-sm flex items-center gap-1.5"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            <span>导出</span>
          </button>
        </div>
      </div>

      <!-- Active Generation Alert Banner -->
      <div v-if="novel.status === 'generating'" class="mb-8 p-4 rounded-xl bg-blue-50 border border-blue-200 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div class="flex items-start gap-3">
          <div class="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center text-blue-600 shrink-0 border border-blue-200">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-5 h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
            </svg>
          </div>
          <div>
            <h3 class="text-sm font-bold text-blue-800">小说正在高速创作生成中</h3>
            <p class="text-xs text-blue-600 mt-1 leading-relaxed">
              AI 创作流水线正在实时编写力量体系、大纲设定与故事线章节，您可以直接点击右侧按钮进入任务控制台监控进度。
            </p>
          </div>
        </div>
        <router-link
          v-if="novel.active_task_id"
          :to="`/task/${novel.active_task_id}`"
          class="btn-primary text-xs py-2 px-4 shrink-0 flex items-center gap-1.5"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
          </svg>
          <span>进入监控控制台</span>
        </router-link>
      </div>

      <!-- Tabs Navigation -->
      <div class="border-b border-neutral-200 mb-8 sticky top-16 z-40 bg-white">
        <nav class="flex gap-6 overflow-x-auto scrollbar-none py-1">
          <button v-for="tab in tabs" :key="tab.id"
            :class="[
              'pb-3 text-sm font-semibold tracking-wide border-b-2 transition-all duration-200 whitespace-nowrap',
              activeTab === tab.id
                ? 'border-accent-600 text-accent-600 font-bold'
                : 'border-transparent text-neutral-500 hover:text-neutral-700'
            ]"
            @click="activeTab = tab.id"
          >{{ tab.label }}</button>
        </nav>
      </div>

      <!-- Tab Content: Overview -->
      <div v-if="activeTab === 'overview'" class="card p-6">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-neutral-800 font-semibold text-sm">作品概览</h2>
          <div class="flex gap-2">
            <button v-if="!editingOverview" @click="startEditOverview" class="btn-secondary text-xs py-1.5 px-3">编辑设定</button>
            <template v-else>
              <button @click="saveOverview" class="btn-primary text-xs py-1.5 px-3" :disabled="savingOverview">{{ savingOverview ? '保存中...' : '保存' }}</button>
              <button @click="cancelEditOverview" class="btn-secondary text-xs py-1.5 px-3">取消</button>
            </template>
          </div>
        </div>
        <dl class="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
          <div class="p-4 rounded-xl bg-neutral-50 border border-neutral-200">
            <dt class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-1">作品状态</dt>
            <dd class="font-semibold text-neutral-700">
              <span :class="'badge-' + statusClass(novel.status)">{{ statusLabel }}</span>
            </dd>
          </div>
          <div class="p-4 rounded-xl bg-neutral-50 border border-neutral-200">
            <dt class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-1">题材类别</dt>
            <dd class="font-semibold text-neutral-700">{{ novel.novel_type }}</dd>
          </div>
          <div class="col-span-1 md:col-span-2 p-4 rounded-xl bg-neutral-50 border border-neutral-200">
            <dt class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-1.5">作品标题</dt>
            <dd class="mt-1">
              <input v-if="editingOverview" v-model="overviewForm.title" class="input text-sm w-full" maxlength="200" />
              <span v-else class="font-extrabold text-neutral-900 text-base">{{ novel.title }}</span>
            </dd>
          </div>
          <div class="col-span-1 md:col-span-2 p-4 rounded-xl bg-neutral-50 border border-neutral-200">
            <dt class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-1.5">核心创意 / 简介</dt>
            <dd class="mt-1">
              <textarea v-if="editingOverview" v-model="overviewForm.idea" class="input text-sm w-full min-h-[100px] resize-y" rows="5" maxlength="2000"></textarea>
              <span v-else class="whitespace-pre-wrap text-neutral-700 leading-relaxed">{{ novel.idea || '暂无作品创意设定。' }}</span>
            </dd>
          </div>
          <div class="p-4 rounded-xl bg-neutral-50 border border-neutral-200">
            <dt class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-1">已登场人物</dt>
            <dd class="font-semibold text-neutral-700">{{ novel.characters_count }} 名主要角色</dd>
          </div>
          <div class="p-4 rounded-xl bg-neutral-50 border border-neutral-200">
            <dt class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-1">世界设定</dt>
            <dd class="font-semibold text-neutral-700">{{ novel.world_setting ? '已架构完成' : '暂未生成' }}</dd>
          </div>
        </dl>
        <p v-if="overviewSaved" class="text-xs text-emerald-600 font-bold mt-4 flex items-center gap-1">
          <span>已成功保存修改</span>
        </p>
        <p v-if="overviewError" class="text-xs text-rose-600 font-semibold mt-4">{{ overviewError }}</p>
      </div>

      <!-- Tab Content: Outlines -->
      <div v-if="activeTab === 'outlines'" class="card p-6">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-neutral-800 font-semibold text-sm">三级大纲体系</h2>
          <router-link :to="`/novels/${novelId}/outlines`" class="btn-primary text-sm flex items-center gap-1.5">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
            </svg>
            <span>大纲编辑器</span>
          </router-link>
        </div>
        <div v-if="outlineTree" class="space-y-6 text-sm">
          <div v-if="outlineTree.master" class="p-5 rounded-xl bg-neutral-50 border border-neutral-200">
            <h3 class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-2.5">主线总纲</h3>
            <p v-if="outlineTree.master.content?.premise" class="font-bold text-neutral-900 text-sm leading-relaxed mb-3">{{ outlineTree.master.content.premise }}</p>
            <div class="space-y-2 pl-4 border-l-2 border-neutral-200 text-xs">
              <p v-if="outlineTree.master.content?.main_conflict" class="text-neutral-500"><span class="font-semibold text-neutral-700">核心冲突：</span>{{ outlineTree.master.content.main_conflict }}</p>
              <p v-if="outlineTree.master.content?.ending" class="text-neutral-500"><span class="font-semibold text-neutral-700">宏大结局：</span>{{ outlineTree.master.content.ending }}</p>
            </div>
          </div>

          <div v-if="outlineTree.volumes?.length" class="space-y-4">
            <h3 class="text-xs text-neutral-500 font-medium uppercase tracking-wider">分卷提纲（{{ outlineTree.volumes.length }} 卷）</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div v-for="vol in outlineTree.volumes" :key="vol.id" class="p-4 rounded-xl bg-white border border-neutral-200 hover:border-neutral-300 transition-colors">
                <p class="font-bold text-neutral-900 text-sm">第{{ vol.volume_number }}卷：{{ vol.content?.title || '卷设定未命名' }}</p>
                <p class="text-neutral-500 text-xs mt-2 leading-relaxed line-clamp-3">{{ vol.content?.summary || '暂无提纲摘要' }}</p>
                <div class="mt-4 flex items-center justify-between text-[10px] text-neutral-400 font-bold tracking-wider">
                  <span>{{ vol.chapters?.length || 0 }} 个章节规划</span>
                </div>
              </div>
            </div>
          </div>

          <p v-if="!outlineTree.master && !outlineTree.volumes?.length" class="text-neutral-500 py-6 text-center">暂无三级大纲数据，您可以通过大纲编辑器或重新全功能生成来确立。</p>
        </div>
        <p v-else class="text-sm text-neutral-500 py-6 text-center">系统将在大纲编辑器内管理您的总纲、卷纲与章节大纲结构体系。</p>
      </div>

      <!-- Tab Content: World Setting -->
      <div v-if="activeTab === 'world'" class="card p-6">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-neutral-800 font-semibold text-sm">世界观宏大设定</h2>
          <router-link :to="`/novels/${novelId}/world`" class="btn-secondary text-sm flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
            </svg>
            <span>编辑设定</span>
          </router-link>
        </div>
        <div v-if="world" class="space-y-6 text-sm">
          <div v-if="world.background" class="p-4 rounded-xl bg-neutral-50 border border-neutral-200">
            <h3 class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-2">世界背景与底层神话</h3>
            <p class="mt-1 text-neutral-700 leading-relaxed whitespace-pre-wrap">{{ world.background }}</p>
          </div>
          <div v-if="world.geography" class="p-4 rounded-xl bg-neutral-50 border border-neutral-200">
            <h3 class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-2">地理环境与灵力分布</h3>
            <p class="mt-1 text-neutral-700 leading-relaxed whitespace-pre-wrap">{{ world.geography }}</p>
          </div>
          <div v-if="world.culture" class="p-4 rounded-xl bg-neutral-50 border border-neutral-200">
            <h3 class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-2">教派宗门与文化体系</h3>
            <p class="mt-1 text-neutral-700 leading-relaxed whitespace-pre-wrap">{{ world.culture }}</p>
          </div>
          <div v-if="world.rules" class="p-4 rounded-xl bg-neutral-50 border border-neutral-200">
            <h3 class="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-2">天道规则与能量演变</h3>
            <p class="mt-1 text-neutral-700 leading-relaxed whitespace-pre-wrap">{{ world.rules }}</p>
          </div>
          <p v-if="!world.background && !world.rules" class="text-neutral-500 py-6 text-center">暂未生成世界观设定体系，点击上方"编辑设定"即可手工创建或等待 AI 提炼。</p>
        </div>
        <p v-else class="text-neutral-500 py-6 text-center">暂无世界设定架构。</p>
      </div>

      <!-- Tab Content: Power Systems -->
      <div v-if="activeTab === 'power-systems'" class="space-y-4">
        <div class="flex justify-between items-center mb-2">
          <h2 class="text-neutral-800 font-semibold text-sm">力量与境界法则</h2>
        </div>
        <div v-if="powerSystems.length === 0" class="card p-8 text-center text-neutral-500">
          暂无设定的境界或灵力修炼体系
        </div>
        <div v-for="ps in powerSystems" :key="ps.id" class="card p-5">
          <h3 class="font-bold text-neutral-900 text-base border-b border-neutral-200 pb-3 mb-4 flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-accent-600"></span>
            <span>{{ ps.name }}</span>
          </h3>
          <p v-if="ps.description" class="text-xs text-neutral-500 mb-4 leading-relaxed bg-neutral-50 p-3 rounded-lg border border-neutral-200">{{ ps.description }}</p>
          <div v-if="ps.levels?.length" class="space-y-3">
            <div v-for="(lvl, i) in ps.levels" :key="i" class="flex flex-col sm:flex-row sm:items-start gap-2 text-xs py-3 border-b border-neutral-100 last:border-0 pl-1">
              <span class="font-bold text-accent-600 shrink-0 w-24 tracking-wide">第{{ i + 1 }}重：{{ lvl.name }}</span>
              <div class="flex-1 space-y-1">
                <p class="text-neutral-700 leading-relaxed"><span class="text-neutral-500 font-bold">描述：</span>{{ lvl.description }}</p>
                <p v-if="lvl.breakthrough" class="text-amber-600 leading-relaxed font-semibold"><span class="text-neutral-500 font-bold">突破契机：</span>{{ lvl.breakthrough }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab Content: Characters -->
      <div v-if="activeTab === 'characters'" class="space-y-4">
        <div class="flex justify-between items-center mb-2">
          <h2 class="text-neutral-800 font-semibold text-sm">登场人物志</h2>
          <router-link :to="`/novels/${novelId}/characters`" class="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-accent-600">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
            </svg>
            <span>管理人物档案</span>
          </router-link>
        </div>
        <div v-if="characters.length === 0" class="card p-8 text-center text-neutral-500">
          暂无登场主要人物，点击右侧管理添加。
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div v-for="char in characters" :key="char.id" class="card p-5 flex gap-4 hover:border-neutral-300 transition-colors">
            <div class="w-12 h-12 rounded-xl bg-neutral-100 border border-neutral-200 shrink-0 flex items-center justify-center font-bold text-neutral-600 font-serif text-lg">
              {{ char.name ? char.name[0] : '人' }}
            </div>
            <div class="flex-1 space-y-1">
              <div class="flex items-center justify-between gap-2">
                <span class="font-bold text-neutral-900 text-sm">{{ char.name }}</span>
                <span v-if="char.role" class="text-[10px] bg-neutral-100 text-neutral-600 px-2 py-0.5 rounded-md font-bold border border-neutral-200">{{ char.role }}</span>
              </div>
              <p v-if="char.description" class="text-xs text-neutral-500 leading-relaxed mt-2">{{ char.description }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab Content: Chapters -->
      <NovelChaptersTab
        v-if="activeTab === 'chapters'"
        :volumes="volumes"
        :chapters="chapters"
        :novel-id="novelId"
        :novel-title="novel?.title"
        :unassigned-chapters="unassignedChapters"
        :show-range-dialog="showRangeDialog"
        :show-export-dialog="showExportDialog"
        :delete-target="deleteTargetUnassigned"
        @cleanup="cleanupFailedChapters"
        @open-range-dialog="showRangeDialog = true"
        @close-range-dialog="showRangeDialog = false"
        @generate-volume="handleGenerateVolume"
        @delete-chapter="handleDeleteChapter"
        @confirm-delete="confirmDeleteUnassigned"
        @cancel-delete="deleteTargetUnassigned = null"
        @do-delete="doDeleteUnassigned"
        @generate-chapters="onGenerateChapters"
        @close-export-dialog="showExportDialog = false"
      />

      <!-- Tab Content: Storylines / Relations -->
      <NovelStorylinesTab
        v-if="activeTab === 'storylines'"
        :novel-id="novelId"
        :storylines-data="storylinesData"
      />

      <!-- Review Dialog (HITL) -->
      <ReviewDialog
        v-if="reviewDialogVisible"
        :task-id="novel.active_task_id"
        :visible="reviewDialogVisible"
        :auto-close="true"
        @decision="onReviewDecision"
        @cancel="reviewDialogVisible = false"
      />

      <!-- Tab Content: Quality Report -->
      <NovelQualityTab
        v-if="activeTab === 'quality-report'"
        :novel-id="novelId"
      />

      <!-- Tab Content: Conversations -->
      <div v-if="activeTab === 'conversations'" class="space-y-4">
        <div class="flex justify-between items-center mb-2">
          <h2 class="text-neutral-800 font-semibold text-sm">AI 创作对话</h2>
          <button @click="startConversation" class="btn-primary text-xs py-1.5 px-3 flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            <span>开启讨论</span>
          </button>
        </div>
        <div v-if="conversations.length === 0" class="card p-8 text-center text-neutral-500">
          暂无创作对话，点击右上角开启与 AI 深度讨论剧情或人物走向吧。
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <router-link v-for="conv in conversations" :key="conv.id"
            :to="`/novels/${novelId}/conversations/${conv.id}`"
            class="card p-4 block hover:border-neutral-300 transition-colors"
          >
            <div class="flex justify-between items-center gap-3">
              <span class="font-bold text-neutral-900 text-sm truncate pr-2">{{ conv.topic }}</span>
              <span :class="conv.status === 'active' ? 'badge-running' : 'badge-completed'" class="shrink-0 font-bold">
                {{ conv.status === 'active' ? '进行中' : '已归档' }}
              </span>
            </div>
          </router-link>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import NovelChaptersTab from '../components/NovelChaptersTab.vue'
import NovelStorylinesTab from '../components/NovelStorylinesTab.vue'
import NovelQualityTab from '../components/NovelQualityTab.vue'
import ReviewDialog from '../components/ReviewDialog.vue'
import { useNovelData } from '../composables/useNovelData.js'
import { useNovelActions } from '../composables/useNovelActions.js'

const route = useRoute()
const novelId = computed(() => route.params.id)

const { novel, world, characters, chapters, volumes, conversations, powerSystems, storylinesData, outlineTree, loading, fetchAll } = useNovelData(novelId)
const { generating, fullGenerating, deleteTargetUnassigned, generate, fullGenerate, startConversation, handleGenerateVolume, handleGenerateChapters, confirmDeleteUnassigned, doDeleteUnassigned, cleanupFailedChapters } = useNovelActions(novelId, chapters)

const activeTab = ref('overview')
const tabs = computed(() => [
  { id: 'overview', label: '概览' },
  { id: 'outlines', label: '大纲' },
  { id: 'world', label: '世界观' },
  { id: 'power-systems', label: '力量体系' },
  { id: 'characters', label: '人物' },
  { id: 'chapters', label: '章节' },
  { id: 'storylines', label: '故事线' },
  { id: 'quality-report', label: '质量报告' },
  { id: 'conversations', label: '对话' },
])
const showRangeDialog = ref(false)
const showExportDialog = ref(false)
const editingOverview = ref(false)
const savingOverview = ref(false)
const overviewSaved = ref(false)
const overviewError = ref('')
const overviewForm = ref({ title: '', idea: '' })

// HITL 审核对话框
const reviewDialogVisible = ref(false)
const reviewPollingTimer = ref(null)

// 轮询任务审核状态，如有 pending review 自动弹出对话框
async function checkReviewStatus() {
  const taskId = novel.value?.active_task_id
  if (!taskId) return
  try {
    const res = await fetch(`/api/v1/tasks/${taskId}/review`)
    if (!res.ok) return
    const data = await res.json()
    if (data.waiting_for_review) {
      reviewDialogVisible.value = true
      stopReviewPolling()
    }
  } catch { /* 静默忽略 */ }
}

function startReviewPolling() {
  if (reviewPollingTimer.value) return
  checkReviewStatus()
  reviewPollingTimer.value = setInterval(checkReviewStatus, 5000)
}

function stopReviewPolling() {
  if (reviewPollingTimer.value) {
    clearInterval(reviewPollingTimer.value)
    reviewPollingTimer.value = null
  }
}

function onReviewDecision() {
  reviewDialogVisible.value = false
  stopReviewPolling()
  // 延迟刷新，等后端状态更新
  setTimeout(() => { fetchAll() }, 1500)
}

const statusLabel = computed(() => ({ draft: '草稿', generating: '生成中', completed: '已完成', failed: '失败' })[novel.value?.status] || novel.value?.status)
const unassignedChapters = computed(() => chapters.value.filter(c => !c.volume_number))

function statusClass(s) { return { draft: 'pending', generating: 'running', completed: 'completed', failed: 'failed' }[s] || 'pending' }

function startEditOverview() {
  overviewForm.value = { title: novel.value.title || '', idea: novel.value.idea || '' }
  editingOverview.value = true; overviewSaved.value = false; overviewError.value = ''
}
function cancelEditOverview() { editingOverview.value = false }

async function saveOverview() {
  savingOverview.value = true; overviewError.value = ''
  try {
    const res = await fetch(`/api/v1/projects/${novelId.value}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: overviewForm.value.title, idea: overviewForm.value.idea }),
    })
    if (!res.ok) { overviewError.value = (await res.json().catch(() => ({}))).detail || '保存失败'; return }
    novel.value = { ...novel.value, ...overviewForm.value }
    editingOverview.value = false; overviewSaved.value = true
    setTimeout(() => { overviewSaved.value = false }, 2000)
  } finally { savingOverview.value = false }
}

function handleDeleteChapter(chapterNumber) { chapters.value = chapters.value.filter(c => c.chapter_number !== chapterNumber) }
function onGenerateChapters(range) { showRangeDialog.value = false; handleGenerateChapters(range) }

onMounted(() => {
  fetchAll()
  if (novel.value?.status === 'generating') {
    startReviewPolling()
  }
})

onUnmounted(stopReviewPolling)
</script>
