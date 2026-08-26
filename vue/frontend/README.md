# Frontend App Template

A Vue 3 + Vite frontend template with built-in SSO authentication, optional RBAC, and a sidebar shell layout.  
Supports Azure AD SSO (modes 1/2) and VueLocalAuth as a local SSO drop-in replacement (mode 3).  
New pages only require three steps: add a route, add a nav entry, create a view.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Environment Variables](#environment-variables)
3. [Adding a New Page](#adding-a-new-page)
   - [Step 1 – Add a Route](#step-1--add-a-route)
   - [Step 2 – Add a Sidebar Nav Item](#step-2--add-a-sidebar-nav-item)
   - [Step 3 – Create the View Component](#step-3--create-the-view-component)
4. [Styling](#styling)
   - [Priority Order](#priority-order)
   - [0. Murata UI Design System](#0-murata-ui-design-system--use-for-all-new-ui)
   - [1. shadcn/ui Components](#1-shadcnui--component-foundation)
   - [2. DaisyUI](#2-daisyui--last-resort-only)
   - [3. Shadcn CSS Variables](#3-shadcn-css-variables--surfaces--color-tokens)
   - [4. Tailwind Utilities](#4-tailwind-utilities--layout--spacing)
   - [Quick Decision Checklist](#quick-decision-checklist)
5. [Auth Modes](#auth-modes)
6. [Project Structure](#project-structure)
7. [Do Not Modify](#do-not-modify)
8. [Before Pushing to Production](#before-pushing-to-production)

---

## Getting Started

### Prerequisites

- Node.js 18+
- npm 9+

### Install dependencies

```bash
npm install
```

### Run the development server

```bash
npm run dev
```

The app will be available at `http://localhost:5173` by default.

### Other scripts

| Command           | Description                  |
| ----------------- | ---------------------------- |
| `npm run dev`     | Start local dev server       |
| `npm run build`   | Production build to `dist/`  |
| `npm run preview` | Preview the production build |
| `npm run test`    | Run unit tests (Vitest)      |

---

## Environment Variables

Open `.env` directly and update the values for your deployment.

> All `VITE_` variables are bundled into the browser JS and are visible in DevTools.  
> Do not store secrets here.

### Variables you need to change

| Variable                        | Description                                                                        | Example                 |
| ------------------------------- | ---------------------------------------------------------------------------------- | ----------------------- |
| `VITE_AUTH_MODE`                | Auth behaviour: `0` = off (dev) · `1` = SSO only · `2` = SSO + RBAC · `3` = Local auth + RBAC | `2`          |
| `VITE_LOCAL_AUTH_URL`           | URL of VueLocalAuth service — **only required when `VITE_AUTH_MODE=3`**            | `http://localhost:8003` |
| `VITE_API_URL`                  | Full URL of the FastAPI backend **including `/api` suffix**                         | `http://163.50.34.44:8000/api` |
| `VITE_POST_LOGOUT_REDIRECT_URI` | Where the browser lands after a Microsoft logout completes (usually your app root) | `http://localhost:5173` |
| `VITE_APP_NAME`                 | App identifier — must match the RBAC API registration for this app                 | `MY_APP`                |
| `VITE_AFFILIATE_BADGE`          | Short label shown as a badge in the top bar (e.g. site/affiliate code). Leave blank to hide. | `MES` |

### Backend API URL

The frontend calls the backend directly using `VITE_API_URL` in `.env` — no nginx or reverse proxy needed.

```env
# frontend/.env
VITE_API_URL=http://localhost:8000/api       # local dev
VITE_API_URL=http://163.50.34.44:8000/api   # production server
```

The axios client uses this URL as-is — the `/api` suffix must be included.

---

### Variables managed by the platform team

These are pre-configured and should only be changed if the platform environment changes:

- `VITE_AUTH_SERVICE_URL` – URL of the VueAuthService that exchanges SSO tokens for app JWTs
- `VITE_SSO_URL` – SSO Proxy login URL (modes 1/2 only)
- `VITE_AUTH_TOKENS` – Pre-shared tokens registered with the SSO Proxy (modes 1/2 only)
- `VITE_AZURE_TENANT_ID` – Azure AD tenant ID used to build the Microsoft logout URL (modes 1/2 only)

---

## Adding a New Page

Adding a page requires three small changes. Do **not** touch `AppLayout.vue` (see [Do Not Modify](#do-not-modify)).

---

### Step 1 – Add a Route

Open `src/router/index.js` and add a child route inside the `AppLayout` parent (the route with `path: '/'`).

```js
// src/router/index.js
import MyNewView from "../views/MyNewView.vue";

const routes = [
  {
    path: "/",
    component: () => import("../components/AppLayout.vue"),
    meta: { requiresAuth: true },
    children: [
      // ... existing routes ...

      // ✅ Add your new route here
      {
        path: "my-page", // URL will be /my-page
        component: MyNewView,
        meta: {
          title: "My Page",

      // Only needed when VITE_AUTH_MODE=2 or 3 (RBAC).
          // Remove this line if the page should be visible to everyone.
          screen_id: "MY_SCREEN_ID",
        },
      },
    ],
  },
  // ... other top-level routes (unauthorized, reset) — leave as-is ...
];
```

> **RBAC note:** If `VITE_AUTH_MODE=2` or `3`, users without the `screen_id` permission are redirected to `/unauthorized`.  
> Set `screen_id` to a string that matches what is registered in the RBAC API.  
> Omit `screen_id` entirely if the page should be accessible to all authenticated users.

---

### Step 2 – Add a Sidebar Nav Item

Open `src/nav.config.js` and add an entry to the exported array.  
Import the icon you want from [`lucide-vue-next`](https://lucide.dev/icons/).

```js
// src/nav.config.js
import { HomeIcon, ShieldCheckIcon, StarIcon } from "lucide-vue-next";

export default [
  // ... existing items ...

  // ✅ Add your new nav item here
  {
    to: "/my-page", // must match the route path in router/index.js
    label: "My Page", // text shown in the sidebar
    icon: StarIcon, // Lucide icon component
    exact: false, // true = highlight on exact match only
    requiredScreen: "MY_SCREEN_ID", // set to null to always show; mirrors screen_id from the route
  },
];
```

> If the page should always appear in the sidebar regardless of RBAC, set `requiredScreen: null`.
> `requiredScreen` is enforced when `VITE_AUTH_MODE=2` or `3`.

---

### Step 3 – Create the View Component

Create a new `.vue` file in `src/views/`. The file name should match what you imported in the router.

```
src/views/MyNewView.vue
```

```vue
<!-- src/views/MyNewView.vue -->
<script setup>
import { Button } from '@/components/ui/button'
import { Card }   from '@/components/ui/card'
</script>

<template>
  <div class="p-6">
    <div class="murata">
      <h1 class="text-2xl font-semibold mb-4">My Page</h1>
      <Card>
        <p class="mu-muted">Page content goes here.</p>
        <Button variant="primary" class="mt-4">Save</Button>
      </Card>
    </div>
  </div>
</template>
```

The view renders inside the `AppLayout` shell (sidebar + topbar) automatically — no wrapper needed.

---

## Styling

This project uses **five CSS layers**. Always reach for the highest priority option first and fall down the list only when it doesn't cover your need.

### Priority Order

```
0. Murata UI Design System    → wrap in <div class="murata">, use shadcn components with Murata variants
1. shadcn/ui Vue components   → src/components/ui/   (app shell, sidebar, tooltip, sheet)
2. DaisyUI component classes  → last resort only, if shadcn + Murata CSS cannot cover the need
3. Shadcn CSS variables       → bg-card, text-muted   (surfaces and color tokens)
4. Tailwind utilities         → flex, p-4, text-sm    (layout, spacing, sizing)
```

> **See it live:** Navigate to `/examples` in the running app for a visual reference of every pattern below.

---

### 0. Murata UI Design System — Use for All New UI

**Visual reference:** [`docs/murata-ui-components.html`](./docs/murata-ui-components.html) — open in a browser to browse the full component library.

**CSS source:** `src/murata-ui.css` — imported automatically via `style.css`.

**Font:** All three IBM Plex families are self-hosted from `public/fonts/` via `@font-face` in `murata-ui.css` — no external font requests.

#### How to use

Wrap any UI section in `<div class="murata">`. Inside the wrapper, shadcn components inherit Murata colors, fonts, and radius automatically via CSS overrides in `murata-ui.css`.

```vue
<script setup>
import { Button } from '@/components/ui/button'
import { Card }   from '@/components/ui/card'
</script>

<template>
  <div class="murata">
    <Button variant="primary">Save</Button>
    <Button variant="secondary">Cancel</Button>
    <Card>Content goes here.</Card>
  </div>
</template>
```

Utility layout classes (`mu-label`, `mu-grid`, `mu-row`, `mu-muted`, etc.) and non-shadcn patterns (`mu-table`, `mu-stat`, `mu-progress`, `mu-skel`) are still applied as raw CSS classes inside the wrapper. The reference HTML uses unprefixed class names — for these utilities, add the `mu-` prefix when translating.

#### Tokens

Murata tokens are CSS variables scoped to `.murata`. They automatically switch in dark mode (`.dark .murata`).

| Token | Light | Dark | Use for |
|---|---|---|---|
| `--primary` | `#1E3A8A` | `#4C7DF0` | Brand blue — buttons, links, focus rings |
| `--card` | `#FFFFFF` | `#141922` | Card / panel backgrounds |
| `--paper` | `#EEF1F4` | `#0C0F14` | Page background |
| `--ink` | `#11151B` | `#EAEEF3` | Primary text |
| `--muted` | `#6B7480` | `#7C8694` | Secondary / placeholder text |
| `--line` | `#DCE1E7` | `#222A35` | Borders and dividers |
| `--ok` | `#157A50` | `#3DBB84` | Success green |
| `--warn` | `#9A6B12` | `#D9A441` | Warning amber |
| `--danger` | `#C01B2B` | `#F06A77` | Error red |
| `--teal` | `#0E8E9A` | `#27C2CE` | Accent teal |
| `--sans` | IBM Plex Sans | ← | Body text font |
| `--cond` | IBM Plex Sans Condensed | ← | Large stat numbers |
| `--mono` | IBM Plex Mono | ← | Labels, badges, code |

#### shadcn components with Murata theme

shadcn components are the foundation — Murata CSS themes them inside the `.murata` wrapper via `[data-slot]` attribute selectors in `murata-ui.css`. Two thin wrapper components (`MuInput`, `MuAlert`) add field-label/error and auto-icon patterns on top of shadcn primitives.

| Component | Import | Props / Notes |
|---|---|---|
| `Button` | `@/components/ui/button` | `variant` (primary\|secondary\|ghost\|danger), `size` (sm\|default\|lg\|icon) |
| `Badge` | `@/components/ui/badge` | `variant` (ok\|warn\|danger\|info\|teal\|neutral) |
| `Card` | `@/components/ui/card` | Slot wrapper — also exports `CardHeader`, `CardContent`, etc. |
| `Alert` | `@/components/ui/alert` | Base shadcn alert — use `MuAlert` for the standard Murata pattern |
| `MuInput` | `@/components/ui/mu-input` | Wraps shadcn `Input` with label, error hint, required indicator |
| `MuAlert` | `@/components/ui/mu-alert` | Wraps shadcn `Alert` with auto-icon per variant (info\|ok\|warn\|err) |
| `MuStat` | `@/components/ui/mu-stat` | Stat widget (no shadcn equivalent) — `value`, `label`, `delta` |

```vue
<script setup>
import { Button }  from '@/components/ui/button'
import { Badge }   from '@/components/ui/badge'
import { Card }    from '@/components/ui/card'
import { MuInput } from '@/components/ui/mu-input'
import { MuAlert } from '@/components/ui/mu-alert'
import { MuStat }  from '@/components/ui/mu-stat'
</script>

<template>
  <div class="murata">
    <Button variant="primary" @click="save">Save</Button>
    <Badge variant="ok">Active</Badge>
    <MuInput v-model="name" label="Name" placeholder="Enter name…" />
    <MuInput v-model="field" label="Required" :required="true" error="This field is required." />
    <MuAlert variant="warn" title="Warning">Approval needed before publishing.</MuAlert>
    <Card><MuStat value="1,284" label="Total Users" delta="+12 this month" /></Card>
  </div>
</template>
```

For the full class reference and more advanced patterns see `docs/murata-ui-components.html`.

---

### 1. shadcn/ui — Component Foundation

All page-level components are **shadcn components themed by Murata CSS**. shadcn provides the accessible primitives; `murata-ui.css` overrides their visual styles inside `.murata` wrappers.

**Installed components:**

| Component                     | Import path                 | Use for                                        |
| ----------------------------- | --------------------------- | ---------------------------------------------- |
| `Button`                      | `@/components/ui/button`    | All buttons — use Murata variants inside `.murata` |
| `Badge`                       | `@/components/ui/badge`     | Status badges — use Murata variants inside `.murata` |
| `Card`                        | `@/components/ui/card`      | Panel / card wrapper                           |
| `Alert`                       | `@/components/ui/alert`     | Base alert (use `MuAlert` wrapper for standard pattern) |
| `Input`                       | `@/components/ui/input`     | Text input (use `MuInput` wrapper for label/error) |
| `Table` + family              | `@/components/ui/table`     | Data tables (or use raw `mu-table` CSS)        |
| `Tooltip` / `TooltipProvider` | `@/components/ui/tooltip`   | Hover tooltips                                 |
| `Sheet`                       | `@/components/ui/sheet`     | Slide-in drawer                                |
| `Sidebar` + family            | `@/components/ui/sidebar`   | App sidebar (AppLayout)                        |
| `Separator`                   | `@/components/ui/separator` | Dividers                                       |
| `Skeleton`                    | `@/components/ui/skeleton`  | Loading shimmer (or use `mu-skel` CSS class)   |

**Adding more shadcn components:**

```bash
npx shadcn-vue@latest add dialog
npx shadcn-vue@latest add select
npx shadcn-vue@latest add popover
```

Each command drops `.vue` files into `src/components/ui/` — yours to own and edit.  
Browse the full list at [shadcn-vue.com/docs/components](https://shadcn-vue.com/docs/components).

#### Rule: theming new shadcn components for Murata

When a new shadcn component will be used inside `<div class="murata">`, apply the Murata theme by following these steps:

> **Reference implementation to copy from:** `src/components/ui/badge/` is the canonical example — `index.js` shows how Murata variants are added to `cva()`, `Badge.vue` shows where `:data-variant="variant"` goes, and the `## shadcn BADGE` block in `murata-ui.css` shows the CSS selector pattern. Follow this exactly for any new component.

1. **Check `data-slot`** — open the generated `.vue` file. Every shadcn component has `data-slot="<name>"` on its root element (e.g. `data-slot="dialog"`, `data-slot="select"`).

2. **Add `data-variant` if the component has variants** — if the component accepts a `variant` prop and you want Murata-specific variant names, add `:data-variant="variant"` to the root element (same way `Badge.vue` and `Alert.vue` do it), then add the variant names to the `cva()` call in `index.js` with empty string values — the CSS handles the actual styling.

3. **Add CSS overrides to `murata-ui.css`** — target the component using its `data-slot` and optionally `data-variant`. Add the block under the correct section comment:

```css
/* Apply Murata font, color, radius to the new component */
.murata [data-slot="dialog-content"] {
  font-family: var(--sans);
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--r);
  box-shadow: var(--shadow-lg);
}

/* Style a Murata-specific variant */
.murata [data-slot="select-item"][data-variant="danger"] {
  color: var(--danger);
}
```

4. **Reference the visual design** — open `docs/murata-ui-components.html` in a browser to see what the target design should look like. Match colors exactly using the Murata tokens below — never hardcode hex values.

5. **For wrapper components** (label + input + error, or auto-icon + content) — follow the pattern in `src/components/ui/mu-input/MuInput.vue`. It imports the shadcn primitive, wraps it in a layout div, and lets `murata-ui.css` handle all visual styling via `[data-slot]`.

**Key Murata tokens available inside `.murata`:**

```
--primary / --primary-press / --primary-tint   Blue brand
--ok / --ok-tint                                Green success
--warn / --warn-tint                            Amber warning
--danger / --danger-tint                        Red error
--teal / --teal-tint                            Teal accent
--card / --card-2 / --paper                     Surfaces
--ink / --ink-2 / --muted                       Text colours
--line / --line-strong                          Borders
--sans / --cond / --mono                        Font families
--r / --r-sm                                    Border radii (12px / 8px)
--shadow / --shadow-lg                          Box shadows
```

---

### 2. DaisyUI — Last Resort Only

Use DaisyUI **only** when a UI need cannot be met with Murata components/classes **and** a shadcn component with Murata CSS applied. The only common use-case is the loading spinner.

```html
<!-- Loading spinner (only DaisyUI use case) -->
<span class="loading loading-spinner loading-sm"></span>
```

#### ⚠️ Never use DaisyUI surface/base tokens

These conflict with the shadcn color system and render incorrectly:

```html
<!-- ❌ Don't use -->
bg-base-100 bg-base-200 bg-base-300 text-base-content card card-body

<!-- ✅ Use shadcn CSS vars instead -->
bg-background bg-card text-foreground text-card-foreground
```

---

### 3. Shadcn CSS Variables — Surfaces & Color Tokens

CSS custom properties defined in `src/style.css`. Use these on structural elements (wrappers, cards, borders).

**Key tokens:**

```
Backgrounds:   bg-background · bg-card · bg-muted · bg-sidebar · bg-primary · bg-destructive
Text:          text-foreground · text-card-foreground · text-muted-foreground · text-destructive
Borders:       border-border · border-input
Ring/Focus:    ring-ring (used automatically by shadcn components)
Chart colors:  bg-chart-1 … bg-chart-5  (theme-aware, use for status dots / tags / data-vis)
```

```html
<!-- Page wrapper -->
<div class="min-h-screen bg-background text-foreground">
  <!-- Card panel -->
  <div class="rounded-lg border border-border bg-card text-card-foreground shadow-md border-t-[3px] border-t-primary p-6">
    <!-- Muted block -->
    <div class="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
      <!-- Error text -->
      <p class="text-sm text-destructive">{{ errorMessage }}</p>
    </div>
  </div>
</div>
```

---

### 4. Tailwind Utilities — Layout & Spacing

Standard Tailwind for anything structural: spacing, flex, grid, typography scale, transitions.

```html
<div class="flex items-center gap-3 px-4 py-2">
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
    <h1 class="text-2xl font-semibold leading-tight">Page Title</h1>
    <p class="text-sm text-muted-foreground">Description</p>
    <div class="transition-colors duration-200 hover:bg-accent"></div>
  </div>
</div>
```

---

### Quick Decision Checklist

```
Button?               → <Button variant="primary|secondary|ghost|danger">
                        from @/components/ui/button   (inside <div class="murata">)

Text input?           → <MuInput v-model label error required>
                        from @/components/ui/mu-input

Status badge?         → <Badge variant="ok|warn|danger|info|teal|neutral">
                        from @/components/ui/badge

Feedback message?     → <MuAlert variant="info|ok|warn|err" title="…">
                        from @/components/ui/mu-alert

Card / panel?         → <Card> from @/components/ui/card

Stat widget?          → <MuStat value label delta> from @/components/ui/mu-stat

Data table?           → raw <table class="mu-table"> (CSS in murata-ui.css)

Progress bar?         → raw <div class="mu-progress"><span class="mu-progress-fill">

Skeleton loader?      → raw <div class="mu-skel">  OR  <Skeleton> from shadcn

2–3 column grid?      → class="mu-grid mu-two"  /  class="mu-grid mu-three"

Tooltip?              → <Tooltip> family from @/components/ui/tooltip
Slide-in panel?       → <Sheet> from @/components/ui/sheet
Divider?              → <Separator> from @/components/ui/separator

DaisyUI spinner only: → <span class="loading loading-spinner loading-sm">
                        ❌ Do NOT use bg-base-*, card-body, or DaisyUI btn/badge/alert

Page background / card tokens?
                      → Shadcn CSS vars (bg-background, bg-card, border-border…)

Layout, spacing, typography, transitions?
                      → Tailwind utilities (flex, p-4, text-sm, gap-3…)
```

---

## Auth Modes

Set `VITE_AUTH_MODE` in your `.env`:

| Value | Mode              | Behaviour                                                                               |
| ----- | ----------------- | --------------------------------------------------------------------------------------- |
| `0`   | Off               | No auth. All routes open. Use only during early local development.                      |
| `1`   | SSO               | JWT required. Users are redirected to SSO on missing/expired token.                     |
| `2`   | SSO + RBAC        | JWT required **and** per-screen role checks via the RBAC API.                           |
| `3`   | Local auth + RBAC | Same as mode 2 but uses **VueLocalAuth** instead of Azure AD SSO. Set `VITE_LOCAL_AUTH_URL` to the VueLocalAuth service. Requires no SSO Proxy or Azure AD. |

### Using RBAC data in components

`useRbac()` exposes the following when `VITE_AUTH_MODE=2` or `3`:

| Property / Method       | Description                                                                 |
| ----------------------- | --------------------------------------------------------------------------- |
| `can(screen_id)`        | Returns `true` if the user has access to the given screen.                  |
| `rbacLoaded`            | `true` once the `/rbac/me` fetch has completed successfully.                |
| `rbacError`             | `true` if the user received a 403 (no RBAC access at all).                  |
| `accessCodes`           | Readonly array of the user's access code records (see shape below).         |

**`accessCodes` entry shape:**

```js
{
  rto0006:  string,
  rto0011_01: string,
  rto0011_02: string,
  msc14036: string,
  rto0011_03: string, 
}
```

**Example:**

```js
import { useRbac } from '@/composables/useRbac.js'

const { can, accessCodes } = useRbac()
// accessCodes is populated after app boot — no extra fetch needed
```

---

## Project Structure

```
frontend/
├── docs/
│   └── murata-ui-components.html  📖 Visual component reference — open in browser
├── public/
│   └── fonts/            Self-hosted IBM Plex Sans / Condensed / Mono font files
├── src/
│   ├── api/              Axios instances and API helpers
│   ├── auth.js           JWT storage, expiry checks, SSO redirect logic
│   ├── components/
│   │   ├── AppLayout.vue ⛔ Do not modify (see below)
│   │   └── ui/
│   │       ├── button/      shadcn Button — Murata variants: primary|secondary|ghost|danger
│   │       ├── badge/       shadcn Badge  — Murata variants: ok|warn|danger|info|teal|neutral
│   │       ├── card/        shadcn Card   — themed with Murata card style
│   │       ├── alert/       shadcn Alert  — Murata variants: info|ok|warn|err
│   │       ├── input/       shadcn Input  — themed with Murata input style
│   │       ├── mu-input/    MuInput — wraps shadcn Input with label + error hint
│   │       ├── mu-alert/    MuAlert — wraps shadcn Alert with auto-icon per variant
│   │       ├── mu-stat/     MuStat  — stat widget (no shadcn equivalent)
│   │       └── ...          other shadcn shell components (tooltip, sheet, sidebar…)
│   ├── composables/      Vue composables (e.g. useRbac)
│   ├── lib/              Utility functions
│   ├── murata-ui.css     Murata Design System CSS (tokens + shadcn [data-slot] overrides + mu-table/stat/progress/skel utilities)
│   ├── nav.config.js     ✅ Edit to update sidebar navigation
│   ├── router/
│   │   └── index.js      ✅ Edit to add/remove routes
│   ├── views/            ✅ Add new page components here
│   ├── App.vue           Root component — do not modify
│   ├── main.js           App entry point — do not modify
│   └── style.css         Global styles (imports murata-ui.css)
├── tests/                Unit tests (Vitest + Vue Test Utils)
├── .env                  Environment variable
├── vite.config.js        Vite config
└── package.json
```

---

## Do Not Modify

| File / Component      | Reason                                                                                     |
| --------------------- | ------------------------------------------------------------------------------------------ |
| `AppLayout.vue`       | Provides the sidebar shell, topbar, and auth integration. Changing it can break all pages. |
| `App.vue`             | Root component — router-view wiring and global providers live here.                        |
| `main.js`             | App bootstrap. Modify only if adding a global plugin.                                      |
| `auth.js`             | Auth token handling. Changes here can break SSO / local auth for the entire app.           |
| `composables/useRbac` | RBAC data layer used by both the router guard and `nav.config.js` filtering.               |

---

## Before Pushing to Production

Follow these steps in order before committing and pushing to Git.

### Step 1 – Build for production

```bash
npm run build
```

This compiles and bundles the app into the `dist/` folder.

### Step 2 – Test the production build locally

Serve the `dist/` folder using `serve` and verify everything works as expected before uploading.

```bash
node vendor/node_modules/serve/build/main.js -s dist -l 5173
```

> `-s` enables single-page app mode (redirects all routes to `index.html`).  
> `-l 5173` sets the local port — change the number if 5173 is already in use.

Open `http://localhost:5173` and smoke-test the app.

### Step 3 – Push to Git

Once the local production build looks correct, commit and push the project:

```bash
git add .
git commit -m "your message"
git push
```
