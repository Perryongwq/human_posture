# App Changelog

> **Purpose:** Tracks every file-level change made to this template.
> After pulling this template, to update existing codebase, use this log to know exactly which files to **add**, **replace**, or **review** — rather than doing a blind diff.

---

## How to Use This File

| Symbol    | Meaning                                                            |
| --------- | ------------------------------------------------------------------ |
| ➕ ADD    | New file — safe to copy directly into your project                 |
| ✏️ MODIFY | Existing file changed — review the diff and merge carefully        |
| 🗑️ DELETE | File removed from template — consider removing from your project   |
| ⚙️ CONFIG | Config/build file — changes may affect your build pipeline or deps |

**When pulling a new version of this template:**

1. Check the entries since your last sync version.
2. For each `➕ ADD` — copy the file into your project.
3. For each `✏️ MODIFY` — compare against your local copy and merge changes.
4. For each `⚙️ CONFIG` — review carefully before applying (may affect deps or tooling).
5. Update your local sync version marker.

---

## Version History

---

### v1.2.0 — 01-07-2026

> **Murata UI Design System integration**
>
> Introduces the Murata Data Platform visual design system as the primary UI layer.
> shadcn components are kept as the accessible primitives but are now themed by Murata tokens
> via `[data-slot]` CSS attribute selectors inside a `.murata` wrapper class.
> IBM Plex Sans / Condensed / Mono fonts are self-hosted from `public/fonts/`.
> Two thin wrapper components (`MuInput`, `MuAlert`) add field-label/error and auto-icon
> convenience on top of shadcn primitives. A stat widget (`MuStat`) covers a pattern
> shadcn does not provide. Raw CSS classes (`mu-table`, `mu-progress`, `mu-skel`, etc.)
> cover remaining patterns without shadcn equivalents.

| Change     | File                                          | Notes                                                                                                                                                           |
| ---------- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ➕ ADD     | `docs/murata-ui-components.html`              | Self-contained visual reference for the full Murata component library. Open in a browser to see design targets for every component and token.                   |
| ➕ ADD     | `public/fonts/IBMPlexSans-*.woff2` (×4)       | Self-hosted IBM Plex Sans at weights 400/500/600/700 (woff2).                                                                                                   |
| ➕ ADD     | `public/fonts/IBMPlexSansCondensed-*.ttf` (×3) | Self-hosted IBM Plex Sans Condensed at weights 500/600/700 (ttf).                                                                                              |
| ➕ ADD     | `public/fonts/IBMPlexMono-*.ttf` (×3)         | Self-hosted IBM Plex Mono at weights 400/500/600 (ttf).                                                                                                         |
| ➕ ADD     | `src/murata-ui.css`                           | Murata Design System CSS. Contains: `@font-face` declarations, design tokens in `.murata {}` / `.dark .murata {}`, shadcn `[data-slot]` theme overrides for Button/Badge/Alert/Card/Input, and utility CSS classes for table, stat, progress, skeleton, grid, typography helpers. |
| ➕ ADD     | `src/components/ui/badge/`                    | shadcn Badge — installed via `npx shadcn-vue@latest add badge`. Extended `index.js` with Murata variants (`ok`, `warn`, `danger`, `info`, `teal`, `neutral`). `Badge.vue` patched to emit `:data-variant="variant"` for CSS targeting. |
| ➕ ADD     | `src/components/ui/alert/`                    | shadcn Alert — installed via `npx shadcn-vue@latest add alert`. Extended `index.js` with Murata variants (`info`, `ok`, `warn`, `err`). `Alert.vue` patched to emit `:data-variant="variant"`. |
| ➕ ADD     | `src/components/ui/card/`                     | shadcn Card — installed via `npx shadcn-vue@latest add card`. Themed via `murata-ui.css` `[data-slot="card"]` overrides (no variant extension needed).          |
| ➕ ADD     | `src/components/ui/mu-input/`                 | `MuInput` — thin wrapper over shadcn `Input`. Adds label, required indicator, and error hint. All visual styling handled by `murata-ui.css` via `[data-slot="input"]`. |
| ➕ ADD     | `src/components/ui/mu-alert/`                 | `MuAlert` — thin wrapper over shadcn `Alert`. Auto-injects the correct SVG icon per variant (`info`/`ok`/`warn`/`err`) and renders title inline before slot content. |
| ➕ ADD     | `src/components/ui/mu-stat/`                  | `MuStat` — custom stat/KPI widget (no shadcn equivalent). Props: `value`, `label`, `delta`. Auto-detects positive/negative delta for colour. Uses `mu-stat-*` CSS classes. |
| ✏️ MODIFY  | `src/style.css`                               | Added `@import './murata-ui.css'` to load Murata tokens and component overrides globally.                                                                        |
| ✏️ MODIFY  | `src/components/ui/button/index.js`           | Added Murata variants to `buttonVariants` CVA: `primary`, `secondary`, `ghost`, `danger`. These carry minimal CVA class strings — actual styling is applied by `murata-ui.css` via `[data-slot="button"][data-variant="*"]` selectors inside `.murata`. Existing shadcn variants (`default`, `destructive`, `outline`, `link`) retained for AppLayout shell. |
| ✏️ MODIFY  | `src/views/ExamplesView.vue`                  | Rewritten to showcase all Murata-themed components: Button, Badge, MuInput, MuAlert, Card/MuStat, mu-table, mu-progress, mu-skel. Imports from shadcn paths (`button`, `badge`, `card`) and mu-* wrappers. |
| ✏️ MODIFY  | `README.md`                                   | Major update: added Murata system section (tokens table, component table, import example), added 5-step rule for theming new shadcn components (with Badge as canonical reference), updated Step 3 view template, updated Quick Decision Checklist, updated Project Structure tree. Removed outdated shadcn-only Button/Input/Table/Card guidance. |

