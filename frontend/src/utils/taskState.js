import { ref } from 'vue'

export const activeTaskId = ref(
  typeof localStorage !== 'undefined' ? localStorage.getItem('active_task_id') : null
)

export function setActiveTaskId(id) {
  activeTaskId.value = id
  if (typeof localStorage !== 'undefined') {
    if (id) {
      localStorage.setItem('active_task_id', id)
    } else {
      localStorage.removeItem('active_task_id')
    }
  }
}

