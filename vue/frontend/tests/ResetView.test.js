import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import axios from 'axios'
import ResetView from '../src/views/ResetView.vue'

vi.mock('axios')

describe('ResetView', () => {
  let router

  beforeEach(() => {
    vi.clearAllMocks()
    vi.unstubAllEnvs()
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/reset', component: ResetView },
      ],
    })
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('renders loading state on mount', async () => {
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://localhost:8001')
    vi.stubEnv('VITE_APP_NAME', 'TestApp')
    
    // Mock axios to never resolve (keep loading)
    axios.delete.mockImplementation(() => new Promise(() => {}))

    await router.push('/reset')
    await router.isReady()

    const wrapper = mount(ResetView, { global: { plugins: [router] } })
    
    expect(wrapper.find('.animate-spin').exists()).toBe(true)
    expect(wrapper.text()).toContain('Cache Reset')
  })

  it('shows success after API call', async () => {
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://localhost:8001')
    vi.stubEnv('VITE_APP_NAME', 'TestApp')
    
    // Mock successful axios response
    axios.delete.mockResolvedValue({
      data: {
        app_name: 'TestApp',
        cleared: ['TestApp_userright', 'TestApp_screenright'],
        message: 'Cache cleared'
      }
    })

    await router.push('/reset')
    await router.isReady()

    const wrapper = mount(ResetView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Cache cleared for')
    expect(wrapper.text()).toContain('TestApp')
    expect(wrapper.text()).toContain('TestApp_userright')
    expect(wrapper.text()).toContain('TestApp_screenright')
    expect(wrapper.find('.bg-primary\\/10').exists()).toBe(true)
    expect(axios.delete).toHaveBeenCalledWith('http://localhost:8001/reset/TestApp')
  })

  it('shows error on API failure', async () => {
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://localhost:8001')
    vi.stubEnv('VITE_APP_NAME', 'TestApp')
    
    // Mock axios error
    axios.delete.mockRejectedValue({
      response: {
        data: { detail: 'Redis unavailable' }
      }
    })

    await router.push('/reset')
    await router.isReady()

    const wrapper = mount(ResetView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('.text-destructive').exists()).toBe(true)
    expect(wrapper.text()).toContain('Redis unavailable')
  })

  it('shows error when env vars missing', async () => {
    // Stub env vars as empty strings (falsy)
    vi.stubEnv('VITE_AUTH_SERVICE_URL', '')
    vi.stubEnv('VITE_APP_NAME', '')
    
    await router.push('/reset')
    await router.isReady()

    const wrapper = mount(ResetView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('.text-destructive').exists()).toBe(true)
    expect(wrapper.text()).toContain('Missing VITE_AUTH_SERVICE_URL or VITE_APP_NAME')
    expect(axios.delete).not.toHaveBeenCalled()
  })

  it('shows no keys message when cleared list is empty', async () => {
    vi.stubEnv('VITE_AUTH_SERVICE_URL', 'http://localhost:8001')
    vi.stubEnv('VITE_APP_NAME', 'TestApp')
    
    // Mock successful response with no keys cleared
    axios.delete.mockResolvedValue({
      data: {
        app_name: 'TestApp',
        cleared: [],
        message: 'No keys found to clear'
      }
    })

    await router.push('/reset')
    await router.isReady()

    const wrapper = mount(ResetView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Cache cleared for')
    expect(wrapper.text()).toContain('TestApp')
    expect(wrapper.text()).toContain('No keys were present in cache')
  })
})
