<template>
  <div class="login-container">
    <div class="glass-card">
      <div class="header">
        <h1 class="title">xIaoShuo</h1>
        <p class="subtitle">AI-Powered Novel Generation Platform</p>
      </div>

      <div class="tabs">
        <button 
          :class="['tab-btn', { active: isLogin }]" 
          @click="isLogin = true"
        >
          Sign In
        </button>
        <button 
          :class="['tab-btn', { active: !isLogin }]" 
          @click="isLogin = false"
        >
          Sign Up
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="form">
        <div class="input-group">
          <label for="username">Username</label>
          <input 
            type="text" 
            id="username" 
            v-model="username" 
            placeholder="Enter username" 
            required 
          />
        </div>

        <div class="input-group">
          <label for="password">Password</label>
          <input 
            type="password" 
            id="password" 
            v-model="password" 
            placeholder="Enter password (min 6 chars)" 
            required 
          />
        </div>

        <div v-if="error" class="error-msg">
          {{ error }}
        </div>

        <button type="submit" class="submit-btn" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          <span v-else>{{ isLogin ? 'Sign In' : 'Create Account' }}</span>
        </button>
      </form>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

export default {
  name: 'LoginView',
  setup() {
    const isLogin = ref(true)
    const username = ref('')
    const password = ref('')
    const error = ref('')
    const loading = ref(false)
    const router = useRouter()

    const handleSubmit = async () => {
      error.value = ''
      loading.value = true

      const endpoint = isLogin.value ? '/api/v1/auth/login' : '/api/v1/auth/register'

      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            username: username.value.trim(),
            password: password.value,
          }),
        })

        const data = await response.json()

        if (!response.ok) {
          throw new Error(data.detail || 'Authentication failed')
        }

        // Save session information
        localStorage.setItem('session_token', data.session_token)
        localStorage.setItem('username', data.username)
        localStorage.setItem('user_id', data.user_id)

        // Redirect to homepage
        router.push({ name: 'home' })
      } catch (err) {
        error.value = err.message
      } finally {
        loading.value = false
      }
    }

    return {
      isLogin,
      username,
      password,
      error,
      loading,
      handleSubmit,
    }
  },
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: radial-gradient(circle at top left, #1a1b2f, #0f1015);
  font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  color: #e2e8f0;
}

.glass-card {
  width: 100%;
  max-width: 420px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px rgba(255, 255, 255, 0.08) solid;
  border-radius: 20px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.title {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 14px;
  color: #94a3b8;
  margin: 0;
}

.tabs {
  display: flex;
  background: rgba(255, 255, 255, 0.02);
  border: 1px rgba(255, 255, 255, 0.05) solid;
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 25px;
}

.tab-btn {
  flex: 1;
  padding: 10px;
  border: none;
  background: none;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.tab-btn:hover {
  color: #f1f5f9;
}

.tab-btn.active {
  background: rgba(99, 102, 241, 0.2);
  border: 1px rgba(99, 102, 241, 0.4) solid;
  color: #a5b4fc;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-group label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #94a3b8;
}

.input-group input {
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px rgba(255, 255, 255, 0.1) solid;
  border-radius: 10px;
  color: #f1f5f9;
  font-size: 15px;
  outline: none;
  transition: all 0.2s ease;
}

.input-group input:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.error-msg {
  font-size: 14px;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.15);
  border: 1px rgba(239, 68, 68, 0.2) solid;
  border-radius: 8px;
  padding: 10px 14px;
}

.submit-btn {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 10px;
  padding: 14px;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  border: none;
  border-radius: 10px;
  color: white;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
}

.submit-btn:active {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
  transform: none;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
