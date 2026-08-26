import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'

// Mock vue-router (memory history for jsdom)
vi.mock('vue-router', async (importOriginal) => {
  const mod = await importOriginal()
  return {
    ...mod,
    createWebHistory: () => mod.createMemoryHistory(),
    useRoute: () => ({ meta: { title: 'Test Page' } }),
  }
})

// Mock useRbac composable
const mockCan = vi.fn(() => false)
vi.mock('../src/composables/useRbac.js', () => ({
  useRbac: () => ({ can: mockCan, rbacLoaded: { value: false }, rbacError: { value: false }, fetchRbac: vi.fn() }),
}))

// Mock nav.config.js with a fixed fixture (one open item, one RBAC-gated
// item) — decouples the RBAC-filtering tests below from whatever pages
// happen to exist in the real nav today (none currently set requiredScreen).
vi.mock('../src/nav.config.js', () => ({
  default: [
    { to: '/', label: 'Home', icon: { template: '<svg />' }, exact: true, requiredScreen: null },
    { to: '/protected', label: 'Protected', icon: { template: '<svg />' }, exact: false, requiredScreen: 'protected' },
  ],
}))

// Mock useAuth composable
const mockLogout = vi.fn()
const mockCurrentUser = { username: 'testuser', payroll: 'P001', deptcode: 'IT' }
vi.mock('../src/composables/useAuth.js', () => ({
  useAuth: () => ({ currentUser: { value: mockCurrentUser }, logout: mockLogout }),
}))

// RouterView stub (required for nested route testing)
const RouterViewStub = { template: '<div data-testid="router-view-stub">RouterView</div>' }
const RouterLinkStub = { template: '<a><slot /></a>', props: ['to'] }

