# 前端视觉统一与组件化重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一 xIaoShuo 前端所有页面的视觉风格（方案 A），再提取公用组件（方案 B），让产品呈现一致、干净、专业的体验。

**Architecture:** 
- 方案 A：纯 CSS/模板改动，不动逻辑。将所有页面统一到 `accent` 蓝调色系，统一容器宽度（`max-w-6xl`），统一按钮/卡片/表单样式。
- 方案 B：从 App.vue 和多个页面中提取出 `AppHeader.vue`、`AppFooter.vue`、`BaseModal.vue` 三个公用组件，减少重复代码。

**Tech Stack:** Vue 3 · Tailwind CSS · Vue Router

**工作目录:** `/Users/a1/Developer/projects/xIaoShuo/frontend`

---

## 方案 A：视觉统一（Task 1-6）

### Task 1: 统一旧版 `ink` 色系 → `accent` 色系

**影响文件:**
- Modify: `src/views/WorldEdit.vue`
- Modify: `src/views/Characters.vue`
- Modify: `src/views/StorylineManager.vue`
- Modify: `src/views/OutlineEditor.vue`
- Modify: `src/views/TaskList.vue`
- Modify: `src/views/Conversation.vue`

这些页面使用了 `text-ink-*` / `bg-ink-*` / `border-ink-*` 等 Tailwind 类名，但 `ink` 并非项目中定义的色系。实际渲染会回退到默认颜色，导致颜色不一致。

**解决方案：** 将 `ink-*` 全部替换为等价的 `neutral-*`（与项目中其他页面一致）。具体映射：
- `ink-50` → `neutral-50`
- `ink-100` → `neutral-100`
- `ink-200` → `neutral-200`
- `ink-300` → `neutral-300`
- `ink-400` → `neutral-400`
- `ink-500` → `neutral-500`
- `ink-600` → `neutral-600`
- `ink-700` → `neutral-700`
- `ink-800` → `neutral-800`
- `ink-900` → `neutral-900`
- `ink-950` → `neutral-950`
- `text-ink` → `text-neutral`
- `bg-ink` → `bg-neutral`
- `border-ink` → `border-neutral`
- `hover:text-ink` → `hover:text-neutral`
- `hover:bg-ink` → `hover:bg-neutral`
- `hover:border-ink` → `hover:border-neutral`

同时 `paper-*` → `neutral-*`。

- [ ] **Step 1: 替换 WorldEdit.vue 中的 ink 色系**

Read file, find all `ink-` / `primary-` classes, replace:
- `text-ink-900` → `text-neutral-900`
- `text-ink-700` → `text-neutral-700`
- `text-ink-600` → `text-neutral-600`
- `text-ink-500` → `text-neutral-500`
- `text-ink-400` → `text-neutral-400`
- `bg-primary-50` → `bg-accent-50`
- `text-primary-700` → `text-accent-700`

- [ ] **Step 2: 替换 Characters.vue 中的 ink 色系**

Same pattern: `text-ink-900` → `text-neutral-900`, `text-ink-800` → `text-neutral-800`, `text-ink-600` → `text-neutral-600`, `text-ink-500` → `text-neutral-500`, `text-ink-400` → `text-neutral-400`, `bg-primary-50` → `bg-accent-50`, `text-primary-700` → `text-accent-700`

- [ ] **Step 3: 替换 StorylineManager.vue 中的 ink 色系**

替换所有 `ink-*` → `neutral-*`，以及 `primary-*` → `accent-*`。

- [ ] **Step 4: 替换 OutlineEditor.vue 中的 ink 色系**

替换所有 `ink-*` → `neutral-*`，`primary-*` → `accent-*`，`paper-*` → `neutral-*`。

- [ ] **Step 5: 替换 TaskList.vue 中的 ink 色系**

替换所有 `ink-*` → `neutral-*`，`primary-*` → `accent-*`。

- [ ] **Step 6: 替换 Conversation.vue 中的 ink 色系**

替换所有 `ink-*` → `neutral-*`，`primary-*` → `accent-*`。

### Task 2: 统一 `TaskDetail.vue` 色系

**影响文件:**
- Modify: `src/views/TaskDetail.vue`

TaskDetail.vue 使用了硬编码的 `text-[#1d1d1f]`、`text-[#86868b]`、`bg-gray-*` 等，需要统一到项目标准色系。

- [ ] **Step 1: 替换 TaskDetail.vue 中的自定义颜色**

