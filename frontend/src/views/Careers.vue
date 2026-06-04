<template>
  <div class="min-h-screen bg-neutral-50 py-10 px-4 sm:px-6 lg:px-8">
    <div class="max-w-7xl mx-auto space-y-8">
      <!-- 头部：标题与面包屑 -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div class="flex items-center gap-2 mb-1.5">
            <router-link :to="`/novels/${novelId}`" class="text-xs text-accent-600 hover:text-accent-700 font-semibold flex items-center gap-1 group">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
              返回作品详情
            </router-link>
          </div>
          <h1 class="text-2xl font-extrabold text-neutral-900 tracking-tight flex items-center gap-2">
            <span>职业体系管理</span>
            <span v-if="novel" class="text-sm font-medium text-neutral-500 bg-neutral-200/60 px-2 py-0.5 rounded-md border border-neutral-300">《{{ novel.title }}》</span>
          </h1>
          <p class="text-xs text-neutral-500 mt-1">为小说架构职业等级阶梯，分配角色当前修炼阶段，打造严密的战力或成长体系。</p>
        </div>

        <!-- 顶部操作按钮 -->
        <div class="flex items-center gap-3">
          <button
            @click="openAiGenerateModal"
            class="btn-secondary text-xs flex items-center gap-1.5 bg-gradient-to-r hover:from-accent-50 hover:to-indigo-50 border-accent-200/80"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-accent-600 animate-pulse">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.091-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.091L9 5.25l.813 2.846a4.5 4.5 0 003.091 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.091z" />
            </svg>
            <span>AI 生成职业</span>
          </button>
          <button
            @click="openAddCareerModal"
            class="btn-primary text-xs flex items-center gap-1.5"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            <span>手动添加职业</span>
          </button>
        </div>
      </div>

      <!-- 主内容区：左（列表）右（详情）分栏 -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        <!-- 左侧：职业卡片列表 (4/12) -->
        <div class="lg:col-span-5 space-y-4">
          <div class="glass-container rounded-2xl border border-white/20 p-5 shadow-xl">
            <h2 class="text-sm font-bold text-neutral-800 mb-4 flex items-center justify-between">
              <span>已设职业库</span>
              <span class="text-xs font-mono font-bold bg-neutral-200/50 text-neutral-600 px-2 py-0.5 rounded-full">{{ careers.length }} 个</span>
            </h2>

            <div v-if="loading" class="flex flex-col items-center justify-center py-16 space-y-3">
              <div class="w-8 h-8 border-3 border-accent-600 border-t-transparent rounded-full animate-spin"></div>
              <p class="text-xs text-neutral-400 font-medium">数据加载中...</p>
            </div>

            <div v-else-if="careers.length === 0" class="text-center py-16 px-4 border border-dashed border-neutral-300/60 rounded-xl bg-white/30 backdrop-blur-sm">
              <p class="text-xs text-neutral-400 mb-3">暂无职业体系设定</p>
              <div class="flex justify-center gap-2">
                <button @click="openAiGenerateModal" class="btn-secondary text-[11px] py-1 px-2.5">AI 快速生成</button>
                <button @click="openAddCareerModal" class="btn-primary text-[11px] py-1 px-2.5">手动添加</button>
              </div>
            </div>

            <div v-else class="space-y-3 max-h-[580px] overflow-y-auto pr-1">
              <div
                v-for="career in careers"
                :key="career.id"
                @click="selectCareer(career)"
                class="glass-panel text-left p-4 rounded-xl border transition-all duration-300 cursor-pointer flex flex-col justify-between"
                :class="[
                  selectedCareer && selectedCareer.id === career.id
                    ? 'border-accent-500 bg-accent-50/20 shadow-md ring-1 ring-accent-500/20'
                    : 'border-neutral-200/60 bg-white/50 hover:bg-white/80 hover:border-neutral-300'
                ]"
              >
                <div>
                  <div class="flex items-center justify-between mb-2">
                    <h3 class="font-bold text-sm text-neutral-800 flex items-center gap-2">
                      <span class="w-1.5 h-1.5 rounded-full" :class="getCategoryColor(career.category)"></span>
                      <span>{{ career.name }}</span>
                    </h3>
                    <span class="text-[10px] font-semibold border px-1.5 py-0.5 rounded" :class="getCategoryBadgeClass(career.category)">
                      {{ career.category }}
                    </span>
                  </div>
                  <p class="text-xs text-neutral-500 leading-relaxed line-clamp-2 mb-3">
                    {{ career.description || '暂无详细背景描述。' }}
                  </p>
                </div>
                <div class="flex items-center justify-between text-[10px] text-neutral-400 font-bold border-t border-neutral-100/80 pt-2">
                  <span>包含阶段数：{{ career.stages?.length || 10 }} 阶</span>
                  <div class="flex items-center gap-2">
                    <button @click.stop="openEditCareerModal(career)" class="text-accent-600 hover:text-accent-700">编辑</button>
                    <button @click.stop="deleteCareer(career.id)" class="text-red-500 hover:text-red-600">删除</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧：职业详情与 vertical timeline (7/12) -->
        <div class="lg:col-span-7 space-y-4">
          <div class="glass-container rounded-2xl border border-white/20 p-6 shadow-xl min-h-[400px] flex flex-col">
            <template v-if="selectedCareer">
              <!-- 职业基本情况 -->
              <div class="border-b border-neutral-200/80 pb-4 mb-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-left">
                <div>
                  <div class="flex items-center gap-2 mb-1">
                    <h2 class="text-lg font-bold text-neutral-800">{{ selectedCareer.name }}</h2>
                    <span class="text-xs font-semibold px-2 py-0.5 rounded border" :class="getCategoryBadgeClass(selectedCareer.category)">
                      {{ selectedCareer.category }}
                    </span>
                  </div>
                  <p class="text-xs text-neutral-500 leading-relaxed max-w-xl">
                    {{ selectedCareer.description }}
                  </p>
                </div>
                <div class="shrink-0 flex items-center gap-2">
                  <button @click="openEditCareerModal(selectedCareer)" class="btn-secondary text-xs py-1 px-3">编辑</button>
                  <button @click="deleteCareer(selectedCareer.id)" class="btn-secondary text-xs py-1 px-3 text-red-500 hover:text-red-600 hover:border-red-200">删除</button>
                </div>
              </div>

              <!-- 职业阶段 Timeline -->
              <div class="flex-1">
                <h3 class="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-4 text-left">修习境界阶段天梯</h3>
                <!-- Timeline 组件 -->
                <CareerStageTimeline
                  :stages="selectedCareer.stages"
                  :current-stage-index="selectedCareerPreviewStage"
                  @select-stage="onTimelineSelect"
                />
              </div>
            </template>

            <div v-else class="flex-1 flex flex-col items-center justify-center py-24 text-center text-neutral-400">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-12 h-12 text-neutral-300 mb-3 animate-bounce">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801-1.206a2.25 2.25 0 00-3.302 0m3.302 0a2.245 2.245 0 001.324-.079m-3.302 0a2.245 2.245 0 01-1.324-.079m0 0a2.249 2.249 0 00-2.247 2.247c0 1.135.845 2.098 1.976 2.192a48.474 48.474 0 001.123.08M12 3v1.5m0 22.5V21m-9-9h1.5m16.5 0H18" />
              </svg>
              <p class="text-sm font-medium">请从左侧职业库中选择一个职业，或者通过 AI/手动 方式添加一个新职业来查看修习天梯。</p>
            </div>
          </div>
        </div>

      </div>

      <!-- 底部：角色职业分配区 -->
      <div class="glass-container rounded-2xl border border-white/20 p-6 shadow-xl text-left">
        <h2 class="text-sm font-bold text-neutral-800 mb-4 flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-accent-600">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
          <span>角色境界修习分配</span>
        </h2>

        <div v-if="characters.length === 0" class="text-center py-10 px-4 border border-dashed border-neutral-300 rounded-xl bg-white/40">
          <p class="text-xs text-neutral-400 mb-2">当前作品库中暂无人物角色档案</p>
          <router-link :to="`/novels/${novelId}/characters`" class="text-xs text-accent-600 hover:text-accent-700 font-bold">立即去管理人物档案添加角色 &rarr;</router-link>
        </div>

        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-neutral-200">
            <thead>
              <tr class="text-xs font-bold text-neutral-400 uppercase tracking-wider text-left">
                <th class="py-3 px-4">角色姓名</th>
                <th class="py-3 px-4">定位身份</th>
                <th class="py-3 px-4">主要修习职业</th>
                <th class="py-3 px-4">当前修炼进度</th>
                <th class="py-3 px-4 text-right">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-neutral-100 text-xs text-neutral-600">
              <tr v-for="char in characters" :key="char.id" class="hover:bg-white/40 transition-colors">
                <!-- 姓名 -->
                <td class="py-3.5 px-4 font-bold text-neutral-800">{{ char.name }}</td>
                <!-- 角色定位 -->
                <td class="py-3.5 px-4">
                  <span class="bg-neutral-100/80 text-neutral-700 px-2 py-0.5 rounded border border-neutral-200 font-medium">
                    {{ char.role || '未定' }}
                  </span>
                </td>
                <!-- 职业分配 -->
                <td class="py-3.5 px-4">
                  <select
                    v-model="assignments[char.id].careerId"
                    @change="onAssignmentChange(char.id)"
                    class="bg-white/80 border border-neutral-200 rounded-lg px-2.5 py-1 text-xs focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
                  >
                    <option value="">暂无职业</option>
                    <option v-for="career in careers" :key="career.id" :value="career.id">
                      {{ career.name }} ({{ career.category }})
                    </option>
                  </select>
                </td>
                <!-- 阶段分配 -->
                <td class="py-3.5 px-4">
                  <select
                    v-model="assignments[char.id].stageIndex"
                    @change="saveAssignment(char.id)"
                    :disabled="!assignments[char.id].careerId"
                    class="bg-white/80 border border-neutral-200 rounded-lg px-2.5 py-1 text-xs focus:ring-1 focus:ring-accent-500 focus:border-accent-500 disabled:bg-neutral-100 disabled:text-neutral-400"
                  >
                    <option v-for="(stage, idx) in getCareerStages(assignments[char.id].careerId)" :key="idx" :value="idx">
                      Lvl {{ idx + 1 }}: {{ stage.name }}
                    </option>
                  </select>
                </td>
                <!-- 自动保存状态 -->
                <td class="py-3.5 px-4 text-right">
                  <span v-if="savingStates[char.id]" class="text-[10px] text-accent-600 font-semibold flex items-center justify-end gap-1">
                    <svg class="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>保存中...</span>
                  </span>
                  <span v-else-if="savingStates[char.id] === false" class="text-[10px] text-emerald-600 font-bold flex items-center justify-end gap-1 animate-pulse">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor" class="w-3.5 h-3.5">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                    <span>已同步</span>
                  </span>
                  <span v-else class="text-[10px] text-neutral-400">自动同步</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- AI 自动生成配置 Modal -->
    <div v-if="showAiModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/40 backdrop-blur-sm">
      <div class="glass-container max-w-md w-full rounded-2xl border border-white/20 p-6 shadow-2xl space-y-4">
        <h3 class="text-base font-bold text-neutral-800 flex items-center gap-2 text-left">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-5 h-5 text-accent-600">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.091-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.091L9 5.25l.813 2.846a4.5 4.5 0 003.091 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.091z" />
          </svg>
          <span>AI 职业天梯架构编织</span>
        </h3>
        <p class="text-xs text-neutral-500 leading-relaxed text-left">
          AI 将结合作品的题材设定、能量守恒定律和冲突架构，为您定制出一套逻辑严密、兼具想象力的 10 重境界职业体系阶梯。
        </p>

        <div class="space-y-3 text-left">
          <div>
            <label class="block text-xs font-semibold text-neutral-500 mb-1">选择职业倾向体系</label>
            <select v-model="aiCareerConfig.category" class="input text-xs w-full">
              <option value="修仙">修仙天道体系</option>
              <option value="武道">高武炼体体系</option>
              <option value="魔法">元素奥术体系</option>
              <option value="异能">超凡心智觉醒</option>
              <option value="科技">机械物理进化</option>
              <option value="其它">神秘学诡异演变</option>
            </select>
          </div>

          <div v-if="novel">
            <label class="block text-xs font-semibold text-neutral-500 mb-1">参考小说类型</label>
            <div class="bg-neutral-100 border rounded-lg p-2.5 text-xs text-neutral-600 font-medium">
              类型：{{ novel.novel_type }} | 目标字数：{{ (novel.target_words / 10000).toFixed(0) }}万字
            </div>
          </div>
        </div>

        <div class="flex gap-3 pt-2">
          <button @click="generateCareerByAi" class="btn-primary flex-1 text-xs" :disabled="aiGenerating">
            {{ aiGenerating ? '天道感悟中...' : '开始编织' }}
          </button>
          <button @click="showAiModal = false" class="btn-secondary flex-1 text-xs" :disabled="aiGenerating">
            取消
          </button>
        </div>

        <!-- 动效加载遮罩 -->
        <div v-if="aiGenerating" class="absolute inset-0 bg-white/85 backdrop-blur-md rounded-2xl flex flex-col items-center justify-center space-y-4 p-6 z-10">
          <div class="w-12 h-12 border-4 border-accent-600 border-t-transparent rounded-full animate-spin"></div>
          <div class="text-center space-y-1.5">
            <p class="text-sm font-bold text-neutral-800">{{ aiLoadingTitle }}</p>
            <p class="text-[10px] text-neutral-400 font-medium animate-pulse">正在利用 Gemini 大模型解析灵感规则...</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 手动添加 / 编辑职业 Modal -->
    <div v-if="showEditModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/40 backdrop-blur-sm overflow-y-auto">
      <div class="glass-container max-w-2xl w-full rounded-2xl border border-white/20 p-6 shadow-2xl my-8 space-y-5 text-left relative">
        <h3 class="text-base font-bold text-neutral-800 flex items-center justify-between border-b pb-3">
          <span>{{ isEditMode ? '编辑职业体系' : '新建职业体系' }}</span>
          <button @click="showEditModal = false" class="text-neutral-400 hover:text-neutral-600">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </h3>

        <!-- 基本字段 -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="sm:col-span-1">
            <label class="block text-xs font-semibold text-neutral-500 mb-1">职业名称</label>
            <input v-model="editCareerForm.name" class="input text-xs w-full" placeholder="例如：玄剑仙、脑域算力士" required />
          </div>
          <div class="sm:col-span-1">
            <label class="block text-xs font-semibold text-neutral-500 mb-1">职业类别</label>
            <select v-model="editCareerForm.category" class="input text-xs w-full">
              <option value="修仙">修仙</option>
              <option value="武道">武道</option>
              <option value="魔法">魔法</option>
              <option value="异能">异能</option>
              <option value="科技">科技</option>
              <option value="其它">其它</option>
            </select>
          </div>
          <div class="sm:col-span-2">
            <label class="block text-xs font-semibold text-neutral-500 mb-1">职业背景描述</label>
            <textarea v-model="editCareerForm.description" class="input text-xs w-full min-h-[60px]" placeholder="描述此职业的世界定位、修行纲领、优缺点等..."></textarea>
          </div>
        </div>

        <!-- 10个阶段等级天梯编辑器 -->
        <div class="space-y-3">
          <h4 class="text-xs font-bold text-neutral-500 border-b pb-1.5 flex items-center justify-between">
            <span>修习 10 重境界天梯设定</span>
            <span class="text-[10px] text-accent-600 font-semibold">* 每一重都需要定义名称和突破瓶颈修行</span>
          </h4>
          <div class="space-y-2 max-h-[250px] overflow-y-auto pr-1">
            <div
              v-for="(stage, idx) in editCareerForm.stages"
              :key="idx"
              class="p-3 bg-neutral-100/50 border border-neutral-200 rounded-xl space-y-2.5"
            >
              <div class="flex items-center gap-3">
                <span class="text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-neutral-200 text-neutral-600">
                  Lvl {{ idx + 1 }}
                </span>
                <input
                  v-model="stage.name"
                  class="bg-white border border-neutral-200 rounded-lg px-2.5 py-1 text-xs flex-1 focus:ring-1 focus:ring-accent-500 focus:outline-none"
                  placeholder="境界名称（如：气感、练气、淬体）"
                  required
                />
              </div>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <input
                  v-model="stage.description"
                  class="bg-white border border-neutral-200 rounded-lg px-2.5 py-1 text-xs focus:ring-1 focus:ring-accent-500 focus:outline-none"
                  placeholder="修炼描述：如经脉灵气贯通..."
                />
                <input
                  v-model="stage.breakthrough"
                  class="bg-white border border-neutral-200 rounded-lg px-2.5 py-1 text-xs focus:ring-1 focus:ring-accent-500 focus:outline-none"
                  placeholder="突破条件：如吞服筑基丹、打破凡胎障..."
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 保存按钮 -->
        <div class="flex gap-3 justify-end pt-3 border-t">
          <button @click="saveCareer" class="btn-primary text-xs px-6" :disabled="savingCareer">
            {{ savingCareer ? '保存中...' : '确定保存' }}
          </button>
          <button @click="showEditModal = false" class="btn-secondary text-xs px-6" :disabled="savingCareer">
            取消
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import CareerStageTimeline from '../components/CareerStageTimeline.vue'