// Tests grouped by requirement
describe('AppLayout.vue', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    mockCan.mockReturnValue(false)
    vi.unstubAllEnvs()
    vi.stubEnv('VITE_AUTH_MODE', '1')  // default: mode 1 — all nav items visible, no RBAC filter
    vi.resetModules()                   // fresh module per test (authMode is module-level constant)
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  // LAYOUT-02: Shared AppLayout wraps authenticated pages via nested routes
  describe('LAYOUT-02: nested RouterView', () => {
    it('renders RouterView for nested child routes', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.find('[data-testid="router-view-stub"]').exists()).toBe(true)
    })
  })

  // SIDE-01: Logo at top of sidebar
  describe('SIDE-01: logo display', () => {
    it('displays logo img with alt="Company Logo" in sidebar', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const logo = wrapper.find('img[alt="Company Logo"]')
      expect(logo.exists()).toBe(true)
    })
  })

  // SIDE-02: Nav items with icons
  describe('SIDE-02: navigation items', () => {
    it('renders nav link to "/" with Home label', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.text()).toContain('Home')
    })

    it('renders nav link to "/protected" with Protected label (mocked nav.config.js fixture)', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.text()).toContain('Protected')
    })

    it('nav items have SVG icons (w-5 h-5)', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const icons = wrapper.findAll('nav svg.w-5.h-5')
      expect(icons.length).toBeGreaterThanOrEqual(2)
    })
  })

  // SIDE-03: User profile (avatar, username, deptcode)
  describe('SIDE-03: user profile', () => {
    it('displays avatar with user initials', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.text()).toContain('TE')  // testuser → TE
    })

    it('displays username from currentUser', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.text()).toContain('testuser')
    })

    it('displays deptcode from currentUser', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.text()).toContain('IT')
    })
  })

  // SIDE-04: Collapsible sidebar
  describe('SIDE-04: sidebar collapse toggle', () => {
    it('sidebar starts with w-64 class when expanded (default)', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const sidebar = wrapper.find('aside')
      expect(sidebar.classes()).toContain('w-64')
    })

    it('clicking toggle changes sidebar to w-16 class', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const toggle = wrapper.find('header button[aria-label="Toggle sidebar"]')
      await toggle.trigger('click')
      const sidebar = wrapper.find('aside')
      expect(sidebar.classes()).toContain('w-16')
    })
  })

  // SIDE-05: Collapse state persists in localStorage
  describe('SIDE-05: localStorage persistence', () => {
    it('reads sidebar_collapsed from localStorage on mount', async () => {
      localStorage.setItem('sidebar_collapsed', 'true')
      vi.resetModules()
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const sidebar = wrapper.find('aside')
      expect(sidebar.classes()).toContain('w-16')
    })

    it('writes sidebar_collapsed to localStorage on toggle', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const toggle = wrapper.find('header button[aria-label="Toggle sidebar"]')
      await toggle.trigger('click')
      expect(localStorage.getItem('sidebar_collapsed')).toBe('true')
    })
  })

  // HEAD-01: Toggle button in header
  describe('HEAD-01: header toggle button', () => {
    it('header contains button[aria-label="Toggle sidebar"]', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const headerToggle = wrapper.find('header button[aria-label="Toggle sidebar"]')
      expect(headerToggle.exists()).toBe(true)
    })

    it('toggle button has aria-label="Toggle sidebar"', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const toggle = wrapper.find('header button[aria-label="Toggle sidebar"]')
      expect(toggle.attributes('aria-label')).toBe('Toggle sidebar')
    })
  })

  // HEAD-02: Page title from route meta.title
  describe('HEAD-02: page title in header', () => {
    it('header displays route.meta.title text', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const header = wrapper.find('header')
      expect(header.text()).toContain('Test Page')
    })
  })

  // SIDE-03 extension: user profile hidden in AUTH_MODE=0
  describe('SIDE-03: user profile visibility by AUTH_MODE', () => {
    it('hides user profile section when VITE_AUTH_MODE=0', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '0')
      vi.resetModules()
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.find('[aria-label="User profile"]').exists()).toBe(false)
    })

    it('shows user profile section when VITE_AUTH_MODE is not 0', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      vi.resetModules()
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.find('[aria-label="User profile"]').exists()).toBe(true)
    })
  })

  // SIDE-03 extension: profile popover
  describe('SIDE-03: user profile popover', () => {
    it('profile button has aria-haspopup="true"', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const btn = wrapper.find('[aria-label="User profile"]')
      expect(btn.attributes('aria-haspopup')).toBe('true')
    })

    it('clicking profile button opens the popover (aria-expanded becomes true)', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const btn = wrapper.find('[aria-label="User profile"]')
      expect(btn.attributes('aria-expanded')).toBe('false')
      await btn.trigger('click')
      expect(btn.attributes('aria-expanded')).toBe('true')
    })

    it('clicking profile button a second time closes the popover', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      const btn = wrapper.find('[aria-label="User profile"]')
      await btn.trigger('click')
      await btn.trigger('click')
      expect(btn.attributes('aria-expanded')).toBe('false')
    })

    it('logout button calls logout() from useAuth', async () => {
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
        attachTo: document.body,
      })
      await wrapper.find('[aria-label="User profile"]').trigger('click')
      await wrapper.find('[aria-label="Log out"]').trigger('click')
      expect(mockLogout).toHaveBeenCalledOnce()
      wrapper.unmount()
    })
  })

  // SIDE-02 extension: RBAC-filtered nav items
  describe('SIDE-02: RBAC nav filtering', () => {
    it('AUTH_MODE != 2: shows all nav items regardless of can()', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '1')
      mockCan.mockReturnValue(false)
      vi.resetModules()
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.text()).toContain('Home')
      expect(wrapper.text()).toContain('Protected')
    })

    it('AUTH_MODE=2: hides items where can() returns false', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '2')
      mockCan.mockReturnValue(false)
      vi.resetModules()
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.text()).toContain('Home')          // requiredScreen: null → always shown
      expect(wrapper.text()).not.toContain('Protected') // requiredScreen: 'protected' → hidden
    })

    it('AUTH_MODE=2: shows items where can() returns true', async () => {
      vi.stubEnv('VITE_AUTH_MODE', '2')
      mockCan.mockReturnValue(true)
      vi.resetModules()
      const AppLayout = (await import('../src/components/AppLayout.vue')).default
      const wrapper = mount(AppLayout, {
        global: { stubs: { RouterView: RouterViewStub, RouterLink: RouterLinkStub, Teleport: true } },
      })
      expect(wrapper.text()).toContain('Home')
      expect(wrapper.text()).toContain('Protected')
    })
  })
})