替换：
- `text-[#1d1d1f]` → `text-neutral-900`
- `text-[#86868b]` → `text-neutral-500`
- `bg-gray-*` → `bg-neutral-*`
- `text-gray-*` → `text-neutral-*`
- `border-gray-*` → `border-neutral-*`
- `hover:bg-gray-*` → `hover:bg-neutral-*`
- `hover:text-gray-*` → `hover:text-neutral-*`

### Task 3: 统一 `RelationGraph.vue` 色系

**影响文件:**
- Modify: `src/views/RelationGraph.vue`

使用了 `text-[#1d1d1f]`、`text-[#86868b]`、`gray-*`、`bg-gray-*` 等。

- [ ] **Step 1: 替换 RelationGraph.vue 中的自定义颜色**

替换 `text-[#1d1d1f]` → `text-neutral-900`，`text-[#86868b]` → `text-neutral-500`，所有 `gray-*` → `neutral-*`。

### Task 4: 统一 `VolumeList.vue` 色系

**影响文件:**
- Modify: `src/components/VolumeList.vue`

使用了 `gray-*` 色系（`text-gray-*`、`bg-gray-*`、`border-gray-*`）。

- [ ] **Step 1: 替换 VolumeList.vue 中的 gray 色系**

替换所有 `gray-*` → `neutral-*`（注意：`bg-indigo-*` 保留，它用于强调色）。

### Task 5: 修复 `Inspiration.vue` 的视觉脱节

**影响文件:**
- Modify: `src/views/Inspiration.vue`

Inspiration 是暗色玻璃态设计，与整体白底风格完全不同。但保留它的独特性也是合理的（灵感向导是一个沉浸式体验）。所以我们**只做微调**：统一 header 中的字体和间距，让它与其他页面有视觉联系。

- [ ] **Step 1: 检查 Inspiration.vue 是否需要改动**

保持其暗色风格不变（它是独立的沉浸式体验），只确保其 header 中的 `xIaoShuo` logo 与 App.vue 风格一致。

### Task 6: 统一 `style.css` 中的组件样式

**影响文件:**
- Modify: `src/style.css`

- [ ] **Step 1: 确认 style.css 中的 .btn-primary / .btn-secondary / .card / .input 等类定义已经统一**

当前 style.css 中的定义是合理的（使用 `accent-*` 色系），无需改动。但需要确保所有页面都使用这些类而非自定义样式。

---

## 方案 B：组件化提取（Task 7-9）

### Task 7: 提取 `AppHeader.vue` 组件

**当前情况：** `App.vue` 中定义了 header，但 `Inspiration.vue` 自建了一个完全不同的 header。

**目标：** 将 App.vue 的 header 提取为独立组件，供 App.vue 使用。Inspiration.vue 可以保持自己的 header（风格不同是合理的）。

**影响文件:**
- Create: `src/components/AppHeader.vue`
- Modify: `src/App.vue`

- [ ] **Step 1: 创建 AppHeader.vue 组件**

```vue
<template>
  <header class="bg-white border-b border-neutral-200 sticky top-0 z-50">
    <div class="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
      <router-link to="/" class="flex items-center gap-2 hover:opacity-80 transition-opacity select-none">
        <span class="text-lg font-bold text-neutral-900">xIaoShuo</span>
        <span class="text-[10px] bg-neutral-100 text-neutral-500 px-1.5 py-0.5 rounded font-medium">AI 创作平台</span>
      </router-link>
      <nav class="flex items-center gap-5">
        <router-link
          to="/tasks"
          class="text-sm text-neutral-500 hover:text-neutral-900 transition-colors font-medium"
        >
          任务大厅
        </router-link>
        <router-link
          to="/settings/llm"
          class="text-sm text-neutral-500 hover:text-neutral-900 transition-colors font-medium"
        >
          模型配置
        </router-link>
        <router-link
          to="/inspiration"
          class="text-sm text-neutral-500 hover:text-neutral-900 transition-colors font-medium"
        >
          灵感向导
        </router-link>
        <router-link to="/create" class="btn-primary text-sm flex items-center gap-1.5">
          <span>开启创作</span>
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
        </router-link>
      </nav>
    </div>
  </header>
</template>

<script setup>
</script>
```

- [ ] **Step 2: 修改 App.vue，使用 AppHeader 组件**

```vue
<script setup>
import AppHeader from './components/AppHeader.vue'
</script>
```

将模板中的 `<header>...</header>` 替换为 `<AppHeader />`。

- [ ] **Step 3: 确认 App.vue 可以正常编译**

运行 `npm run build` 或 `npx vite build` 验证无报错。