const route = useRoute()
const novelId = route.params.id

// 数据模型
const novel = ref(null)
const characters = ref([])
const careers = ref([])
const assignments = ref({}) // 结构：{ characterId: { careerId, stageIndex } }

// 交互状态
const loading = ref(true)
const selectedCareer = ref(null)
const selectedCareerPreviewStage = ref(0)
const savingStates = ref({}) // 对应各角色的同步状态

// AI生成Modal
const showAiModal = ref(false)
const aiGenerating = ref(false)
const aiLoadingTitle = ref('灵气交感中...')
const aiCareerConfig = ref({ category: '修仙' })

// 手动添加/编辑Modal
const showEditModal = ref(false)
const isEditMode = ref(false)
const savingCareer = ref(false)
const editCareerForm = ref({
  id: '',
  name: '',
  category: '修仙',
  description: '',
  stages: []
})

// 默认的 10 重天梯基础格式
function createEmptyStages() {
  const arr = []
  for (let i = 1; i <= 10; i++) {
    arr.push({ level: i, name: `第 ${i} 阶境`, description: '', breakthrough: '' })
  }
  return arr
}

// 门派特色颜色
function getCategoryColor(cat) {
  return {
    '修仙': 'bg-emerald-500',
    '武道': 'bg-amber-500',
    '魔法': 'bg-purple-500',
    '异能': 'bg-blue-500',
    '科技': 'bg-cyan-500',
    '其它': 'bg-neutral-500'
  }[cat] || 'bg-neutral-500'
}

