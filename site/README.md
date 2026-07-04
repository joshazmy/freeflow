# website-template

Pinned awwwards-style site scaffold, extracted from the 5080 Ti build (2026-07-03).
Used by the `/make-website` skill — don't hand-copy unless the skill is unavailable.

Stack: Vite vanilla + three 0.185.1 + gsap 3.15.0 (ScrollTrigger/SplitText) + lenis 1.3.25.

## What's inside
- `DESIGN.md` — art-direction template the grill fills in BEFORE code
- `CLAUDE.md` — verification loop + the traps already paid for
- `index.html` — skeleton with the layout-discipline rules inline
- `src/style.css` — token system + nav/hero/sections/footer + grain overlay
- `src/main.js` — Lenis+GSAP wiring, hero choreography, counters, reveals, magnetic CTA (generic)
- `src/scene.js` — full 3D reference implementation: ACES + RoomEnvironment + bloom/vignette/grain,
  lerped scroll-driven object, dust field, depth halo, idle float, quality tiers, reduced-motion +
  no-WebGL fallbacks. Swap `buildCard()` for the new hero object; delete if the site has no 3D.

## Update policy
Versions are pinned because they were tested together. To upgrade: bump here, run a full build +
screenshot pass on a scratch project, fix breaks, THEN update this README. Never bump inside a
child project.