**Migration notes for existing users:**

1. **`npm install`** — Run after pulling to pick up the new shadcn Badge/Alert/Card packages added to `package.json`.
2. **Copy fonts** — Copy all files from `public/fonts/` into your project's `public/fonts/`. Without these, IBM Plex Sans will not load (the system falls back to `system-ui`).
3. **Copy `docs/murata-ui-components.html`** — Place in `frontend/docs/`. This is the visual reference used by the LLM and developers.
4. **`src/murata-ui.css`** — Copy as a new file. If you have custom styles that used the old `mu-btn`, `mu-badge`, `mu-alert`, `mu-card`, `mu-input` class names, migrate them to use the shadcn components with Murata variants instead (see README).
5. **`src/style.css`** — Add `@import './murata-ui.css';` after the Google Fonts import and before `@import "tailwindcss"`.
6. **`src/components/ui/button/index.js`** — Replace or merge. Add the four Murata variants (`primary`, `secondary`, `ghost`, `danger`) to the `variant` map in `buttonVariants`. Do not remove existing shadcn variants.
7. **New shadcn components (`badge/`, `alert/`, `card/`)** — Run `npx shadcn-vue@latest add badge alert card`, then apply the `index.js` CVA extensions and `.vue` `data-variant` patches as shown in the modified files.
8. **New wrapper/custom components** — Copy `src/components/ui/mu-input/`, `mu-alert/`, and `mu-stat/` folders directly into your project.
9. **`src/views/ExamplesView.vue`** — Replace to see the updated showcase. If you have added your own sections, merge them back in.
10. **Wrap page content** — Any new view or component using Murata-themed shadcn components must be inside `<div class="murata">`. See README Step 3 for the standard view template.

---

### v1.1.2 — 02-07-2026

> **Enhancement: Pass app name to VueLocalAuth on login redirect (Mode 3)**
>
> When `VITE_AUTH_MODE=3`, the login redirect now includes the app's identifier as an `app` query parameter so VueLocalAuth knows which application is initiating the login.

| Change    | File                          | Notes                                                                                                                                                                      |
| --------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ✏️ MODIFY | `src/auth.js`                 | Login redirect to `VITE_LOCAL_AUTH_URL` now appends `&app=<VITE_APP_NAME>` (URL-encoded). No change to modes 1/2. |
| ✏️ MODIFY | `src/composables/useAuth.js`  | Logout redirect to VueLocalAuth login page now also appends `&app=<VITE_APP_NAME>` (URL-encoded), consistent with the login redirect. |