function getCategoryBadgeClass(cat) {
  return {
    '修仙': 'bg-emerald-50 text-emerald-700 border-emerald-100',
    '武道': 'bg-amber-50 text-amber-700 border-amber-100',
    '魔法': 'bg-purple-50 text-purple-700 border-purple-100',
    '异能': 'bg-blue-50 text-blue-700 border-blue-100',
    '科技': 'bg-cyan-50 text-cyan-700 border-cyan-100',
    '其它': 'bg-neutral-50 text-neutral-600 border-neutral-200'
  }[cat] || 'bg-neutral-50 text-neutral-600'
}

// 获取某一职业的阶段列表，用来给下拉框遍历
function getCareerStages(careerId) {
  const found = careers.value.find(c => c.id === careerId)
  if (found && found.stages) return found.stages
  return createEmptyStages()
}

// 时间线点击回调
function onTimelineSelect({ index }) {
  selectedCareerPreviewStage.value = index
}

// 数据加载与初始化
async function load() {
  loading.value = true
  try {
    // 1. 加载小说基本设定
    const novelRes = await fetch(`/api/v1/projects/${novelId}`)
    if (novelRes.ok) novel.value = await novelRes.json()

    // 2. 加载小说角色档案
    const charRes = await fetch(`/api/v1/projects/${novelId}/characters`)
    if (charRes.ok) {
      characters.value = await charRes.json()
    }

    // 3. 加载职业体系数据
    await loadCareers()

    // 4. 加载角色职业分配数据
    await loadAssignments()

  } catch (err) {
    console.error('Failed to load data', err)
  } finally {
    loading.value = false
  }
}

