<template>
  <div class="max-w-5xl mx-auto px-6 py-10">
    <div v-if="loading" class="flex flex-col items-center justify-center py-32 space-y-4">
      <div class="w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
      <p class="text-sm text-slate-400 font-medium">作品数据加载中...</p>
    </div>
    
    <div v-else-if="!novel" class="text-center py-20 glass-panel rounded-3xl p-8 border border-slate-900">
      <p class="text-slate-400 text-lg mb-4">该小说不存在或已被移除</p>
      <router-link to="/" class="btn-secondary">返回书架</router-link>
    </div>

    <template v-else>
      <!-- Top header layout -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div class="flex items-center gap-2 mb-1.5">
            <router-link to="/" class="text-xs text-purple-400 hover:text-purple-300 font-semibold flex items-center gap-1 group">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
              返回书架
            </router-link>
          </div>
          <h1 class="text-3xl font-extrabold text-slate-100 tracking-tight">{{ novel.title }}</h1>
          <p class="text-xs text-slate-400 mt-2 flex items-center gap-2 font-medium">
            <span class="bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded-md border border-purple-500/20">{{ novel.novel_type }}</span>
            <span class="text-slate-700">|</span>
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
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4 text-purple-400">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
            </svg>
            <span>{{ generating ? '启动中...' : (novel.status === 'draft' ? '分步生成' : '重新分步生成') }}</span>
          </button>
          
          <button 
            v-if="novel.status === 'draft' || novel.status === 'completed' || novel.status === 'failed'" 
            @click="fullGenerate" 
            class="btn-primary text-sm flex items-center gap-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-500/10 shadow-lg" 
            :disabled="fullGenerating"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
            </svg>
            <span>{{ fullGenerating ? '启动中...' : '一键全功能生成' }}</span>
          </button>
          
          <router-link to="/" class="btn-secondary text-sm">返回书架</router-link>
        </div>
      </div>

      <!-- Active Generation Alert Banner -->
      <div v-if="novel.status === 'generating'" class="generating-halo mb-8 p-5 rounded-2xl bg-purple-500/10 border border-purple-500/30 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div class="flex items-start gap-3">
          <div class="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center text-purple-400 shrink-0 border border-purple-500/30 animate-pulse">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-5 h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
            </svg>
          </div>
          <div>
            <h3 class="text-sm font-bold text-slate-200">小说正在高速创作生成中</h3>
            <p class="text-xs text-slate-400 mt-1 leading-relaxed">
              AI 创作流水线正在实时编写力量体系、大纲设定与故事线章节，您可以直接点击右侧按钮进入任务控制台监控进度。
            </p>
          </div>
        </div>
        <router-link
          v-if="novel.active_task_id"
          :to="`/task/${novel.active_task_id}`"
          class="btn-primary text-xs py-2 px-4 shadow-lg shrink-0 flex items-center gap-1.5"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5 animate-spin">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
          </svg>
          <span>进入监控控制台</span>
        </router-link>
      </div>

      <!-- Tabs Navigation -->
      <div class="border-b border-slate-900/60 mb-8 sticky top-16 z-40 bg-slate-950/80 backdrop-blur-md">
        <nav class="flex gap-6 overflow-x-auto scrollbar-none py-1">
          <button v-for="tab in tabs" :key="tab.id"
            :class="[
              'pb-3 text-sm font-semibold tracking-wide border-b-2 transition-all duration-200 whitespace-nowrap', 
              activeTab === tab.id 
                ? 'border-purple-500 text-purple-400 font-bold' 
                : 'border-transparent text-slate-400 hover:text-slate-200'
            ]"
            @click="activeTab = tab.id"
          >{{ tab.label }}</button>
        </nav>
      </div>

      <!-- Tab Content: Overview -->
      <div v-if="activeTab === 'overview'" class="card p-6 bg-slate-900/40 backdrop-blur-md">
        <div class="flex justify-between items-center mb-6">
          <h2 class="font-bold text-slate-200 text-base">作品概览</h2>
          <div class="flex gap-2">
            <button v-if="!editingOverview" @click="startEditOverview" class="btn-secondary text-xs py-1.5 px-3">编辑设定</button>
            <template v-else>
              <button @click="saveOverview" class="btn-primary text-xs py-1.5 px-3" :disabled="savingOverview">{{ savingOverview ? '保存中...' : '保存' }}</button>
              <button @click="cancelEditOverview" class="btn-secondary text-xs py-1.5 px-3">取消</button>
            </template>
          </div>
        </div>
        <dl class="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
          <div class="p-4 rounded-xl bg-slate-950/30 border border-slate-900/60">
            <dt class="text-slate-500 font-bold text-xs uppercase tracking-wider mb-1">作品状态</dt>
            <dd class="font-semibold text-slate-300">
              <span :class="'badge-' + statusClass(novel.status)">{{ statusLabel }}</span>
            </dd>
          </div>
          <div class="p-4 rounded-xl bg-slate-950/30 border border-slate-900/60">
            <dt class="text-slate-500 font-bold text-xs uppercase tracking-wider mb-1">题材类别</dt>
            <dd class="font-semibold text-slate-300">{{ novel.novel_type }}</dd>
          </div>
          <div class="col-span-1 md:col-span-2 p-4 rounded-xl bg-slate-950/30 border border-slate-900/60">
            <dt class="text-slate-500 font-bold text-xs uppercase tracking-wider mb-1.5">作品标题</dt>
            <dd class="mt-1">
              <input v-if="editingOverview" v-model="overviewForm.title" class="input text-sm w-full" maxlength="200" />
              <span v-else class="font-extrabold text-slate-100 text-base">{{ novel.title }}</span>
            </dd>
          </div>
          <div class="col-span-1 md:col-span-2 p-4 rounded-xl bg-slate-950/30 border border-slate-900/60">
            <dt class="text-slate-500 font-bold text-xs uppercase tracking-wider mb-1.5">核心创意 / 简介</dt>
            <dd class="mt-1">
              <textarea v-if="editingOverview" v-model="overviewForm.idea" class="input text-sm w-full min-h-[100px] resize-y" rows="5" maxlength="2000"></textarea>
              <span v-else class="whitespace-pre-wrap text-slate-300 leading-relaxed">{{ novel.idea || '暂无作品创意设定。' }}</span>
            </dd>
          </div>
          <div class="p-4 rounded-xl bg-slate-950/30 border border-slate-900/60">
            <dt class="text-slate-500 font-bold text-xs uppercase tracking-wider mb-1">已登场人物</dt>
            <dd class="font-semibold text-slate-300">{{ novel.characters_count }} 名主要角色</dd>
          </div>
          <div class="p-4 rounded-xl bg-slate-950/30 border border-slate-900/60">
            <dt class="text-slate-500 font-bold text-xs uppercase tracking-wider mb-1">世界设定</dt>
            <dd class="font-semibold text-slate-300">{{ novel.world_setting ? '已架构完成' : '暂未生成' }}</dd>
          </div>
        </dl>
        <p v-if="overviewSaved" class="text-xs text-emerald-400 font-bold mt-4 flex items-center gap-1">
          <span>已成功保存修改</span>
        </p>
        <p v-if="overviewError" class="text-xs text-rose-400 font-semibold mt-4">{{ overviewError }}</p>
      </div>

      <!-- Tab Content: Outlines -->
      <div v-if="activeTab === 'outlines'" class="card p-6 bg-slate-900/40 backdrop-blur-md">
        <div class="flex justify-between items-center mb-6">
          <h2 class="font-bold text-slate-200 text-base">三级大纲体系</h2>
          <router-link :to="`/novels/${novelId}/outlines`" class="btn-primary text-sm flex items-center gap-1.5">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
            </svg>
            <span>大纲编辑器</span>
          </router-link>
        </div>
        <div v-if="outlineTree" class="space-y-6 text-sm">
          <div v-if="outlineTree.master" class="p-5 rounded-2xl bg-slate-950/30 border border-slate-900">
            <h3 class="text-purple-400 font-extrabold text-xs uppercase tracking-wider mb-2.5">主线总纲</h3>
            <p v-if="outlineTree.master.content?.premise" class="font-bold text-slate-200 text-sm leading-relaxed mb-3">{{ outlineTree.master.content.premise }}</p>
            <div class="space-y-2 pl-4 border-l-2 border-slate-800 text-xs">
              <p v-if="outlineTree.master.content?.main_conflict" class="text-slate-400"><span class="font-semibold text-slate-300">核心冲突：</span>{{ outlineTree.master.content.main_conflict }}</p>
              <p v-if="outlineTree.master.content?.ending" class="text-slate-400"><span class="font-semibold text-slate-300">宏大结局：</span>{{ outlineTree.master.content.ending }}</p>
            </div>
          </div>
          
          <div v-if="outlineTree.volumes?.length" class="space-y-4">
            <h3 class="text-slate-400 font-bold text-xs uppercase tracking-wider">分卷提纲（{{ outlineTree.volumes.length }} 卷）</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div v-for="vol in outlineTree.volumes" :key="vol.id" class="p-4 rounded-xl bg-slate-950/20 border border-slate-900/60 hover:border-purple-500/20 hover:bg-slate-950/40 transition-all duration-300">
                <p class="font-extrabold text-slate-200 text-sm">第{{ vol.volume_number }}卷：{{ vol.content?.title || '卷设定未命名' }}</p>
                <p class="text-slate-400 text-xs mt-2 leading-relaxed line-clamp-3">{{ vol.content?.summary || '暂无提纲摘要' }}</p>
                <div class="mt-4 flex items-center justify-between text-[10px] text-slate-500 font-bold tracking-wider">
                  <span>{{ vol.chapters?.length || 0 }} 个章节规划</span>
                </div>
              </div>
            </div>
          </div>
          
          <p v-if="!outlineTree.master && !outlineTree.volumes?.length" class="text-slate-500 py-6 text-center">暂无三级大纲数据，您可以通过大纲编辑器或重新全功能生成来确立。</p>
        </div>
        <p v-else class="text-sm text-slate-500 py-6 text-center">系统将在大纲编辑器内管理您的总纲、卷纲与章节大纲结构体系。</p>
      </div>

      <!-- Tab Content: World Setting -->
      <div v-if="activeTab === 'world'" class="card p-6 bg-slate-900/40 backdrop-blur-md">
        <div class="flex justify-between items-center mb-6">
          <h2 class="font-bold text-slate-200 text-base">世界观宏大设定</h2>
          <router-link :to="`/novels/${novelId}/world`" class="btn-secondary text-sm flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
            </svg>
            <span>编辑设定</span>
          </router-link>
        </div>
        <div v-if="world" class="space-y-6 text-sm">
          <div v-if="world.background" class="p-4 rounded-xl bg-slate-950/20 border border-slate-900">
            <h3 class="text-purple-400 font-extrabold text-xs uppercase tracking-wider mb-2">世界背景与底层神话</h3>
            <p class="mt-1 text-slate-300 leading-relaxed whitespace-pre-wrap">{{ world.background }}</p>
          </div>
          <div v-if="world.geography" class="p-4 rounded-xl bg-slate-950/20 border border-slate-900">
            <h3 class="text-purple-400 font-extrabold text-xs uppercase tracking-wider mb-2">地理环境与灵力分布</h3>
            <p class="mt-1 text-slate-300 leading-relaxed whitespace-pre-wrap">{{ world.geography }}</p>
          </div>
          <div v-if="world.culture" class="p-4 rounded-xl bg-slate-950/20 border border-slate-900">
            <h3 class="text-purple-400 font-extrabold text-xs uppercase tracking-wider mb-2">教派宗门与文化体系</h3>
            <p class="mt-1 text-slate-300 leading-relaxed whitespace-pre-wrap">{{ world.culture }}</p>
          </div>
          <div v-if="world.rules" class="p-4 rounded-xl bg-slate-950/20 border border-slate-900">
            <h3 class="text-purple-400 font-extrabold text-xs uppercase tracking-wider mb-2">天道规则与能量演变</h3>
            <p class="mt-1 text-slate-300 leading-relaxed whitespace-pre-wrap">{{ world.rules }}</p>
          </div>
          <p v-if="!world.background && !world.rules" class="text-slate-500 py-6 text-center">暂未生成世界观设定体系，点击上方“编辑设定”即可手工创建或等待 AI 提炼。</p>
        </div>
        <p v-else class="text-slate-500 py-6 text-center">暂无世界设定架构。</p>
      </div>

      <!-- Tab Content: Power Systems -->
      <div v-if="activeTab === 'power-systems'" class="space-y-4">
        <div class="flex justify-between items-center mb-2">
          <h2 class="font-bold text-slate-200 text-base">力量与境界法则</h2>
        </div>
        <div v-if="powerSystems.length === 0" class="card p-8 text-center text-slate-500 bg-slate-900/40">
          暂无设定的境界或灵力修炼体系
        </div>
        <div v-for="ps in powerSystems" :key="ps.id" class="card p-5 bg-slate-900/40 border-slate-800">
          <h3 class="font-extrabold text-slate-200 text-base border-b border-slate-800 pb-3 mb-4 flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
            <span>{{ ps.name }}</span>
          </h3>
          <p v-if="ps.description" class="text-xs text-slate-400 mb-4 leading-relaxed bg-slate-950/20 p-3 rounded-lg border border-slate-900">{{ ps.description }}</p>
          <div v-if="ps.levels?.length" class="space-y-3">
            <div v-for="(lvl, i) in ps.levels" :key="i" class="flex flex-col sm:flex-row sm:items-start gap-2 text-xs py-3 border-b border-slate-800/60 last:border-0 pl-1">
              <span class="font-extrabold text-purple-400 shrink-0 w-24 tracking-wide">第{{ i + 1 }}重：{{ lvl.name }}</span>
              <div class="flex-1 space-y-1">
                <p class="text-slate-300 leading-relaxed"><span class="text-slate-500 font-bold">描述：</span>{{ lvl.description }}</p>
                <p v-if="lvl.breakthrough" class="text-amber-400/80 leading-relaxed font-semibold"><span class="text-slate-500 font-bold">突破契机：</span>{{ lvl.breakthrough }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab Content: Characters -->
      <div v-if="activeTab === 'characters'" class="space-y-4">
        <div class="flex justify-between items-center mb-2">
          <h2 class="font-bold text-slate-200 text-base">登场人物志</h2>
          <router-link :to="`/novels/${novelId}/characters`" class="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-purple-400">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
            </svg>
            <span>管理人物档案</span>
          </router-link>
        </div>
        <div v-if="characters.length === 0" class="card p-8 text-center text-slate-500 bg-slate-900/40">
          暂无登场主要人物，点击右侧管理添加。
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div v-for="char in characters" :key="char.id" class="card p-5 bg-slate-900/40 border-slate-800 flex gap-4 hover:border-purple-500/20 transition-all duration-300">
            <!-- Icon/Avatar placeholder -->
            <div class="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 shrink-0 flex items-center justify-center font-bold text-purple-300 font-serif text-lg">
              {{ char.name ? char.name[0] : '人' }}
            </div>
            <div class="flex-1 space-y-1">
              <div class="flex items-center justify-between gap-2">
                <span class="font-extrabold text-slate-200 text-sm">{{ char.name }}</span>
                <span v-if="char.role" class="text-[10px] bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded-md font-bold border border-purple-500/20">{{ char.role }}</span>
              </div>
              <p v-if="char.description" class="text-xs text-slate-400 leading-relaxed mt-2">{{ char.description }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab Content: Chapters -->
      <div v-if="activeTab === 'chapters'" class="space-y-6">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h2 class="font-bold text-slate-200 text-base">小说正文章节</h2>
          <div class="flex items-center gap-3">
            <button @click="showRangeDialog = true" class="btn-secondary text-xs py-2 px-4 flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-purple-400">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              <span>按范围重新生成章节</span>
            </button>
          </div>
        </div>

        <!-- Volume List Component -->
        <VolumeList
          v-if="volumes.length"
          :volumes="volumes"
          :chapters="chapters"
          :novel-id="novelId"
          @generate-volume="handleGenerateVolume"
          @delete-chapter="handleDeleteChapter"
        />

        <!-- Unassigned Chapters List -->
        <div v-if="unassignedChapters.length" class="mt-6">
          <h3 v-if="volumes.length" class="text-sm font-medium text-gray-400 mb-3 pl-1">未分卷章节</h3>
          <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y divide-gray-50">
            <div v-for="ch in unassignedChapters" :key="ch.id"
              class="flex items-center justify-between px-6 py-3.5 hover:bg-gray-50/50 transition-colors group"
            >
              <router-link
                :to="`/novels/${novelId}/chapters/${ch.chapter_number}`"
                class="flex-1 flex items-center gap-3 min-w-0"
              >
                <span class="text-sm text-gray-400 font-mono w-6 shrink-0">{{ ch.chapter_number }}</span>
                <span class="text-sm font-medium text-gray-800 truncate">{{ ch.title }}</span>
              </router-link>
              <div class="flex items-center gap-3 shrink-0">
                <span class="text-xs text-gray-400 font-mono">{{ ch.word_count || 0 }} 字</span>
                <button
                  @click="confirmDeleteUnassigned(ch)"
                  class="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-500 transition-all p-1 rounded"
                  title="删除章节"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
                    <path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty Chapters -->
        <div v-if="!volumes.length && !chapters.length" class="bg-white rounded-2xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
          尚未开始正文章节的生成。您可以点击右上角"一键全功能生成"或进行分步设定创建。
        </div>

        <!-- Chapter Range Selector Modal Dialog -->
        <ChapterRangeDialog
          :visible="showRangeDialog"
          @close="showRangeDialog = false"
          @generate="handleGenerateChapters"
        />

        <!-- Delete Confirmation Modal for Unassigned Chapters -->
        <Teleport to="body">
          <div v-if="deleteTargetUnassigned" class="fixed inset-0 z-50 flex items-center justify-center">
            <div class="absolute inset-0 bg-black/20 backdrop-blur-sm" @click="deleteTargetUnassigned = null"></div>
            <div class="relative bg-white rounded-2xl shadow-xl p-6 w-80 mx-4">
              <h3 class="text-base font-semibold text-gray-900 mb-2">确认删除</h3>
              <p class="text-sm text-gray-500 mb-5">
                确定要删除「第{{ deleteTargetUnassigned.chapter_number }}章：{{ deleteTargetUnassigned.title }}」吗？此操作不可撤销。
              </p>
              <div class="flex gap-3 justify-end">
                <button @click="deleteTargetUnassigned = null" class="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 rounded-lg hover:bg-gray-100 transition-colors">
                  取消
                </button>
                <button @click="doDeleteUnassigned" class="px-4 py-2 text-sm font-medium text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors">
                  删除
                </button>
              </div>
            </div>
          </div>
        </Teleport>
      </div>

      <!-- Tab Content: Storylines / Relations -->
      <div v-if="activeTab === 'storylines'" class="card p-6 bg-slate-900/40 backdrop-blur-md">
        <div class="flex justify-between items-center mb-6">
          <h2 class="font-bold text-slate-200 text-base">核心脉络（故事线 / 弧光 / 场景）</h2>
          <div class="flex gap-2">
            <router-link :to="`/novels/${novelId}/graph`" class="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-purple-400">
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
            <h3 class="text-slate-400 font-bold text-xs uppercase tracking-wider mb-3">故事线分布</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div v-for="sl in storylinesData.storylines" :key="sl.id" class="p-4 rounded-xl bg-slate-950/20 border border-slate-900/60 flex flex-col justify-between hover:border-purple-500/20 transition-all duration-300">
                <div>
                  <div class="flex items-center justify-between gap-2 mb-2">
                    <span class="font-extrabold text-slate-200">{{ sl.name }}</span>
                    <span :class="sl.type === 'main' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20 text-[9px] px-2 py-0.5 rounded-full font-bold' : sl.type === 'hidden' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[9px] px-2 py-0.5 rounded-full font-bold' : 'bg-slate-800 text-slate-400 text-[9px] px-2 py-0.5 rounded-full font-bold'">{{ sl.type === 'main' ? '主线' : sl.type === 'hidden' ? '暗线' : '支线' }}</span>
                  </div>
                  <p v-if="sl.description" class="text-slate-400 text-xs mt-1.5 leading-relaxed">{{ sl.description }}</p>
                </div>
              </div>
            </div>
          </div>
          
          <div v-if="storylinesData.character_arcs?.length">
            <h3 class="text-slate-400 font-bold text-xs uppercase tracking-wider mb-3">人物弧光轨迹</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div v-for="arc in storylinesData.character_arcs" :key="arc.id" class="p-3.5 rounded-xl bg-slate-950/20 border border-slate-900/60 hover:border-purple-500/20 transition-all duration-300 flex items-start gap-3">
                <span :class="arc.arc_type === 'growth' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : arc.arc_type === 'fall' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-blue-500/10 text-blue-400 border-blue-500/20'" class="shrink-0 text-[9px] px-2 py-0.5 rounded-md border font-bold">
                  {{ arc.arc_type === 'growth' ? '成长' : arc.arc_type === 'fall' ? '沉沦' : '蜕变' }}
                </span>
                <p class="text-slate-300 text-xs leading-relaxed">{{ arc.description || '无具体弧光轨迹描述' }}</p>
              </div>
            </div>
          </div>
          
          <div v-if="storylinesData.scenes?.length">
            <h3 class="text-slate-400 font-bold text-xs uppercase tracking-wider mb-2.5">生成创作场景</h3>
            <div class="flex flex-wrap gap-2">
              <div v-for="sc in storylinesData.scenes" :key="sc.id" class="px-3 py-1.5 bg-slate-950/40 border border-slate-800 rounded-xl text-xs font-medium text-slate-300">
                <span class="font-extrabold text-slate-200">{{ sc.name }}</span>
                <span v-if="sc.location" class="text-purple-400 font-semibold ml-1.5 font-mono">@{{ sc.location }}</span>
              </div>
            </div>
          </div>
          
          <p v-if="!storylinesData.storylines?.length && !storylinesData.character_arcs?.length && !storylinesData.scenes?.length" class="text-slate-500 py-6 text-center">暂无脉络数据生成。</p>
        </div>
        <p v-else class="text-slate-500 py-6 text-center">系统将在故事线管理器中创建并建立您的故事线、人物弧光和创作场景之间的关联映射。</p>
      </div>

      <!-- Tab Content: Conversations -->
      <div v-if="activeTab === 'conversations'" class="space-y-4">
        <div class="flex justify-between items-center mb-2">
          <h2 class="font-bold text-slate-200 text-base">AI 创作对话</h2>
          <button @click="startConversation" class="btn-primary text-xs py-1.5 px-3 flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            <span>开启讨论</span>
          </button>
        </div>
        <div v-if="conversations.length === 0" class="card p-8 text-center text-slate-500 bg-slate-900/40">
          暂无创作对话，点击右上角开启与 AI 深度讨论剧情或人物走向吧。
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <router-link v-for="conv in conversations" :key="conv.id"
            :to="`/novels/${novelId}/conversations/${conv.id}`"
            class="card p-4 block bg-slate-900/30 hover:bg-slate-900/60 border border-slate-800/80 hover:border-purple-500/20 hover:shadow-lg transition-all duration-300"
          >
            <div class="flex justify-between items-center gap-3">
              <span class="font-bold text-slate-200 text-sm truncate pr-2">{{ conv.topic }}</span>
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
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VolumeList from '../components/VolumeList.vue'
import ChapterRangeDialog from '../components/ChapterRangeDialog.vue'

const route = useRoute()
const router = useRouter()
const novelId = route.params.id

const novel = ref(null)
const world = ref(null)
const characters = ref([])
const chapters = ref([])
const volumes = ref([])
const conversations = ref([])
const powerSystems = ref([])
const storylinesData = ref(null)
const outlineTree = ref(null)
const loading = ref(true)
const generating = ref(false)
const fullGenerating = ref(false)
const activeTab = ref('overview')
const showRangeDialog = ref(false)

const editingOverview = ref(false)
const savingOverview = ref(false)
const overviewSaved = ref(false)
const overviewError = ref('')
const overviewForm = ref({ title: '', idea: '' })

function statusClass(s) {
  return { draft: 'pending', generating: 'running', completed: 'completed', failed: 'failed' }[s] || 'pending'
}

function startEditOverview() {
  overviewForm.value = { title: novel.value.title || '', idea: novel.value.idea || '' }
  editingOverview.value = true
  overviewSaved.value = false
  overviewError.value = ''
}

function cancelEditOverview() {
  editingOverview.value = false
}

async function saveOverview() {
  savingOverview.value = true
  overviewError.value = ''
  try {
    const res = await fetch(`/api/v1/projects/${novelId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: overviewForm.value.title, idea: overviewForm.value.idea }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      overviewError.value = data.detail || '保存失败'
      return
    }
    novel.value = { ...novel.value, ...overviewForm.value }
    editingOverview.value = false
    overviewSaved.value = true
    setTimeout(() => { overviewSaved.value = false }, 2000)
  } finally {
    savingOverview.value = false
  }
}

const unassignedChapters = computed(() =>
  chapters.value.filter(c => !c.volume_number)
)

const tabs = [
  { id: 'overview', label: '概览' },
  { id: 'outlines', label: '大纲' },
  { id: 'world', label: '世界观' },
  { id: 'power-systems', label: '力量体系' },
  { id: 'characters', label: '人物' },
  { id: 'chapters', label: '章节' },
  { id: 'storylines', label: '故事线' },
  { id: 'conversations', label: '创作对话' },
]

const statusLabel = computed(() => {
  const map = { draft: '草稿', generating: '生成中', completed: '已完成', failed: '失败' }
  return map[novel.value?.status] || novel.value?.status
})

async function fetchAll() {
  loading.value = true
  try {
    const [nRes, wRes, cRes, chRes, convRes, volRes, psRes, slRes, olRes] = await Promise.all([
      fetch(`/api/v1/projects/${novelId}`),
      fetch(`/api/v1/projects/${novelId}/world`),
      fetch(`/api/v1/projects/${novelId}/characters`),
      fetch(`/api/v1/projects/${novelId}/chapters`),
      fetch(`/api/v1/projects/${novelId}/conversations`),
      fetch(`/api/v1/projects/${novelId}/volumes`),
      fetch(`/api/v1/projects/${novelId}/power-systems`),
      fetch(`/api/v1/projects/${novelId}/relations`),
      fetch(`/api/v1/projects/${novelId}/outlines`),
    ])
    if (nRes.ok) novel.value = await nRes.json()
    if (wRes.ok) world.value = await wRes.json()
    if (cRes.ok) characters.value = await cRes.json()
    if (chRes.ok) chapters.value = await chRes.json()
    if (convRes.ok) conversations.value = await convRes.json()
    if (volRes.ok) volumes.value = await volRes.json()
    if (psRes.ok) powerSystems.value = await psRes.json()
    if (slRes.ok) storylinesData.value = await slRes.json()
    if (olRes.ok) outlineTree.value = await olRes.json()
  } finally {
    loading.value = false
  }
}

async function generate() {
  generating.value = true
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/generate`, { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      router.push(`/task/${data.task_id}`)
    }
  } finally {
    generating.value = false
  }
}

async function fullGenerate() {
  fullGenerating.value = true
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/generate-full`, { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      router.push(`/task/${data.task_id}`)
    }
  } finally {
    fullGenerating.value = false
  }
}

async function startConversation() {
  const topic = prompt('对话主题（如：讨论主角设定、情节走向）')
  if (!topic) return
  const res = await fetch(`/api/v1/projects/${novelId}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  })
  if (res.ok) {
    const data = await res.json()
    router.push(`/novels/${novelId}/conversations/${data.id}`)
  }
}

async function handleGenerateVolume(volumeNumber) {
  const res = await fetch(`/api/v1/projects/${novelId}/generate-volume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ volume_number: volumeNumber }),
  })
  if (res.ok) {
    const data = await res.json()
    router.push(`/task/${data.task_id}`)
  }
}

async function handleGenerateChapters({ chapter_start, chapter_end }) {
  showRangeDialog.value = false
  const res = await fetch(`/api/v1/projects/${novelId}/generate-chapters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chapter_start, chapter_end }),
  })
  if (res.ok) {
    const data = await res.json()
    router.push(`/task/${data.task_id}`)
  }
}

const deleteTargetUnassigned = ref(null)

function handleDeleteChapter(chapterNumber) {
  chapters.value = chapters.value.filter(c => c.chapter_number !== chapterNumber)
}

function confirmDeleteUnassigned(ch) {
  deleteTargetUnassigned.value = ch
}

async function doDeleteUnassigned() {
  const ch = deleteTargetUnassigned.value
  if (!ch) return
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/chapters/${ch.chapter_number}`, { method: 'DELETE' })
    if (res.ok) {
      chapters.value = chapters.value.filter(c => c.chapter_number !== ch.chapter_number)
    }
  } finally {
    deleteTargetUnassigned.value = null
  }
}

onMounted(fetchAll)
</script>
