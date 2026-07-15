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
  background: radial-gradient(circle at top left, #2c2416, #141009);
  font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, sans-serif;
  color: #5c4f3d;
}

.glass-card {
  width: 100%;
  max-width: 420px;
  padding: 40px;
  background: rgba(253, 251, 247, 0.92);
  border: 1px solid rgba(217, 208, 194, 0.6);
  border-radius: 20px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 15px 35px rgba(44, 36, 22, 0.12);
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.title {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: #2c2416;
  font-family: "Noto Serif SC", "Source Han Serif SC", serif;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 14px;
  color: #8a7a64;
  margin: 0;
}

.tabs {
  display: flex;
  background: rgba(247, 245, 241, 0.6);
  border: 1px solid rgba(217, 208, 194, 0.5);
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 25px;
}

.tab-btn {
  flex: 1;
  padding: 10px;
  border: none;
  background: none;
  color: #8a7a64;
  font-size: 14px;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.tab-btn:hover {
  color: #3d3327;
}

.tab-btn.active {
  background: rgba(168, 50, 74, 0.1);
  border: 1px solid rgba(168, 50, 74, 0.4);
  color: #8a273a;
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
  color: #8a7a64;
}

.input-group input {
  padding: 12px 16px;
  background: rgba(253, 251, 247, 0.8);
  border: 1px solid rgba(217, 208, 194, 0.7);
  border-radius: 10px;
  color: #3d3327;
  font-size: 15px;
  outline: none;
  transition: all 0.2s ease;
}

.input-group input:focus {
  border-color: #d94e6f;
  box-shadow: 0 0 0 3px rgba(168, 50, 74, 0.15);
}

.error-msg {
  font-size: 14px;
  color: #8a273a;
  background: rgba(253, 242, 244, 0.7);
  border: 1px solid rgba(245, 184, 196, 0.6);
  border-radius: 8px;
  padding: 10px 14px;
}

.submit-btn {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 10px;
  padding: 14px;
  background: #2c2416;
  border: none;
  border-radius: 10px;
  color: #fdfbf7;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(44, 36, 22, 0.25);
}

.submit-btn:hover {
  transform: translateY(-2px);
  background: #a8324a;
  box-shadow: 0 6px 20px rgba(168, 50, 74, 0.35);
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
  border: 2px solid rgba(253, 251, 247, 0.3);
  border-top-color: #fdfbf7;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
