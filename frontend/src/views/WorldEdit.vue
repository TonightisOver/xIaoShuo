<template>
  <div class="max-w-3xl mx-auto px-6 py-10">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-ink-900">世界观设定</h1>
      <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm">返回</router-link>
    </div>

    <form @submit.prevent="save" class="space-y-5">
      <div>
        <label class="block text-sm font-medium text-ink-700 mb-2">世界背景</label>
        <textarea v-model="form.background" class="input min-h-[100px] resize-y" placeholder="描述这个世界的基本设定..."></textarea>
      </div>
      <div>
        <label class="block text-sm font-medium text-ink-700 mb-2">地理环境</label>
        <textarea v-model="form.geography" class="input min-h-[80px] resize-y" placeholder="大陆、国家、地形..."></textarea>
      </div>
      <div>
        <label class="block text-sm font-medium text-ink-700 mb-2">文化体系</label>
        <textarea v-model="form.culture" class="input min-h-[80px] resize-y" placeholder="宗门、势力、社会结构..."></textarea>
      </div>
      <div>
        <label class="block text-sm font-medium text-ink-700 mb-2">世界规则</label>
        <textarea v-model="form.rules" class="input min-h-[80px] resize-y" placeholder="修炼体系、力量法则..."></textarea>
      </div>

      <div class="flex gap-3 pt-2">
        <button type="submit" class="btn-primary" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
        <router-link :to="`/novels/${novelId}`" class="btn-secondary">取消</router-link>
      </div>

      <p v-if="saved" class="text-sm text-emerald-600">已保存</p>
    </form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const novelId = route.params.id

const form = ref({ background: '', geography: '', culture: '', rules: '' })
const saving = ref(false)
const saved = ref(false)

async function load() {
  const res = await fetch(`/api/v1/projects/${novelId}/world`)
  if (res.ok) {
    const data = await res.json()
    form.value = {
      background: data.background || '',
      geography: data.geography || '',
      culture: data.culture || '',
      rules: data.rules || '',
    }
  }
}

async function save() {
  saving.value = true
  saved.value = false
  await fetch(`/api/v1/projects/${novelId}/world`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form.value),
  })
  saving.value = false
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}

onMounted(load)
</script>
