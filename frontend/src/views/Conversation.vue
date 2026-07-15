<template>
  <div class="max-w-3xl mx-auto px-6 py-10 animate-fade-up">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-bold text-ink-700 heading-serif">创作对话</h1>
        <p class="text-sm text-ink-400">{{ conversation?.topic }}</p>
      </div>
      <div class="flex gap-2">
        <button v-if="conversation?.status === 'active'" @click="conclude" class="btn-secondary text-sm">
          结束对话
        </button>
        <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm">返回</router-link>
      </div>
    </div>

    <!-- Messages -->
    <div class="space-y-4 mb-6 max-h-[500px] overflow-y-auto" ref="messagesContainer">
      <div v-for="(msg, idx) in messages" :key="msg.id"
        class="p-4 rounded-lg max-w-[85%] animate-fade-up-stagger"
        :style="{ animationDelay: `${Math.min(idx,8)*60}ms` }"
        :class="msg.role === 'user' ? 'ml-auto bg-vermilion-50 text-ink-700' : 'bg-paper-50 border border-ink-100'"
      >
        <p class="text-sm whitespace-pre-wrap">{{ msg.content }}</p>
        <div class="flex items-center gap-2 mt-2">
          <span class="text-[10px] text-ink-300">{{ formatTime(msg.created_at) }}</span>
          <span v-if="msg.confirmed_as" class="badge-completed text-[10px]">已确定为{{ confirmLabel(msg.confirmed_as) }}</span>
          <template v-if="msg.role === 'assistant' && !msg.confirmed_as && conversation?.status === 'active'">
            <button @click="confirmMsg(msg.id, 'world')" class="text-[10px] text-vermilion-500 hover:text-vermilion-600">确定为世界观</button>
            <button @click="confirmMsg(msg.id, 'character')" class="text-[10px] text-emerald-500 hover:text-emerald-700">确定为人物</button>
            <button @click="confirmMsg(msg.id, 'storyline')" class="text-[10px] text-purple-500 hover:text-purple-700">确定为故事线</button>
          </template>
        </div>
      </div>
      <div v-if="sending" class="p-4 rounded-lg bg-paper-50 border border-ink-100 max-w-[85%]">
        <p class="text-sm text-ink-300">思考中...</p>
      </div>
    </div>

    <!-- Suggestions (after conclude) -->
    <div v-if="suggestions.length" class="card p-5 mb-6 animate-fade-up">
      <h2 class="text-sm font-medium text-ink-600 mb-3">对话结论</h2>
      <ul class="space-y-3">
        <li v-for="(s, i) in suggestions" :key="i" class="flex items-start gap-2">
          <span class="badge bg-paper-100 text-ink-600 shrink-0 mt-0.5">{{ s.type }}</span>
          <span class="text-sm flex-1">{{ s.content }}</span>
          <button
            @click="applySuggestion(s)"
            class="btn-secondary text-xs shrink-0"
            :disabled="s.applied"
          >{{ s.applied ? '已应用' : '应用到设定' }}</button>
        </li>
      </ul>
      <button @click="generateStorylines" class="btn-secondary text-xs mt-3" :disabled="generatingStorylines">
        {{ generatingStorylines ? '生成中...' : '从对话生成故事线' }}
      </button>
      <button @click="generateOutline" class="btn-primary text-xs mt-3 ml-2" :disabled="generatingOutline">
        {{ generatingOutline ? '生成中...' : '生成总纲→卷纲' }}
      </button>
      <p v-if="storylineGenerated" class="text-xs text-emerald-600 mt-1">故事线已生成</p>
      <p v-if="outlineGenerated" class="text-xs text-emerald-600 mt-1">总纲和卷纲已生成，<router-link :to="`/novels/${novelId}/outlines`" class="text-vermilion-500 underline">查看大纲</router-link></p>
    </div>

    <!-- Input -->
    <form v-if="conversation?.status === 'active'" @submit.prevent="send" class="flex gap-3">
      <input
        v-model="input"
        class="input flex-1"
        placeholder="输入你的想法..."
        :disabled="sending"
        maxlength="2000"
      />
      <button type="submit" class="btn-primary" :disabled="!input.trim() || sending">发送</button>
    </form>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const novelId = route.params.id
const convId = route.params.convId

const conversation = ref(null)
const messages = ref([])
const input = ref('')
const sending = ref(false)
const suggestions = ref([])
const messagesContainer = ref(null)
const generatingStorylines = ref(false)
const storylineGenerated = ref(false)
const generatingOutline = ref(false)
const outlineGenerated = ref(false)

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function load() {
  const res = await fetch(`/api/v1/projects/${novelId}/conversations/${convId}`)
  if (res.ok) {
    const data = await res.json()
    conversation.value = data
    messages.value = data.messages || []
  }
}

async function send() {
  if (!input.value.trim() || sending.value) return
  const content = input.value.trim()
  input.value = ''

  messages.value.push({ id: Date.now(), role: 'user', content, created_at: new Date().toISOString() })
  sending.value = true
  await nextTick()
  scrollToBottom()

  try {
    const res = await fetch(`/api/v1/projects/${novelId}/conversations/${convId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
    if (res.ok) {
      const aiMsg = await res.json()
      messages.value.push(aiMsg)
    }
  } finally {
    sending.value = false
    await nextTick()
    scrollToBottom()
  }
}

async function conclude() {
  const res = await fetch(`/api/v1/projects/${novelId}/conversations/${convId}/conclude`, { method: 'POST' })
  if (res.ok) {
    const data = await res.json()
    conversation.value = { ...conversation.value, status: 'concluded' }
    suggestions.value = (data.suggestions || []).map(s => ({ ...s, applied: false }))
  }
}

async function applySuggestion(suggestion) {
  const res = await fetch(`/api/v1/projects/${novelId}/conversations/${convId}/apply-suggestion`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suggestion_type: suggestion.type, content: suggestion.content }),
  })
  if (res.ok) {
    suggestion.applied = true
  }
}

async function generateStorylines() {
  generatingStorylines.value = true
  storylineGenerated.value = false
  const res = await fetch(`/api/v1/projects/${novelId}/storylines/from-conversation/${convId}`, { method: 'POST' })
  if (res.ok) {
    storylineGenerated.value = true
  }
  generatingStorylines.value = false
}

async function generateOutline() {
  generatingOutline.value = true
  outlineGenerated.value = false
  const res = await fetch(`/api/v1/projects/${novelId}/conversations/${convId}/generate-outline`, { method: 'POST' })
  if (res.ok) {
    outlineGenerated.value = true
  }
  generatingOutline.value = false
}

async function confirmMsg(msgId, confirmAs) {
  const res = await fetch(`/api/v1/projects/${novelId}/conversations/${convId}/messages/${msgId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm_as: confirmAs }),
  })
  if (res.ok) {
    const msg = messages.value.find(m => m.id === msgId)
    if (msg) msg.confirmed_as = confirmAs
  }
}

function confirmLabel(type) {
  return { world: '世界观', character: '人物', storyline: '故事线', outline: '大纲' }[type] || type
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

onMounted(load)
</script>
