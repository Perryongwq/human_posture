import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import UnauthorizedView from '../src/views/UnauthorizedView.vue'

describe('UnauthorizedView', () => {
  beforeEach(() => {
    vi.unstubAllEnvs()
  })

  it('renders access-denied message', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/unauthorized', component: UnauthorizedView },
      ],
    })
    await router.push('/unauthorized')
    await router.isReady()

    const wrapper = mount(UnauthorizedView, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('Access Denied')
    expect(wrapper.text()).toContain('do not have permission to access')
  })

  it('displays screen name from query param', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/unauthorized', component: UnauthorizedView },
      ],
    })
    await router.push('/unauthorized?screen=Admin%20Panel')
    await router.isReady()

    const wrapper = mount(UnauthorizedView, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('Admin Panel')
  })

  it('contains Go Home link to /', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/unauthorized', component: UnauthorizedView },
      ],
    })
    await router.push('/unauthorized')
    await router.isReady()

    const wrapper = mount(UnauthorizedView, { global: { plugins: [router] } })
    expect(wrapper.find('a[href="/"]').exists()).toBe(true)
  })
})
