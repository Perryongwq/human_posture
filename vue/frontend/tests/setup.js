// frontend/tests/setup.js
// Global test setup — runs before each test file
import { vi, beforeEach, afterEach } from 'vitest'

// Stub lucide-vue-next globally — icons are irrelevant in unit tests and the
// package is large enough to cause vitest fork-worker startup timeouts when
// multiple workers initialise in parallel.
vi.mock('lucide-vue-next', () => ({
  HomeIcon:            { template: '<svg data-testid="icon-home" />' },
  HandIcon:            { template: '<svg data-testid="icon-hand" />' },
  ListOrderedIcon:     { template: '<svg data-testid="icon-list-ordered" />' },
  MenuIcon:            { template: '<svg data-testid="icon-menu" />' },
  LogOutIcon:          { template: '<svg data-testid="icon-logout" />' },
  ChevronsUpDownIcon:  { template: '<svg data-testid="icon-chevrons-updown" />' },
  MoonIcon:            { template: '<svg data-testid="icon-moon" />' },
  SunIcon:             { template: '<svg data-testid="icon-sun" />' },
}))

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  vi.unstubAllEnvs()
})

afterEach(() => {
  vi.restoreAllMocks()
})
