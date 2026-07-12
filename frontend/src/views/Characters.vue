<template>
  <div class="max-w-3xl mx-auto px-6 py-10 animate-fade-up">
    <div class="flex items-center justify-between mb-6">
      <h1 class="heading-serif text-xl">人物管理</h1>
      <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm">返回</router-link>
    </div>

    <!-- Add Character Form -->
    <div class="card p-5 mb-6">
      <h2 class="text-sm font-serif text-ink-700 font-medium mb-3">添加人物</h2>
      <form @submit.prevent="addCharacter" class="grid grid-cols-2 gap-3">
        <input v-model="newChar.name" class="input text-sm" placeholder="姓名" required />
        <select v-model="newChar.role" class="input text-sm">
          <option value="">选择角色</option>
          <option value="主角">主角</option>
          <option value="配角">配角</option>
          <option value="反派">反派</option>
          <option value="导师">导师</option>
        </select>
        <textarea v-model="newChar.description" class="input text-sm col-span-2 min-h-[60px]" placeholder="人物描述"></textarea>
        <textarea v-model="newChar.personality" class="input text-sm col-span-2 min-h-[60px]" placeholder="性格特点"></textarea>
        <textarea v-model="newChar.abilities" class="input text-sm col-span-2 min-h-[60px]" placeholder="能力/技能"></textarea>
        <div class="col-span-2">
          <button type="submit" class="btn-primary text-sm">添加</button>
        </div>
      </form>
    </div>

    <!-- Character List -->
    <div class="space-y-3">
      <div v-for="(char, idx) in characters" :key="char.id" class="card card-hover shine-on-hover p-5 animate-fade-up-stagger" :style="{ animationDelay: `${Math.min(idx,8)*60}ms` }">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-2">
              <span class="font-bold text-ink-700">{{ char.name }}</span>
              <span v-if="char.role" class="badge bg-vermilion-50 text-vermilion-600">{{ char.role }}</span>
            </div>
            <p v-if="char.description" class="text-sm text-ink-600 mb-1">{{ char.description }}</p>
            <p v-if="char.personality" class="text-sm text-ink-400"><span class="text-ink-300">性格：</span>{{ char.personality }}</p>
            <p v-if="char.abilities" class="text-sm text-ink-400"><span class="text-ink-300">能力：</span>{{ char.abilities }}</p>
          </div>
          <button @click="deleteChar(char.id)" class="text-red-400 hover:text-red-600 text-sm ml-4">删除</button>
        </div>
      </div>
      <p v-if="characters.length === 0" class="text-center text-ink-300 py-8">暂无人物，请添加</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const novelId = route.params.id

const characters = ref([])
const newChar = ref({ name: '', role: '', description: '', personality: '', abilities: '' })

async function load() {
  const res = await fetch(`/api/v1/projects/${novelId}/characters`)
  if (res.ok) characters.value = await res.json()
}

async function addCharacter() {
  if (!newChar.value.name) return
  const body = Object.fromEntries(Object.entries(newChar.value).filter(([, v]) => v))
  await fetch(`/api/v1/projects/${novelId}/characters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  newChar.value = { name: '', role: '', description: '', personality: '', abilities: '' }
  await load()
}

async function deleteChar(id) {
  await fetch(`/api/v1/projects/${novelId}/characters/${id}`, { method: 'DELETE' })
  await load()
}

onMounted(load)
</script>
