// frontend/src/nav.config.js
// ─────────────────────────────────────────────────────────────────────────────
// Sidebar navigation items — edit this file to add/remove pages.
// AppLayout.vue reads this config and handles rendering automatically.
//
// Fields:
//   to              Vue Router path (must match a route in router/index.js)
//   label           Display text shown in the sidebar
//   icon            Lucide icon component (import from 'lucide-vue-next')
//   exact           true  → highlight only on exact route match
//                   false → highlight on any route that starts with `to`
//   requiredScreen  RBAC screen_id required to see this item.
//                   Enforced when VITE_AUTH_MODE=2 or 3.
//                   Set to null to always show the item regardless of RBAC.
// ─────────────────────────────────────────────────────────────────────────────
import { HomeIcon, HandIcon } from 'lucide-vue-next'

export default [
  {
    to:             '/',
    label:          'Home',
    icon:           HomeIcon,
    exact:          true,
    requiredScreen: null,
  },
  {
    to:             '/posture',
    label:          'Pick & Place',
    icon:           HandIcon,
    exact:          false,
    requiredScreen: null,
  },
]
