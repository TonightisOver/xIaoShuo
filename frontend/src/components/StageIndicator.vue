<template>
  <div class="space-y-6 font-sans">
    <!-- Grid layout of stages to prevent squeezing and enhance legibility -->
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
      <div
        v-for="(stage, i) in stages"
        :key="stage.id"
        :class="[
          'rounded-xl p-3 border flex items-center gap-3 transition-all duration-300 shadow-sm',
          stageStatus(stage.id) === 'done' ? 'bg-emerald-50/70 border-emerald-100 text-emerald-800' :
          stageStatus(stage.id) === 'active' ? 'bg-purple-50/80 border-purple-200 text-purple-900 ring-2 ring-purple-500/60 ring-offset-1 font-semibold shadow-md shadow-purple-500/5' :
          stageStatus(stage.id) === 'failed' ? 'bg-rose-50 border-rose-200 text-rose-800 ring-2 ring-rose-500/60 ring-offset-1 font-semibold shadow-md' :
          'bg-neutral-50/40 border-neutral-100/60 text-neutral-400'
        ]"
      >
        <!-- Status Indicator Icon/Number -->
        <div
          :class="[
            'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 transition-all duration-300',
            stageStatus(stage.id) === 'done' ? 'bg-emerald-500 text-white' :
            stageStatus(stage.id) === 'active' ? 'bg-purple-600 text-white animate-pulse' :
            stageStatus(stage.id) === 'failed' ? 'bg-rose-600 text-white' :
            'bg-neutral-200 text-neutral-500'
          ]"
        >
          <svg v-if="stageStatus(stage.id) === 'done'" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          <svg v-else-if="stageStatus(stage.id) === 'failed'" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="3.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m0-10.03V12m0 3h.008v.008H12V15z" />
          </svg>
          <span v-else>{{ i + 1 }}</span>
        </div>
        
        <!-- Label -->
        <span class="text-xs md:text-sm font-semibold leading-tight">{{ stage.label }}</span>
      </div>
    </div>

    <!-- Active Stage Spotlight Card -->
    <div 
      :class="[
        'rounded-2xl border p-5 shadow-sm transition-all duration-300',
        status === 'failed' ? 'bg-rose-50/40 border-rose-200/80 shadow-rose-500/5' : 'bg-white/80 backdrop-blur-md border-[#e5e5ea]'
      ]"
    >
      <div class="flex items-center gap-2.5 mb-2.5">
        <span class="flex h-3 w-3 relative">
          <span 
            :class="[
              'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
              status === 'failed' ? 'bg-rose-400' : 'bg-purple-400'
            ]"
          ></span>
          <span 
            :class="[
              'relative inline-flex rounded-full h-3 w-3',
              status === 'failed' ? 'bg-rose-600' : 'bg-purple-600'
            ]"
          ></span>
        </span>
        <h3 class="text-sm font-bold text-[#1d1d1f] tracking-tight">
          {{ activeDetail.title }}
        </h3>
      </div>
      <p class="text-xs md:text-sm text-neutral-600 leading-relaxed font-sans">
        {{ activeDetail.description }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  currentStage: {
    type: String,
    default: ''
  },
  status: {
    type: String,
    default: 'running'
  }
})

const stages = [
  { id: 'idea_expansion', label: '创意拓展' },
  { id: 'world_building', label: '世界观设定' },
  { id: 'character_design', label: '人物人设设计' },
  { id: 'outline_generation', label: '剧情大纲生成' },
  { id: 'chapter_generation', label: '章节正文创写' },
  { id: 'quality_check', label: '章节质量检测' },
  { id: 'human_review', label: '人工审核卡点' },
  { id: 'power_systems', label: '境界力量体系' },
  { id: 'outline_persist', label: '分卷大纲入库' },
  { id: 'storylines', label: '三层图谱提取' },
  { id: 'character_arcs', label: '人物弧光演化' },
  { id: 'scenes', label: '戏剧场景规划' },
  { id: 'auto_conversation', label: '经典对白创作' },
]

