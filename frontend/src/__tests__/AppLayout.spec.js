import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '../App.vue'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/welcome', name: 'landing', component: { template: '<div>landing</div>' } },
      { path: '/login', name: 'login', component: { template: '<div>login</div>' } },
      { path: '/', name: 'home', component: { template: '<div>home</div>' } },
    ],
  })
}

async function mountAt(path) {
  const router = makeRouter()
  await router.push(path)
  await router.isReady()
  return mount(App, {
    global: {
      plugins: [router],
      stubs: {
        AppHeader: { template: '<header data-test="app-header" />' },
        AppFooter: { template: '<footer data-test="app-footer" />' },
        ActiveTaskMonitor: { template: '<aside data-test="task-monitor" />' },
      },
    },
  })
}

describe('App layout', () => {
  it('lets the landing page own its complete layout', async () => {
    const wrapper = await mountAt('/welcome')

    expect(wrapper.find('[data-test="app-header"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="app-footer"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="task-monitor"]').exists()).toBe(false)
  })

  it('keeps the shared application layout on authenticated views', async () => {
    const wrapper = await mountAt('/')

    expect(wrapper.find('[data-test="app-header"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="app-footer"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="task-monitor"]').exists()).toBe(true)
  })
})