### Task 8: 提取 `AppFooter.vue` 组件

**影响文件:**
- Create: `src/components/AppFooter.vue`
- Modify: `src/App.vue`

- [ ] **Step 1: 创建 AppFooter.vue 组件**

```vue
<template>
  <footer class="border-t border-neutral-200 bg-neutral-50 py-6 mt-12">
    <div class="max-w-6xl mx-auto px-6 text-center text-xs text-neutral-400">
      xIaoShuo &copy; 2026 &middot; Powered by DeepSeek + LangGraph
    </div>
  </footer>
</template>

<script setup>
</script>
```

- [ ] **Step 2: 修改 App.vue，使用 AppFooter 组件**

将模板中的 `<footer>...</footer>` 替换为 `<AppFooter />`。

- [ ] **Step 3: 确认编译通过**

### Task 9: 提取 `BaseModal.vue` 通用模态框组件

**当前情况：** 多个页面各自实现了模态框（`NovelChaptersTab.vue` 中的删除确认、`VolumeList.vue` 中的删除确认、`ChapterModals.vue` 中的 AI 改写等），样式和结构重复。

**目标：** 提取一个通用的 `BaseModal.vue` 组件，支持 title、自定义内容插槽、确认/取消按钮。

**影响文件:**
- Create: `src/components/BaseModal.vue`

此组件仅创建，**不强制修改现有页面引用**（保持向后兼容）。后续逐步迁移。

- [ ] **Step 1: 创建 BaseModal.vue 组件**

```vue
<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="onCancel">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/20 backdrop-blur-sm"></div>
      <!-- Modal -->
      <div class="relative bg-white rounded-xl shadow-xl w-full max-w-md mx-4 border border-neutral-200 overflow-hidden">
        <!-- Header -->
        <div v-if="title" class="px-6 py-4 border-b border-neutral-200 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-neutral-900 flex items-center gap-2">
            <slot name="title-icon"></slot>
            {{ title }}
          </h3>
          <button
            v-if="closable"
            @click="onCancel"
            class="text-neutral-400 hover:text-neutral-600 transition-colors p-1 rounded-lg hover:bg-neutral-100"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <!-- Body -->
        <div class="px-6 py-5">
          <slot />
        </div>
        <!-- Footer -->
        <div v-if="$slots.footer" class="px-6 py-4 border-t border-neutral-200 flex justify-end gap-3">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  closable: { type: Boolean, default: true },
})

const emit = defineEmits(['cancel', 'confirm'])

function onCancel() {
  if (props.closable) {
    emit('cancel')
  }
}
</script>
```

- [ ] **Step 2: 确认编译通过**

```bash
cd frontend && npx vite build 2>&1 | tail -5
```

Expected: Build completes without errors.

---

## 验证

### Task 10: 整体验证

- [ ] **Step 1: 编译检查**

```bash
cd /Users/a1/Developer/projects/xIaoShuo/frontend && npx vite build 2>&1
```

Expected: 所有文件编译通过，无报错。

- [ ] **Step 2: 视觉检查清单**
  - [ ] Home.vue — 正常（已经是 accent 色系）
  - [ ] NovelDetail.vue — 正常（已经是 accent 色系）
  - [ ] ChapterEdit.vue — 正常（已经是 accent 色系）
  - [ ] Create.vue — 正常（已经是 accent 色系）
  - [ ] WorldEdit.vue — 已修复（ink → neutral）
  - [ ] Characters.vue — 已修复（ink → neutral）
  - [ ] StorylineManager.vue — 已修复（ink → neutral）
  - [ ] OutlineEditor.vue — 已修复（ink → neutral）
  - [ ] TaskList.vue — 已修复（ink → neutral）
  - [ ] TaskDetail.vue — 已修复（自定义颜色 → neutral）
  - [ ] Conversation.vue — 已修复（ink → neutral）
  - [ ] RelationGraph.vue — 已修复（自定义颜色 → neutral）
  - [ ] LLMSettings.vue — 正常（已经是 accent 色系）
  - [ ] ForeshadowTracker.vue — 正常（已经是 accent 色系）
  - [ ] Careers.vue — 正常（已经是 neutral/accent 色系）
  - [ ] VolumeList.vue — 已修复（gray → neutral）
  - [ ] Inspiration.vue — 保持暗色风格不变

- [ ] **Step 3: 确认新组件正常导出**

```bash
grep -r "AppHeader\|AppFooter\|BaseModal" src/ --include="*.vue" --include="*.js"
```

Expected: AppHeader/AppFooter 在 App.vue 中被引用。