**Migration notes for existing users:**

1. **No breaking changes** — modes 0, 1, and 2 are completely unchanged.
2. **Mode 3 only** — both files must be updated together so both redirect paths (unauthenticated guard and logout) send the `app` param.
3. **No new env vars** — `VITE_APP_NAME` is already required by the template; no additions to `.env` are needed.

---

### v1.1.1 — 16-06-2026

> **Enhancement: SSO login method detection for Mode 3 logout**
>
> When `VITE_AUTH_MODE=3`, the login page (VueLocalAuth) can now present a "Sign in with SSO" button alongside local credentials.
> This change makes the frontend detect *which* path was used and route logout correctly — local login clears the session and returns to VueLocalAuth, while SSO login also tears down the Azure AD session.

| Change    | File                          | Notes                                                                                                                                                                      |
| --------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ✏️ MODIFY | `src/auth.js`                 | Add `LOGIN_METHOD_KEY` localStorage constant. On `?Authorization=` callback, read and strip `auth_mode` param from URL — stores `'local'` if VueLocalAuth set it, `'sso'` otherwise. `logout()` now also clears `LOGIN_METHOD_KEY`. Added comment clarifying `auth_mode` is a logout-routing hint, not a security boundary. |
| ✏️ MODIFY | `src/composables/useAuth.js`  | Import `LOGIN_METHOD_KEY`. Mode 3 logout now reads `loginMethod` from localStorage *before* calling `authLogout()` (which clears it), then branches: `'sso'` → Azure AD logout; `'local'` or missing → redirect to VueLocalAuth login. Fixed logout return URL to use `import.meta.env.BASE_URL` instead of hardcoded `'/'` so subdirectory deployments are handled correctly. |

**Migration notes for existing users:**

1. **No breaking changes** — modes 0, 1, and 2 are completely unchanged.
2. **Mode 3 only** — both files must be updated together; updating only one will leave logout routing incomplete.
3. **`src/auth.js`** — Replace or merge. The new additions are: the `LOGIN_METHOD_KEY` export (line after `JWT_CLAIMS_KEY`), the `auth_mode` read/strip block inside the `if (jweToken)` handler, `localStorage.setItem(LOGIN_METHOD_KEY, ...)` after storing claims, and `localStorage.removeItem(LOGIN_METHOD_KEY)` inside `logout()`.
4. **`src/composables/useAuth.js`** — Replace or merge. Changes are: add `LOGIN_METHOD_KEY` to the import, read `loginMethod` at the top of `logout()` before `authLogout()`, and replace the flat mode-3 block with the branching `if (loginMethod === 'sso')` logic.
5. **No new env vars required** — Azure AD logout reuses the existing `VITE_AZURE_TENANT_ID` and `VITE_POST_LOGOUT_REDIRECT_URI` vars already needed for modes 1/2.

---

### v1.1.0 — 25-05-2026

> **New feature: Auth Mode 3 — VueLocalAuth (local SSO drop-in)**
>
> Adds a fourth authentication mode (`VITE_AUTH_MODE=3`) that replaces Azure AD SSO with **VueLocalAuth** — a self-hosted local auth service.
> Mode 3 behaves identically to Mode 2 (JWT + RBAC) but routes login/logout through the VueLocalAuth service instead of the SSO Proxy and Azure AD.
> No Azure AD tenant or SSO Proxy is required. Useful for environments without cloud identity, air-gapped networks, or local development with real auth.

