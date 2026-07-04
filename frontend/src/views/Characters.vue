<template>
  <div class="max-w-3xl mx-auto px-6 py-10">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-neutral-900">人物管理</h1>
      <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm">返回</router-link>
    </div>

    <!-- Add Character Form -->
    <div class="card p-5 mb-6">
      <h2 class="text-sm font-medium text-neutral-600 mb-3">添加人物</h2>
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
      <div v-for="char in characters" :key="char.id" class="card p-5">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-2">
              <span class="font-bold text-neutral-800">{{ char.name }}</span>
              <span v-if="char.role" class="badge bg-accent-50 text-accent-700">{{ char.role }}</span>
            </div>
            <p v-if="char.description" class="text-sm text-neutral-600 mb-1">{{ char.description }}</p>
            <p v-if="char.personality" class="text-sm text-neutral-500"><span class="text-neutral-400">性格：</span>{{ char.personality }}</p>
            <p v-if="char.abilities" class="text-sm text-neutral-500"><span class="text-neutral-400">能力：</span>{{ char.abilities }}</p>
          </div>
          <button @click="deleteChar(char.id)" class="text-red-400 hover:text-red-600 text-sm ml-4">删除</button>
        </div>
      </div>
      <p v-if="characters.length === 0" class="text-center text-neutral-400 py-8">暂无人物，请添加</p>
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
