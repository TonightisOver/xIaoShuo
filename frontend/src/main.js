import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './style.css'

// Global Fetch Interceptor for Authentication
const originalFetch = window.fetch
window.fetch = async (url, options = {}) => {
  const token = localStorage.getItem('session_token')
  if (token && url.toString().startsWith('/api/')) {
    options.headers = options.headers || {}
    options.headers['Authorization'] = `Bearer ${token}`
    options.headers['x-session-token'] = token
  }

  const response = await originalFetch(url, options)

  // Redirect to login if token is expired/invalid
  if (response.status === 401 && !url.toString().includes('/api/v1/auth/')) {
    localStorage.removeItem('session_token')
    localStorage.removeItem('username')
    localStorage.removeItem('user_id')
    window.location.href = '/login'
  }

  return response
}

createApp(App).use(router).mount('#app')