| Change    | File                              | Notes                                                                                                                                                                                      |
| --------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ✏️ MODIFY | `.env`                            | Added `VITE_LOCAL_AUTH_URL` env var (required for mode 3). Updated `VITE_AUTH_MODE` comment to document mode `3`. Default mode changed to `3` in the template `.env`.                     |
| ✏️ MODIFY | `src/auth.js`                     | Login redirect now branches on `VITE_AUTH_MODE=3`: redirects to `VITE_LOCAL_AUTH_URL/login?next=<url>` instead of the SSO Proxy. Modes 1/2 behaviour unchanged.                           |
| ✏️ MODIFY | `src/composables/useAuth.js`      | Logout now handles mode 3 — skips Azure AD session teardown (VueLocalAuth is stateless) and redirects to the local login page instead.                                                     |
| ✏️ MODIFY | `src/composables/useRbac.js`      | RBAC fetch is now active for **both mode 2 and mode 3** (was mode 2 only). Comment and guard condition updated accordingly.                                                                 |
| ✏️ MODIFY | `src/main.js`                     | RBAC bootstrap (`fetchRbac`) now runs for both mode 2 and mode 3.                                                                                                                          |
| ✏️ MODIFY | `src/router/index.js`             | RBAC route guard (`screen_id` check) now applies to both mode 2 and mode 3.                                                                                                                |
| ✏️ MODIFY | `src/components/AppLayout.vue`    | Sidebar nav RBAC filtering (`can(requiredScreen)`) now active for both mode 2 and mode 3.                                                                                                  |
| ✏️ MODIFY | `src/nav.config.js`               | Updated `requiredScreen` comment to reflect that it is enforced in mode 2 **or** 3.                                                                                                        |
| ✏️ MODIFY | `src/views/ResetView.vue`         | Reset page now also clears the VueLocalAuth user cache (`DELETE /reset/<app>` on `VITE_LOCAL_AUTH_URL`) when mode 3 is active. VueLocalAuth reset failure is non-fatal (RBAC cache is still cleared). |
| ✏️ MODIFY | `README.md`                       | Added mode 3 to auth mode table, documented `VITE_LOCAL_AUTH_URL` env var, updated all RBAC references to include mode 3, updated `useRbac()` usage table.                                |

**Migration notes for existing users:**

1. **No breaking changes** — modes 0, 1, and 2 are completely unchanged. If you are not using mode 3, no action is required.
2. **To adopt mode 3:** Set `VITE_AUTH_MODE=3` and add `VITE_LOCAL_AUTH_URL=<your-vuelocalauth-url>` to your `.env`. The `VITE_SSO_URL`, `VITE_AUTH_TOKENS`, and `VITE_AZURE_TENANT_ID` vars are not used in mode 3.
3. **`src/auth.js`** — Replace this file. If you have local modifications (e.g. custom redirect logic), re-apply them after replacing — the only change in this file is the mode-3 branch in the redirect block.
4. **`src/composables/useAuth.js`** — Replace or merge the `logout()` function. The new mode-3 branch is inserted before the existing Azure AD redirect block.
5. **`src/composables/useRbac.js`** — Replace. The only change is `!== '2'` → `!['2', '3'].includes(...)` in the early-return guard.
6. **`src/main.js`** — Replace or update the single RBAC bootstrap condition (`=== '2'` → `['2', '3'].includes(...)`).
7. **`src/router/index.js`** — Replace or update the RBAC guard condition (same change as `main.js`).
8. **`src/components/AppLayout.vue`** — Replace or update the `navItems` computed property guard (same condition change).
9. **`src/views/ResetView.vue`** — Replace. If you have not customised this file, replace entirely. The logic is now split into RBAC reset + optional VueLocalAuth reset.

---

### v1.0.4 — 21-05-2026

> **Feature update:** Dark mode toggle, affiliate badge, Examples showcase page, Indigo theme, sidebar footer, and user profile enhancements.

