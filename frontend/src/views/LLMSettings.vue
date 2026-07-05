<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-neutral-900">模型配置</h1>
      <p class="text-neutral-500 mt-1 text-sm">管理 LLM API 配置，查看 token 用量统计</p>
    </div>

    <!-- LLM 配置列表 -->
    <div class="card p-6 mb-8">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-neutral-800">API 配置</h2>
        <button class="btn-primary text-sm" @click="openCreateModal">新增配置</button>
      </div>

      <!-- Loading -->
      <div v-if="loadingConfigs" class="flex items-center justify-center py-12">
        <div class="w-6 h-6 border-2 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>

      <!-- Empty -->
      <div v-else-if="configs.length === 0" class="text-center py-10 text-neutral-400 text-sm">
        暂无配置，点击"新增配置"添加第一条
      </div>

      <!-- Table -->
      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-neutral-200 text-left text-xs text-neutral-500">
              <th class="pb-2 pr-4 font-medium">名称</th>
              <th class="pb-2 pr-4 font-medium">Base URL</th>
              <th class="pb-2 pr-4 font-medium">Flash 模型</th>
              <th class="pb-2 pr-4 font-medium">Pro 模型</th>
              <th class="pb-2 pr-4 font-medium">状态</th>
              <th class="pb-2 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="cfg in configs"
              :key="cfg.id"
              class="border-b border-neutral-100 last:border-0"
            >
              <td class="py-3 pr-4 font-medium text-neutral-800">{{ cfg.name }}</td>
              <td class="py-3 pr-4 text-neutral-500 max-w-[200px] truncate">{{ cfg.base_url }}</td>
              <td class="py-3 pr-4 text-neutral-500">{{ cfg.model_flash }}</td>
              <td class="py-3 pr-4 text-neutral-500">{{ cfg.model_pro }}</td>
              <td class="py-3 pr-4">
                <span
                  :class="cfg.is_active
                    ? 'bg-green-100 text-green-700'
                    : 'bg-neutral-100 text-neutral-500'"
                  class="text-xs font-medium px-2 py-0.5 rounded"
                >
                  {{ cfg.is_active ? '激活' : '未激活' }}
                </span>
              </td>
              <td class="py-3">
                <div class="flex items-center gap-2">
                  <button
                    class="text-xs text-accent-600 hover:text-accent-800 font-medium transition-colors"
                    @click="openEditModal(cfg)"
                  >编辑</button>
                  <button
                    v-if="!cfg.is_active"
                    class="text-xs text-green-600 hover:text-green-800 font-medium transition-colors"
                    @click="activateConfig(cfg.id)"
                  >激活</button>
                  <button
                    v-if="!cfg.is_active"
                    class="text-xs text-red-400 hover:text-red-600 font-medium transition-colors"
                    @click="deleteConfig(cfg.id)"
                  >删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Token 统计 -->
    <div class="card p-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-base font-semibold text-neutral-800">Token 用量统计</h2>
        <button class="text-xs text-neutral-500 hover:text-neutral-800 transition-colors" @click="fetchStats">刷新</button>
      </div>

      <div v-if="loadingStats" class="flex items-center justify-center py-8">
        <div class="w-6 h-6 border-2 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
      </div>

      <div v-else-if="stats">
        <!-- 汇总卡片 -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div class="bg-neutral-50 rounded-lg p-4">
            <p class="text-xs text-neutral-500 mb-1">总调用次数</p>
            <p class="text-xl font-bold text-neutral-900">{{ stats.total_calls.toLocaleString() }}</p>
          </div>
          <div class="bg-neutral-50 rounded-lg p-4">
            <p class="text-xs text-neutral-500 mb-1">累计 Prompt Tokens</p>
            <p class="text-xl font-bold text-neutral-900">{{ stats.total_prompt_tokens.toLocaleString() }}</p>
          </div>
          <div class="bg-neutral-50 rounded-lg p-4">
            <p class="text-xs text-neutral-500 mb-1">累计 Completion Tokens</p>
            <p class="text-xl font-bold text-neutral-900">{{ stats.total_completion_tokens.toLocaleString() }}</p>
          </div>
          <div class="bg-neutral-50 rounded-lg p-4">
            <p class="text-xs text-neutral-500 mb-1">累计总 Tokens</p>
            <p class="text-xl font-bold text-neutral-900">{{ stats.total_tokens.toLocaleString() }}</p>
          </div>
        </div>

        <!-- 跳过次数 -->
        <p v-if="stats.records_skipped > 0" class="text-xs text-neutral-400 mb-4">
          注：{{ stats.records_skipped }} 次调用未返回 token 信息（已跳过记录）
        </p>

        <!-- 按模型分组 -->
        <div v-if="Object.keys(stats.by_model).length > 0" class="mb-6">
          <h3 class="text-sm font-medium text-neutral-700 mb-3">按模型分组</h3>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-neutral-200 text-left text-xs text-neutral-500">
                  <th class="pb-2 pr-4 font-medium">模型</th>
                  <th class="pb-2 pr-4 font-medium">调用次数</th>
                  <th class="pb-2 pr-4 font-medium">Prompt Tokens</th>
                  <th class="pb-2 pr-4 font-medium">Completion Tokens</th>
                  <th class="pb-2 font-medium">总 Tokens</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(data, model) in stats.by_model"
                  :key="model"
                  class="border-b border-neutral-100 last:border-0"
                >
                  <td class="py-2 pr-4 font-medium text-neutral-800">{{ model }}</td>
                  <td class="py-2 pr-4 text-neutral-600">{{ data.calls.toLocaleString() }}</td>
                  <td class="py-2 pr-4 text-neutral-600">{{ data.prompt_tokens.toLocaleString() }}</td>
                  <td class="py-2 pr-4 text-neutral-600">{{ data.completion_tokens.toLocaleString() }}</td>
                  <td class="py-2 text-neutral-600">{{ data.total_tokens.toLocaleString() }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <p v-else class="text-sm text-neutral-400">暂无调用记录</p>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div
      v-if="showModal"
      class="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      @click.self="closeModal"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
        <h3 class="text-base font-semibold text-neutral-900 mb-4">
          {{ editingConfig ? '编辑配置' : '新增配置' }}
        </h3>

        <div class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-neutral-700 mb-1">名称</label>
            <input v-model="form.name" class="input w-full" placeholder="例：我的 DeepSeek" />
          </div>
          <div>
            <label class="block text-xs font-medium text-neutral-700 mb-1">Base URL</label>
            <input v-model="form.base_url" class="input w-full" placeholder="https://api.deepseek.com/v1" />
          </div>
          <div>
            <label class="block text-xs font-medium text-neutral-700 mb-1">API Key</label>
            <input v-model="form.api_key" type="password" class="input w-full" placeholder="sk-..." />
          </div>
          <div>
            <label class="block text-xs font-medium text-neutral-700 mb-1">Flash 模型</label>
            <input v-model="form.model_flash" class="input w-full" placeholder="deepseek-v4-flash" />
          </div>
          <div>
            <label class="block text-xs font-medium text-neutral-700 mb-1">Pro 模型</label>
            <input v-model="form.model_pro" class="input w-full" placeholder="deepseek-v4-pro" />
          </div>
        </div>

        <p v-if="formError" class="text-xs text-red-500 mt-3">{{ formError }}</p>

        <div class="flex justify-end gap-3 mt-6">
          <button class="btn-secondary text-sm" @click="closeModal">取消</button>
          <button class="btn-primary text-sm" :disabled="saving" @click="saveConfig">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const configs = ref([])
const loadingConfigs = ref(true)
const stats = ref(null)
const loadingStats = ref(true)

const showModal = ref(false)
const editingConfig = ref(null)
const saving = ref(false)
const formError = ref('')

const form = ref({
  name: '',
  base_url: '',
  api_key: '',
  model_flash: '',
  model_pro: '',
})

async function fetchConfigs() {
  loadingConfigs.value = true
  try {
    const res = await fetch('/api/v1/llm/configs')
    if (res.ok) {
      configs.value = await res.json()
    } else {
      configs.value = []
    }
  } catch {
    configs.value = []
  } finally {
    loadingConfigs.value = false
  }
}

async function fetchStats() {
  loadingStats.value = true
  try {
    const res = await fetch('/api/v1/llm/token-stats')
    if (res.ok) {
      stats.value = await res.json()
    } else {
      stats.value = null
    }
  } catch {
    stats.value = null
  } finally {
    loadingStats.value = false
  }
}

function openCreateModal() {
  editingConfig.value = null
  form.value = { name: '', base_url: '', api_key: '', model_flash: '', model_pro: '' }
  formError.value = ''
  showModal.value = true
}

function openEditModal(cfg) {
  editingConfig.value = cfg
  form.value = {
    name: cfg.name,
    base_url: cfg.base_url,
    api_key: '',
    model_flash: cfg.model_flash,
    model_pro: cfg.model_pro,
  }
  formError.value = ''
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

async function saveConfig() {
  formError.value = ''
  if (!form.value.name || !form.value.base_url || !form.value.model_flash || !form.value.model_pro) {
    formError.value = '请填写所有必填字段'
    return
  }
  if (!editingConfig.value && !form.value.api_key) {
    formError.value = '新增配置时 API Key 不能为空'
    return
  }

  saving.value = true
  try {
    const body = { ...form.value }
    // 编辑时若 api_key 为空则不传（保留原值）
    if (editingConfig.value && !body.api_key) {
      delete body.api_key
    }

    const url = editingConfig.value
      ? `/api/v1/llm/configs/${editingConfig.value.id}`
      : '/api/v1/llm/configs'
    const method = editingConfig.value ? 'PUT' : 'POST'

    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      formError.value = err.detail || '保存失败'
      return
    }

    closeModal()
    await fetchConfigs()
  } finally {
    saving.value = false
  }
}

async function activateConfig(id) {
  const res = await fetch(`/api/v1/llm/configs/${id}/activate`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    alert(err.detail || '激活失败')
    return
  }
  await fetchConfigs()
}

async function deleteConfig(id) {
  if (!confirm('确定删除此配置？')) return
  const res = await fetch(`/api/v1/llm/configs/${id}`, { method: 'DELETE' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    alert(err.detail || '删除失败')
    return
  }
  await fetchConfigs()
}

onMounted(() => {
  fetchConfigs()
  fetchStats()
})
</script>
