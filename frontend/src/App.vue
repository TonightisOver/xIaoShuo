<template>
  <div class="min-h-screen flex flex-col bg-slate-950 text-slate-100">
    <AppHeader v-slot="{}" v-if="showLayout" />

    <main class="flex-1">
      <router-view />
    </main>

    <AppFooter v-if="showLayout" />

    <ActiveTaskMonitor v-if="showLayout" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import ActiveTaskMonitor from './components/ActiveTaskMonitor.vue'

const route = useRoute()
const showLayout = computed(() => route.name && route.name !== 'login')
</script>