// 获取职业列表 (API 优先，LocalStorage 兜底)
async function loadCareers() {
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/careers`)
    if (res.ok) {
      careers.value = await res.json()
      if (careers.value.length > 0 && !selectedCareer.value) {
        selectedCareer.value = careers.value[0]
      }
      return
    }
  } catch (e) {
    console.warn('API error, falling back to LocalStorage', e)
  }
  
  // LocalStorage 兜底
  const localData = localStorage.getItem(`careers_${novelId}`)
  if (localData) {
    careers.value = JSON.parse(localData)
  } else {
    // 默认内置的修仙职业，以免界面光秃秃的
    const defaultCareers = [
      {
        id: 'def-xiuxian',
        name: '九天御雷真仙',
        category: '修仙',
        description: '引动九天神仙雷劫，淬炼金身，以剑道御雷法则纵横宇宙的无上真仙体系。',
        stages: [
          { level: 1, name: '感气引雷', description: '吞吐灵气，首次在丹田内凝结微弱电弧。', breakthrough: '在暴雨雷鸣之夜入定突破。' },
          { level: 2, name: '凝雷入脉', description: '雷霆游走奇经八脉，将凡俗之身转为半灵体。', breakthrough: '炼化一颗一阶辟雷丹。' },
          { level: 3, name: '筑基雷池', description: '在丹田内铸就一方雷水法池，灵力彻底化为雷元。', breakthrough: '心境圆满，灵气蓄满。' },
          { level: 4, name: '结丹九重', description: '金丹生电芒，每一次呼吸都伴随着震耳雷音。', breakthrough: '渡过三九天劫，金丹浑圆。' },
          { level: 5, name: '碎丹元婴', description: '金丹破碎，化为一个雷霆本源的紫电元婴。', breakthrough: '六九雷劫洗礼，破茧成婴。' },
          { level: 6, name: '法相化神', description: '元婴化为百丈高的雷帝法相，代天行罚。', breakthrough: '天道感悟雷霆秩序。' },
          { level: 7, name: '天雷合体', description: '肉身与雷帝法相融为一体，本身即是神罚雷霆。', breakthrough: '天人合一，融雷入骨。' },
          { level: 8, name: '大乘雷域', description: '周身百里演化为永恒雷域，诸邪辟易。', breakthrough: '元神突破星域枷锁。' },
          { level: 9, name: '渡劫登天', description: '迎接天地最终的大破灭九重神雷劫。', breakthrough: '在渡劫大阵中硬抗灭世劫雷。' },
          { level: 10, name: '御雷真仙', description: '飞升仙界，成为掌控诸天惩戒法纪的御雷剑仙。', breakthrough: '飞升仙门，法则圆满。' }
        ]
      }
    ]
    careers.value = defaultCareers
    localStorage.setItem(`careers_${novelId}`, JSON.stringify(defaultCareers))
  }

  if (careers.value.length > 0 && !selectedCareer.value) {
    selectedCareer.value = careers.value[0]
  }
}

// 获取分配数据 (API 优先，LocalStorage 兜底)
async function loadAssignments() {
  const mapping = {}
  
  // 先把所有角色在 assignments 注册好
  characters.value.forEach(char => {
    mapping[char.id] = { careerId: '', stageIndex: 0 }
  })

  try {
    const res = await fetch(`/api/v1/projects/${novelId}/characters/careers`)
    if (res.ok) {
      const data = await res.json()
      // data 结构假定为数组: [{ character_id, career_id, stage_index }]
      data.forEach(item => {
        if (mapping[item.character_id]) {
          mapping[item.character_id] = {
            careerId: item.career_id || '',
            stageIndex: item.stage_index || 0
          }
        }
      })
      assignments.value = mapping
      return
    }
  } catch (e) {
    console.warn('API error on assignments, falling back to LocalStorage', e)
  }

  // LocalStorage 兜底
  const localData = localStorage.getItem(`char_careers_${novelId}`)
  if (localData) {
    const data = JSON.parse(localData)
    Object.keys(data).forEach(id => {
      if (mapping[id]) {
        mapping[id] = data[id]
      }
    })
  }

  assignments.value = mapping
}

// 选中职业
function selectCareer(career) {
  selectedCareer.value = career
  selectedCareerPreviewStage.value = 0
}

// 角色选择了新职业
function onAssignmentChange(charId) {
  const currentAss = assignments.value[charId]
  if (!currentAss.careerId) {
    currentAss.stageIndex = 0
  }
  saveAssignment(charId)
}

// 保存分配关系
async function saveAssignment(charId) {
  savingStates.value[charId] = true
  const record = assignments.value[charId]
  
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/characters/careers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        character_id: charId,
        career_id: record.careerId,
        stage_index: record.stageIndex
      })
    })
    if (res.ok) {
      savingStates.value[charId] = false
      setTimeout(() => { delete savingStates.value[charId] }, 1500)
      return
    }
  } catch (e) {
    console.warn('API sync failed, updating local storage only', e)
  }

  // 更新 localstorage 兜底
  localStorage.setItem(`char_careers_${novelId}`, JSON.stringify(assignments.value))
  savingStates.value[charId] = false
  setTimeout(() => { delete savingStates.value[charId] }, 1500)
}

// AI生成弹框
function openAiGenerateModal() {
  if (novel.value) {
    // 结合小说类别匹配默认倾向
    const type = novel.value.novel_type || ''
    if (type.includes('仙') || type.includes('玄')) aiCareerConfig.value.category = '修仙'
    else if (type.includes('科') || type.includes('武')) aiCareerConfig.value.category = '科技'
    else if (type.includes('魔') || type.includes('奇')) aiCareerConfig.value.category = '魔法'
    else aiCareerConfig.value.category = '修仙'
  }
  showAiModal.value = true
  aiGenerating.value = false
}

// AI 职业模拟生成逻辑
async function generateCareerByAi() {
  aiGenerating.value = true
  
  // 炫酷动效切换标题
  const titles = ['感悟天道意志...', '推演元素能量守恒...', '划定凡俗神灵界限...', '构建突破死生瓶颈...']
  let titleIndex = 0
  const interval = setInterval(() => {
    aiLoadingTitle.value = titles[titleIndex % titles.length]
    titleIndex++
  }, 500)

  // 1. 模拟网络生成延时
  await new Promise(resolve => setTimeout(resolve, 2200))
  clearInterval(interval)

  // 2. 根据选定的类别，生成一个极为优秀和高度契合的 10 阶段职业
  const category = aiCareerConfig.value.category
  let newCareer = {}

  if (category === '修仙') {
    newCareer = {
      id: 'ai-' + Date.now(),
      name: '大罗九天太乙仙',
      category: '修仙',
      description: '证道混元大罗，在灵气中参悟造化生死、虚空万界因果规则的至上修真天梯。',
      stages: [
        { level: 1, name: '凡砂蜕骨', description: '褪去一身凡俗骨血尘垢，吸纳天地第一缕玄清灵气。', breakthrough: '在清晨紫气东来之时盘坐洗髓。' },
        { level: 2, name: '九宫灵旋', description: '在腹中气海开拓出九个小灵旋，源源不断吞吐大荒气息。', breakthrough: '破入灵髓池浸泡半日。' },
        { level: 3, name: '玄胎筑基', description: '灵气化液，汇入仙脉，筑造出支撑万载寿元的琉璃玄台。', breakthrough: '服下一颗极品筑基丹并心境通透。' },
        { level: 4, name: '紫金结丹', description: '灵台雷霆闪烁，孕育出一枚照耀百里的紫金不灭金丹。', breakthrough: '在无上聚灵大阵中经受天劫余威。' },
        { level: 5, name: '真命元神', description: '粉碎金丹，温养出不堕虚空的元神，精神力可瞬息扫过山河。', breakthrough: '元神突破魂海束缚，历经地心罡风淬洗。' },
        { level: 6, name: '万法化身', description: '元神化为九种极道仙光，拥有断肢重生、移山填海的莫大神通。', breakthrough: '炼化一件本命灵虚法宝。' },
        { level: 7, name: '诸界洞天', description: '神识在体内开辟出微型乾坤，可凭空储物或演化万物灵力。', breakthrough: '融合一片残存的破碎仙界洞天。' },
        { level: 8, name: '无极太乘', description: '参悟天地自然造化无为，举手投足自带法则压迫，震慑四野。', breakthrough: '枯坐百年了却红尘宿愿。' },
        { level: 9, name: '乾坤道劫', description: '斩却三尸，直面天地法则的大破灭风水火土混元四九神雷。', breakthrough: '依靠自身坚毅不灭的意志硬抗道劫。' },
        { level: 10, name: '太乙金仙', description: '白日飞升，跳出三界外，不在五行中，证得太乙金仙道果。', breakthrough: '登天路，斩断因果锁链。' }
      ]
    }
  } else if (category === '武道') {
    newCareer = {
      id: 'ai-' + Date.now(),
      name: '万劫真龙武神',
      category: '武道',
      description: '极致磨砺肉身极限，开辟体内十万神藏，以气血真意打破粉碎真空的无双纯肉身战斗神话。',
      stages: [
        { level: 1, name: '磐石骨骼', description: '骨髓如汞，骨骼粗壮坚硬胜过百炼精钢，肉身力负千斤。', breakthrough: '浸泡九窍药水，锤炼筋骨百日。' },
        { level: 2, name: '惊雷真劲', description: '气血于肌肉之中震荡，产生如雷鸣般的刚猛爆发暗劲。', breakthrough: '击断瀑布十丈，领悟爆发暗劲。' },
        { level: 3, name: '气海沸腾', description: '气血如惊涛骇浪，开辟中丹田武道气海，真气能外放三丈。', breakthrough: '击杀一头一阶凶兽并吞食其气血精元。' },
        { level: 4, name: '琉璃金身', description: '肌肤亮如琉璃，内脏强劲，刀枪不入，寻常水火兵刃难伤分毫。', breakthrough: '经受熔火真铁砂捶打七天七夜。' },
        { level: 5, name: '五脏神光', description: '心肝脾肺肾孕育出五行神光，生机断续，心脏受创亦能短时自愈。', breakthrough: '吞噬一枚五行奇珍天心草。' },
        { level: 6, name: '通达造化', description: '武道感悟融入气血，举手投足皆合乎武道至理，真气生生不息。', breakthrough: '与同阶武者鏖战三天三夜，突破心障。' },
        { level: 7, name: '碎空法体', description: '举手投足间空气开裂，纯肉身速度超越音速，产生震荡虚空的裂音。', breakthrough: '在重力极高的地磁深渊修行七日。' },
        { level: 8, name: '滴血重生', description: '生命元能浓郁到每一滴鲜血中都蕴含着极强意志，断手一息可续。', breakthrough: '涅槃熔炉之火淬炼，死里逃生。' },
        { level: 9, name: '粉碎真空', description: '打破天地屏障的绝对唯物压制，纯物理重拳可以直接砸裂虚空。', breakthrough: '挥出十万八千重拳，打破法则重压。' },
        { level: 10, name: '真龙武神', description: '肉身跨越纪元而永生，凝练不朽真龙神格，宇宙崩塌唯肉体长存。', breakthrough: '将体内十万八千神藏与宇宙星空连通。' }
      ]
    }
  } else if (category === '魔法') {
    newCareer = {
      id: 'ai-' + Date.now(),
      name: '奥术编织主宰',
      category: '魔法',
      description: '掌握构成多元宇宙的秩序、混沌、水、火、风、土等纯元素魔力符号，以真理编织奥术世界的法则君主。',
      stages: [
        { level: 1, name: '冥想学徒', description: '能在灵魂深处观想魔力光点，并勉强画出单字魔力符文。', breakthrough: '成功点亮第一枚灵识魔力符咒。' },
        { level: 2, name: '低阶法士', description: '可凝聚出火球、水弹等基础元素具象，精神力足支持数轮施法。', breakthrough: '独自完成一次实战施法历练。' },
        { level: 3, name: '魔导专精', description: '在某一元素或奥术领域极其专精，能够默发三环以下所有法术。', breakthrough: '通过法师工会考核，成功精炼魔力。' },
        { level: 4, name: '魔力泉涌', description: '法术海无间断爆发，可以在精神海形成永动回蓝泉眼，极大提高爆发。', breakthrough: '融合一颗中阶魔核并建立体内回路。' },
        { level: 5, name: '天灾大巫', description: '能够吟唱大范围灾厄级法术，如陨石天降或暴风雪降临。', breakthrough: '抗衡并驯服一只高阶魔能元素兽。' },
        { level: 6, name: '传奇贤者', description: '洞悉元素本质，甚至能利用魔力在自身周围构建传奇豁免结界。', breakthrough: '在古老真理遗迹感悟魔力之源。' },
        { level: 7, name: '空间旅者', description: '精通时空编织，能够随心所欲跨越百里闪烁，甚至开启界域之门。', breakthrough: '掌握星轨逆转方程式并稳定穿梭空间。' },
        { level: 8, name: '法则禁咒尊', description: '能施展毁灭城池与改变气候格局的灭世禁咒，引动星空魔法狂潮。', breakthrough: '炼制一把属于自己的禁咒级法则权杖。' },
        { level: 9, name: '神格点燃', description: '将奥术本源铭刻在灵魂深处，神识在奥术星河中获得属于自己的坐标。', breakthrough: '汇聚庞大信仰之力，点燃神火。' },
        { level: 10, name: '奥术主宰', description: '意志即是魔法界的最高铁律，一言即出元素重组，真理彻底掌握在手。', breakthrough: '将魔网节点彻底接入自身意志中。' }
      ]
    }
  } else {
    // 默认提供通用的神秘学或科技体系
    newCareer = {
      id: 'ai-' + Date.now(),
      name: '序列超脑掌控者',
      category: category,
      description: '开发脑域至 100% 极限，将肉身及意志尽皆降维信息流并掌握机械科技绝对真理的先驱者。',
      stages: [
        { level: 1, name: '微光接口', description: '在后脑成功植入神经芯片，可通过意念直接和普通终端实现信息互联。', breakthrough: '顺利通过信息交互压力测试。' },
        { level: 2, name: '超感神经', description: '五感敏锐度提升五倍，脑电波可形成实体微弱念力，能隔空移物。', breakthrough: '植入超感纳米机群。' },
        { level: 3, name: '初级超脑', description: '脑域开发达到20%，心算速度比拟普通电脑，可侵入并接管民用局域网络。', breakthrough: '融合外载算力阵列。' },
        { level: 4, name: '念力具象', description: '脑力高度实质化，可以用念力硬抗轻型机枪扫射，并在体外凝结屏障。', breakthrough: '突破四维认知屏障。' },
        { level: 5, name: '天网节点', description: '能够将自身脑波投射进全球网络，化为天网算法的一部分，操纵无人机群。', breakthrough: '成功上传1TB个人逻辑数据。' },
        { level: 6, name: '智囊先驱', description: '脑域开发45%，能够自主预判战场三秒内的任意弹道与攻势，绝对掌控。', breakthrough: '通过智库终极心智考核。' },
        { level: 7, name: '量子拟合', description: '脑域完全实现量子运算，可模拟演化分子级物质重组，凭空操控机械。', breakthrough: '吸收星核量子源。' },
        { level: 8, name: '机械先驱', description: '可以随时接管大型歼星舰或者星际防线的核心主脑，掌控千亿级机械军团。', breakthrough: '将肉身半数转为超导纳米合金。' },
        { level: 9, name: '高维幽灵', description: '摆脱碳基肉身依赖，意志融入全宇宙的量子波谱中，无处不在。', breakthrough: '主脑全面云端化，超脱生死。' },
        { level: 10, name: '神念造物主', description: '掌握科技法则最高真理，单凭宏大算法意识便可瞬息编织、捏造或湮灭星体。', breakthrough: '宇宙基本力信息逻辑公式完美融汇。' }
      ]
    }
  }

  // 3. 将新生成的职业加入数组并保存
  careers.value.push(newCareer)
  await saveCareersToStore()

  // 4. 关闭 Modal，默认选中刚刚生成的
  selectedCareer.value = newCareer
  selectedCareerPreviewStage.value = 0
  showAiModal.value = false
  aiGenerating.value = false
}

// 模拟或真实向后端提交保存职业数据
async function saveCareersToStore() {
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/careers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(careers.value)
    })
    if (res.ok) {
      return
    }
  } catch (e) {
    console.warn('API save failed, local storage fallback instead', e)
  }

  // 本地持久化
  localStorage.setItem(`careers_${novelId}`, JSON.stringify(careers.value))
}

// 打开“手动新建职业”Modal
function openAddCareerModal() {
  isEditMode.value = false
  editCareerForm.value = {
    id: '',
    name: '',
    category: '修仙',
    description: '',
    stages: createEmptyStages()
  }
  showEditModal.value = true
}

// 打开“编辑已有职业”Modal
function openEditCareerModal(career) {
  isEditMode.value = true
  
  // 深拷贝，避免在 modal 里未保存就修改了原数据
  const stagesCopy = career.stages ? JSON.parse(JSON.stringify(career.stages)) : createEmptyStages()
  // 确保一定是10个阶段
  while (stagesCopy.length < 10) {
    const nextLvl = stagesCopy.length + 1
    stagesCopy.push({ level: nextLvl, name: `第 ${nextLvl} 阶境`, description: '', breakthrough: '' })
  }

  editCareerForm.value = {
    id: career.id,
    name: career.name || '',
    category: career.category || '修仙',
    description: career.description || '',
    stages: stagesCopy
  }
  showEditModal.value = true
}

// 保存/更新职业 (手动编辑)
async function saveCareer() {
  if (!editCareerForm.value.name) {
    alert('请输入职业名称')
    return
  }

  savingCareer.value = true

  // 验证每个阶段的名称
  for (let i = 0; i < 10; i++) {
    if (!editCareerForm.value.stages[i].name) {
      editCareerForm.value.stages[i].name = `第 ${i + 1} 阶境`
    }
  }

  if (isEditMode.value) {
    // 1. 编辑模式：查找并替换原数组
    const index = careers.value.findIndex(c => c.id === editCareerForm.value.id)
    if (index !== -1) {
      careers.value[index] = {
        ...careers.value[index],
        name: editCareerForm.value.name,
        category: editCareerForm.value.category,
        description: editCareerForm.value.description,
        stages: editCareerForm.value.stages
      }
      // 如果当前正选中的是这个职业，同步更新详情显示
      if (selectedCareer.value && selectedCareer.value.id === editCareerForm.value.id) {
        selectedCareer.value = careers.value[index]
      }
    }
  } else {
    // 2. 新建模式：追加
    const newId = 'manual-' + Date.now()
    const newCareerObj = {
      id: newId,
      name: editCareerForm.value.name,
      category: editCareerForm.value.category,
      description: editCareerForm.value.description,
      stages: editCareerForm.value.stages
    }
    careers.value.push(newCareerObj)
    selectedCareer.value = newCareerObj
    selectedCareerPreviewStage.value = 0
  }

  // 3. 数据保存
  await saveCareersToStore()

  // 4. 重置状态并关闭弹框
  savingCareer.value = false
  showEditModal.value = false
}

// 删除职业
async function deleteCareer(id) {
  if (!confirm('确定要彻底删除该职业体系设定吗？此操作将导致所有已分配此职业的角色失去修炼阶梯！')) return

  try {
    const res = await fetch(`/api/v1/projects/${novelId}/careers/${id}`, {
      method: 'DELETE'
    })
    if (res.ok) {
      // 成功
    }
  } catch (e) {
    console.warn('API delete failed, performing local delete instead', e)
  }

  // 过滤职业
  careers.value = careers.value.filter(c => c.id !== id)
  
  // 如果当前选中的是被删除的职业，重新选一个
  if (selectedCareer.value && selectedCareer.value.id === id) {
    selectedCareer.value = careers.value.length > 0 ? careers.value[0] : null
    selectedCareerPreviewStage.value = 0
  }

  // 过滤分配关系：如果有人属于这个职业，将其清空
  Object.keys(assignments.value).forEach(charId => {
    if (assignments.value[charId].careerId === id) {
      assignments.value[charId].careerId = ''
      assignments.value[charId].stageIndex = 0
      saveAssignment(charId) // 自动同步
    }
  })

  // 保存数据
  await saveCareersToStore()
}

onMounted(load)
</script>

<style scoped>
.glass-container {
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.05);
}

.glass-panel {
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.35);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.glass-panel:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.04);
}

/* 隐藏滚动条 */
::-webkit-scrollbar {
  width: 4px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.08);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.15);
}
</style>