| Change    | File                                            | Notes                                                                                                                                                          |
| --------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ✏️ MODIFY | `src/components/AppLayout.vue`                  | (1) Dark mode toggle button added to top bar (left of clock) — persists to `localStorage`. (2) Top bar uses `bg-sidebar` for colour consistency. (3) Affiliate badge added (reads `VITE_AFFILIATE_BADGE` env var). (4) "Developed by SP5143" footer added below user profile in sidebar. (5) User payroll now shown alongside dept code in profile. |
| ✏️ MODIFY | `src/style.css`                                 | Replaced theme with official shadcn Indigo (hue 264°, OKLCH). Background uses a subtle tinted value. `--ring` set to primary colour for coloured input focus rings. |
| ✏️ MODIFY | `src/nav.config.js`                             | Added Examples page nav entry (`LayoutPanelLeftIcon`, path `/examples`).                                                                                       |
| ✏️ MODIFY | `src/router/index.js`                           | Added `/examples` route pointing to `ExamplesView.vue`.                                                                                                        |
| ✏️ MODIFY | `.env`                                          | Added `VITE_AFFILIATE_BADGE=MES` — set to your affiliate/team code; leave blank to hide the badge.                                                             |
| ✏️ MODIFY | `README.md`                                     | Added `VITE_AFFILIATE_BADGE` to env vars table. Expanded Styling section with dedicated Buttons, Inputs, Tables, Cards, and status badge patterns referencing the Examples page. |
| ➕ ADD    | `src/views/ExamplesView.vue`                    | Component showcase page at `/examples` — visual reference for all UI patterns (buttons, inputs, table, cards, stat cards).                                     |
| ➕ ADD    | `src/components/examples/SectionCard.vue`       | Reusable section wrapper card used on the Examples page. Provides consistent header + body layout with `border-t-[3px] border-t-primary` accent.               |
| ➕ ADD    | `src/components/examples/StatCard.vue`          | Stat card component showing a label, value, delta, and icon. Used in the Examples page KPI row. No top border (inner card).                                    |

**Migration notes for existing users:**

1. **`AppLayout.vue`** — This file has many changes. The safest approach is to replace it entirely. If you have local customisations (e.g. custom nav icons, extra top-bar elements), merge those back in after replacing.
2. **`style.css`** — Replace entirely. If you have custom CSS added at the bottom, move it to a separate file or re-append after replacing.
3. **`.env`** — Add `VITE_AFFILIATE_BADGE=<your-code>` (or leave it empty to hide the badge).
4. **New files** — Copy the three new files (`ExamplesView.vue`, `SectionCard.vue`, `StatCard.vue`) directly into your project.
5. **`nav.config.js` / `router/index.js`** — Add the Examples entries (see the new files for exact syntax). These are additive — existing routes/nav entries are unaffected.

---

### v1.0.3 — 18-05-2026

> **Security fix:** SSO redirect URLs containing `?Authorization=...` could be copied and reused to access protected pages without going through the login flow.
> The router now strips the `Authorization` query param immediately on navigation (before auth/RBAC guards run), so the token is never retained in the URL.

| Change    | File                  | Notes                                                                                                                      |
| --------- | --------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| ✏️ MODIFY | `src/router/index.js` | Added step 0 in `beforeEach` to strip `?Authorization` from the URL on SSO redirects, preventing token leakage via copied links |

---

### v1.0.2 — 27-04-2026

> **Bug fix:** Removed `"base": "reka"` from `components.json` — this field is not a valid shadcn-vue config key and was breaking `shadcn-vue add <component>` installs.

| Change    | File              | Notes                                                                                         |
| --------- | ----------------- | --------------------------------------------------------------------------------------------- |
| ✏️ MODIFY | `components.json` | Removed `"base": "reka"` — invalid field that caused errors when adding new shadcn components |

---

### v1.0.1 — 23-04-2026

> **Bug fix:** Auth mode `0` (auth disabled) caused the protected page to not load.
> The auth guard was not short-circuiting correctly when `VITE_AUTH_MODE=0`, blocking navigation even though no JWT check should occur.

| Change    | File                     | Notes                                                                                                                                                                          |
| --------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ✏️ MODIFY | `src/router/index.js`    | Added `&& import.meta.env.VITE_AUTH_MODE !== '0'` condition to the auth guard so that when auth is disabled the JWT check is skipped entirely and navigation proceeds normally |
| ✏️ MODIFY | `src/views/HomeView.vue` | Display access codes properly                                                                                                                                                  |

---

## Adding a New Entry

When you make changes, add a block at the **top** of the Version History section:

```markdown
### vX.Y.Z — DD-MM-YYYY

> Short description of the release.

| Change    | File           | Notes                       |
| --------- | -------------- | --------------------------- |
| ➕ ADD    | `path/to/file` | What it does                |
| ✏️ MODIFY | `path/to/file` | What changed and why        |
| 🗑️ DELETE | `path/to/file` | Why it was removed          |
| ⚙️ CONFIG | `package.json` | Added `some-package@^1.0.0` |
```
