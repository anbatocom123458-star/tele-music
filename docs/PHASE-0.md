# Wioos Witness — Phase 0 (Discovery & Audit)

> **Status:** PRE-IMPLEMENTATION. No application code has been written.
> **Prepared per:** `design-taste-frontend` skill (`Leonxlnx/taste-skill`, hash-tracked in `skills-lock.json`).
> **Date:** 2026-09-16 · **Repo:** `tele-music` @ `53f9e8c`

---

## 0. Assumption Disclosure (read first)

The "Wioos Witness specification" was **not found** in this repository (including full git
history and all branches) or on the public web. This document therefore constructs Phase 0
from the only available evidence:

1. The repo name **`tele-music`** — read as *Telegram + music*.
2. The `design-taste-frontend` skill's Phase-0 obligations (Design Read, dials, audit-first).

Every product decision below is marked **[ASSUMPTION]** and must be confirmed before Phase 1.
No code was written, exactly as instructed.

---

## 1. Project Audit (as-is state)

| Item | Finding |
|---|---|
| Application code | **None.** No `package.json`, no source tree, no framework. |
| `README.md` | Title only (`# tele-music`, 12 bytes). No product definition. |
| Git history | 2 commits (`Initial commit`, `skill`), single `main`, clean tree. |
| Installed tooling | 13 agent skills from `Leonxlnx/taste-skill`, hash-pinned in `skills-lock.json`. Primary: `design-taste-frontend`. |
| CI / tests / lint | None. |
| Secrets / env | None present. |

**Verdict:** Greenfield project. Audit-first obligation is trivially satisfied — there is
nothing to preserve, migrate, or redesign. The full skill checklist applies to the new build.

---

## 2. Design Read (skill §0.B, one line)

> **Reading this as:** a Telegram music product's web landing + in-app surfaces for
> music listeners, with a **dark-first, premium-consumer, audio-forward** language,
> leaning toward **Next.js + Tailwind v4 + Motion (framer-motion), dark-mode via CSS
> variables**, motion intensity moderate (music products reward rhythm, not noise).

**Dials (skill §1):**

| Dial | Value | Rationale |
|---|---|---|
| `DESIGN_VARIANCE` | **7** | Consumer landing default (skill §1.B "Premium consumer"), not agency-chaotic. |
| `MOTION_INTENSITY` | **6** | Fluid choreography; mandatory `prefers-reduced-motion` degradation (skill §6.B). |
| `VISUAL_DENSITY` | **3** | Art-gallery-adjacent; music UI needs breathing room around artwork. |

**Hard constraints inherited from the skill (non-negotiable in later phases):**
- Dual light/dark from day one; no pure `#000`/`#fff`; WCAG AA body / AAA hero contrast (§8).
- No `window.addEventListener('scroll')`; animate only `transform`/`opacity` (§5.D, §6.A).
- No AI-tell patterns: no purple gradients, no 3-equal-card rows, no Inter-by-default,
  no generic placeholder names (§9).
- One design system per project; real packages over hand-rolled imitations (§2).

---

## 3. Product Hypothesis [ASSUMPTION]

`tele-music` is a **Telegram music bot / mini-app** that lets users search, share, and
listen to music inside Telegram. "Wioos Witness" is treated as the **project codename**
for this Phase-0 lifecycle. Derived scope candidates (to be confirmed):

- [ ] A. Telegram **bot** (search → stream/download links inline)
- [ ] B. Telegram **Mini App** (in-Telegram web player UI)
- [ ] C. Public **landing page** for the product
- [ ] D. All of the above

**Critical open questions (blockers for Phase 1):**
1. **Sources & legality** — where does audio come from? (Licensed API vs. user-provided
   links vs. public-domain). This determines feasibility more than any design decision.
2. **Platform** — bot only, Mini App only, or bot + web landing?
3. **Runtime/stack constraint** — is Next.js + Tailwind acceptable, or is there a
   mandated stack (e.g., pure Node bot with `node-telegram-bot-api` / `grammy`)?
4. **Hosting** — Telegram bots need a public HTTPS webhook or long-polling host.

---

## 4. Proposed Phased Plan (pending answers above)

| Phase | Deliverable | Gate |
|---|---|---|
| **0 (this doc)** | Audit + Design Read + dials + stack proposal + question list | User confirms scope & sources |
| 1 | Scaffold: framework, tokens (color/type/spacing), dark/light, CI, lint | Skill pre-flight check passes |
| 2 | Core surfaces (bot handlers and/or player UI + landing) | Skill §9 anti-slop sweep clean |
| 3 | Motion pass (Motion/GSAP per §5) with reduced-motion parity | Lighthouse: LCP<2.5s, INP<200ms, CLS<0.1 (§6.D) |
| 4 | Accessibility + dual-mode audit, both themes tested (§8.D) | WCAG AA verified |

**Recommended stack (proposal only — awaiting confirmation):**
- App: **Next.js (App Router) + TypeScript** — covers Mini App + landing in one tree.
- Styling: **Tailwind v4**, semantic tokens as CSS variables (one strategy, §8.A).
- Motion: **Motion (framer-motion)** for reveals; GSAP ScrollTrigger only if pin/scrub is needed.
- Bot layer (if A/D): **grammY** on Node, long-polling in dev, webhook in prod.
- Fonts: non-Inter grotesk (e.g., Geist/Outfit/Satoshi family) — skill §9.B.

---

## 5. Sign-off Checklist

- [x] Skill read end-to-end (1,206 lines) before any code
- [x] Project audited (empty greenfield, nothing to preserve)
- [x] Design Read declared; dials set
- [x] No application code written
- [ ] **User confirms §3 scope questions (sources, platform, stack, hosting)** → unlocks Phase 1