const STAGE_DETAILS = {
  idea_expansion: {
    title: '当前活动：创意拓展阶段 (Idea Expansion)',
    description: 'AI 正在深度分析您的创意闪光点，将其融汇贯通为具备市场爆款潜质、剧情大线索及受众定位的网文创意基盘。'
  },
  world_building: {
    title: '当前活动：世界观背景构建 (World Building)',
    description: 'AI 正在为您生成浩瀚的世界观法则，包含世界起源、地理地貌（势力、秘境）、社会阶层、修行/科技规则及文明禁忌，用作后续大纲创作的唯一设定底座。'
  },
  character_design: {
    title: '当前活动：主角与配角人设塑造 (Character Design)',
    description: 'AI 正在倾力绘制核心人物的完整人设卡。包括角色心魔（缺陷）、隐藏动机、血脉/法宝设定、人际纠葛和战力定位，实现立体人物群像。'
  },
  outline_generation: {
    title: '当前活动：小说剧情大纲编排 (Outline Generation)',
    description: 'AI 正在梳理整本书的剧情总纲及卷级分布。精心设计黄金三章、剧情强爽点、反转高潮和终极大劫，形成跌宕起伏的脉络。'
  },
  chapter_generation: {
    title: '当前活动：章节正文创作生成 (Chapter Writing)',
    description: 'AI 正在全力以赴进行章节正文的高能创写！当前已开启前置“规划检查器”，逐一为每一章制定“章节规划单”（落实核心冲突、核销旧伏笔、埋下新伏笔、保留悬念钩子），强效避免脱轨。'
  },
  quality_check: {
    title: '当前活动：章节质量智能检测 (Quality Inspection)',
    description: '系统正在调用后台质检引擎，对已创写的章节进行 8 类维度的硬度指标打分（文笔流畅度、剧情节奏、冲突张力），同时智能比对图谱快照以防冲突。'
  },
  human_review: {
    title: '当前活动：人工审核卡点 (Human Gatekeeper)',
    description: '系统正在等待人工审核放行。在此环节您可以对章节内容做微调，确保生成的长篇正文每一字每一句都符合最高工业化创作预期。'
  },
  power_systems: {
    title: '当前活动：等级境界与力量体系细化 (Power System Design)',
    description: 'AI 正在精心配置小说等级规则。包括每一重大境界的实力表现、破镜瓶颈、战斗消耗公式及独特招式流派，确保升级爽感连绵不断。'
  },
  outline_persist: {
    title: '当前活动：小说分卷大纲入库持久化 (Outline Persisting)',
    description: 'AI 正在将生成的小说主大纲、分卷大纲与章节概要细致落库入表，为长篇网文提供极高一致性的大脑网络底图。'
  },
  storylines: {
    title: '当前活动：三层拓扑剧情图谱抽取 (Storyline Graph Extraction)',
    description: 'AI 正在梳理小说设定，在图谱数据库中精确聚类提取“人物关系谱”、“剧情演进谱”与“伏笔回收谱”三层全功能拓扑网，打通数据关联。'
  },
  character_arcs: {
    title: '当前活动：人物弧光成长轨迹演化 (Character Arcs)',
    description: 'AI 正在计算各主要角色在危机冲突中的心路转变轨迹，设计合乎情理的觉醒、黑化或蜕变成长弧光，防止脸谱化扁平人设。'
  },
  scenes: {
    title: '当前活动：重点戏剧场景库提炼 (Scene Templates)',
    description: 'AI 正在设计极具氛围描写与环境画面的戏剧场景（如经典夺宝、擂台决斗、坊市交易），以确保章节内容有身临其境的极佳画面感。'
  },
  auto_conversation: {
    title: '当前活动：经典个性化对白创作 (Auto Conversations)',
    description: 'AI 正在自动提炼角色个性的台词与说话口癖。设计富有张力的人物口角、高情商言语试探以及名场面对决对白。'
  }
}

const activeDetail = computed(() => {
  if (props.status === 'failed') {
    const stageObj = stages.find(s => s.id === props.currentStage)
    const stageLabel = stageObj ? stageObj.label : '未知步骤'
    return {
      title: `生成流程在【${stageLabel}】发生故障阻断`,
      description: `创作引擎在此步骤执行时遭遇了异常阻断。请检查下方“实时创作控制台”中以红字标出的详细报错信息，重新核查或补足您的小说世界观、人物卡设定，然后重新启动生成任务。`
    }
  }
  
  if (props.status === 'completed') {
    return {
      title: '生成流程全部顺利完成！',
      description: '全套 13 阶段创作流水线已全部高质量绿灯通关。世界观、精细大纲、分章正文正文及三层活态图谱均已完美入库。'
    }
  }

  return STAGE_DETAILS[props.currentStage] || {
    title: '任务准备中 / 后台流程初始化...',
    description: '系统正在拉取最新的小说设定和图谱上下文，为您初始化高保真 AI 小说生成流水线，请稍后。一旦任务开始，将立刻在此为您展示详细进度详情。'
  }
})

function stageStatus(id) {
  const currentIdx = stages.findIndex(s => s.id === props.currentStage)
  const thisIdx = stages.findIndex(s => s.id === id)
  
  if (props.status === 'completed') return 'done'
  
  if (thisIdx < currentIdx) return 'done'
  if (thisIdx === currentIdx) {
    return props.status === 'failed' ? 'failed' : 'active'
  }
  return 'pending'
}
</script>
