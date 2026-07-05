<template>
  <div v-if="activeTaskId" class="task-monitor-wrap">
    <div class="task-card">
      <div class="card-header">
        <div class="header-left">
          <div class="pulse-indicator" :class="taskStatus"></div>
          <span class="header-title">AI Write Pipeline</span>
        </div>
        <button @click="closeMonitor" class="close-btn" title="Dismiss">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="card-body">
        <div class="stage-info">
          <div class="stage-name">{{ currentStageName || 'Connecting to pipeline...' }}</div>
          <div class="progress-pct" v-if="progress > 0">{{ progress }}%</div>
        </div>

        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: progress + '%' }"></div>
        </div>

        <p class="status-msg text-ellipsis">{{ currentMessage || 'Initializing WebSocket connection...' }}</p>
      </div>

      <div class="card-footer">
        <router-link :to="`/task/${activeTaskId}`" class="console-link">
          Open Control Console
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3.5 h-3.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
          </svg>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { activeTaskId, setActiveTaskId } from '../utils/taskState.js'
import { useWebSocket } from '../composables/useWebSocket.js'

export default {
  name: 'ActiveTaskMonitor',
  setup() {
    const currentStage = ref('')
    const progress = ref(0)
    const currentMessage = ref('')
    const taskStatus = ref('running') // running, completed, failed
    let wsController = null

    const stageMap = {
      'init': 'Initializing project state',
      'expand_idea': 'Expanding creative premise',
      'build_world': 'Building custom world bible',
      'design_characters': 'Designing character profiles',
      'generate_outline': 'Generating master outline',
      'generate_chapters': 'Writing novel chapters',
      'quality_check': 'Evaluating chapter text quality',
      'chapter_completed': 'Finalizing draft chapters',
      'completed': 'Generation completed successfully',
      'error': 'Generation error occurred'
    }

    const currentStageName = computed(() => {
      if (taskStatus.value === 'completed') return 'Completed'
      if (taskStatus.value === 'failed') return 'Failed'
      return stageMap[currentStage.value] || currentStage.value
    })

    const calculateProgress = (stage) => {
      const stageProgress = {
        'init': 5,
        'expand_idea': 15,
        'build_world': 30,
        'design_characters': 45,
        'generate_outline': 60,
        'generate_chapters': 80,
        'quality_check': 90,
        'chapter_completed': 95,
        'completed': 100,
        'error': 100
      }
      return stageProgress[stage] || 0
    }

    const startTracking = (taskId) => {
      if (wsController) {
        wsController.disconnect()
      }

      currentStage.value = 'init'
      progress.value = 5
      currentMessage.value = 'Connecting to task pipeline...'
      taskStatus.value = 'running'

      wsController = useWebSocket(taskId, {
        onMessage: (data) => {
          if (data.type === 'stage_start') {
            currentStage.value = data.stage
            progress.value = calculateProgress(data.stage)
            currentMessage.value = `Starting stage: ${stageMap[data.stage] || data.stage}`
          } else if (data.type === 'chapter_token') {
            currentStage.value = 'generate_chapters'
            progress.value = calculateProgress('generate_chapters')
            currentMessage.value = `Writing Chapter ${data.chapter_number || ''}...`
          } else if (data.type === 'completed') {
            taskStatus.value = 'completed'
            progress.value = 100
            currentMessage.value = 'All novel writing phases completed successfully.'
            // Keep on screen for 5 seconds, then dismiss
            setTimeout(() => {
              if (activeTaskId.value === taskId) {
                setActiveTaskId(null)
              }
            }, 5000)
          } else if (data.type === 'error') {
            taskStatus.value = 'failed'
            progress.value = 100
            currentMessage.value = data.message || 'Novel pipeline run failed.'
            setTimeout(() => {
              if (activeTaskId.value === taskId) {
                setActiveTaskId(null)
              }
            }, 8000)
          }
        }
      })

      wsController.connect()
    }

    const closeMonitor = () => {
      setActiveTaskId(null)
    }

    watch(activeTaskId, (newVal) => {
      if (newVal) {
        startTracking(newVal)
      } else {
        if (wsController) {
          wsController.disconnect()
          wsController = null
        }
      }
    })

    onMounted(() => {
      if (activeTaskId.value) {
        startTracking(activeTaskId.value)
      }
    })

    onUnmounted(() => {
      if (wsController) {
        wsController.disconnect()
      }
    })

    return {
      activeTaskId,
      currentStageName,
      progress,
      currentMessage,
      taskStatus,
      closeMonitor,
    }
  },
}
</script>

<style scoped>
.task-monitor-wrap {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 1000;
  width: 320px;
  font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
}

.task-card {
  background: rgba(15, 17, 26, 0.85);
  border: 1px rgba(255, 255, 255, 0.08) solid;
  border-radius: 16px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  padding: 16px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(99, 102, 241, 0.15);
  animation: slideIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes slideIn {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pulse-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #6366f1;
}

.pulse-indicator.running {
  animation: pulse 1.5s infinite alternate;
}

.pulse-indicator.completed {
  background-color: #10b981;
}

.pulse-indicator.failed {
  background-color: #ef4444;
}

@keyframes pulse {
  from {
    transform: scale(0.8);
    opacity: 0.5;
  }
  to {
    transform: scale(1.3);
    opacity: 1;
    box-shadow: 0 0 8px #6366f1;
  }
}

.header-title {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #94a3b8;
}

.close-btn {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.close-btn:hover {
  color: #f1f5f9;
  background: rgba(255, 255, 255, 0.05);
}

.stage-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.stage-name {
  font-size: 14px;
  font-weight: 600;
  color: #f1f5f9;
  max-width: 80%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-pct {
  font-size: 13px;
  font-weight: 700;
  color: #a5b4fc;
}

.progress-bar-bg {
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #a855f7);
  border-radius: 3px;
  transition: width 0.4s ease;
}

.status-msg {
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
  line-height: 1.4;
}

.text-ellipsis {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-footer {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px rgba(255, 255, 255, 0.06) solid;
}

.console-link {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #a5b4fc;
  text-decoration: none;
  transition: color 0.2s ease;
}

.console-link:hover {
  color: #c7d2fe;
}
</style>
