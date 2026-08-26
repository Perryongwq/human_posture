import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

// Mock useAuth to return controlled currentUser and logout
const mockLogout = vi.fn()
vi.mock('../src/composables/useAuth.js', () => ({
  useAuth: () => ({
    currentUser: ref({ username: 'testuser', payroll: 'P12345', deptcode: 'ENG' }),
    logout: mockLogout,
  }),
}))

// Helper: create a test router with memory history
function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>Home</div>' } },
      { path: '/protected', component: { template: '<div>Protected</div>' } },
    ],
  })
}

describe('HomeView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders username, payroll, and deptcode from currentUser', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()

    const HomeView = (await import('../src/views/HomeView.vue')).default
    const wrapper = mount(HomeView, { global: { plugins: [router] } })

    expect(wrapper.text()).toContain('testuser')
    expect(wrapper.text()).toContain('P12345')
    expect(wrapper.text()).toContain('ENG')
  })
})
