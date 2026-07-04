# <project> — built with the /make-website pipeline

## Authority
- **DESIGN.md rules every visual/motion decision.** It is filled by the grill BEFORE code. Read it first, always.
- Skills in play: `design-taste-frontend` (layout/copy bans), `frontend-design` (aesthetic floor),
  `awwwards-3d` (only if 3D hero), `gsap-*` (API correctness), `taste` (extract tokens from reference URLs).

## Stack (pinned by package.json — bump only via the template, never silently)
three 0.185.1 (built-in EffectComposer from three/addons, NOT the `postprocessing` npm lib) ·
gsap 3.15.0 (ScrollTrigger, SplitText — all plugins free/public) · lenis 1.3.25 (`lenis`, NOT `@studio-freight/lenis`) ·
Vite vanilla. No React. No new deps without a stated reason.

## Commands
- `npm run dev` — http://localhost:5173 (localhost-only; never `--host` without Josh's OK, Tailscale-only if so)
- `npm run build && npm run preview` — production check

## Verification loop (mandatory after EVERY section)
1. `agent-browser open http://localhost:5173` → `screenshot` at desktop, then `agent-browser set viewport 390 844` for mobile.
2. Compare against DESIGN.md: a SPECIFIC diff (spacing, type scale, alignment, palette), never a vibe check.
3. Console: `agent-browser console` — buffer is CUMULATIVE across loads; drop a
   `console.log('MARKER')` via eval, reload, and only read lines after the marker.
4. Scroll states: `agent-browser eval "window.scrollTo(0, document.querySelector('.x').offsetTop - innerHeight*0.5 + h*0.5)"`,
   wait ~2s for the scrub to settle, then screenshot.
5. Motion is invisible in screenshots: verify values against DESIGN.md numbers + Josh's eyes at checkpoints.

## Known traps (paid for on 2026-07-03 — do not rediscover)
- SplitText BEFORE fonts load = clipped mask lines. Split inside `document.fonts.ready.then()`.
- Canvas-texture lettering: rebuild textures on `document.fonts.ready` too.
- three r185: use `THREE.Timer` (Clock is deprecated); `timer.update()` first in the loop.
- Emissive + bloom: start emissiveIntensity ~1.1, bloom 0.4/0.28/0.82 — 2.5+ floods the frame.
- 3D meshes must physically fit their housings — check the SIDE view, not just the front (fan-blade spikes).
- A 3D pose that faces the camera can hide broken geometry; screenshot every scroll pose.
- Scene needs environment (dust/halo/idle motion/lettering) or it reads as tech demo — see scene.js env pass.
- Scroll tweens: end 'center 65%' so the rest pose is reached while the section text is centered.
- Vite may bind IPv6 only: test with `localhost`, not `127.0.0.1`.

## Files
- `index.html` (all DOM) · `src/style.css` (tokens mirror DESIGN.md) · `src/main.js` (Lenis/GSAP wiring, reveals, counters, magnetic CTA) · `src/scene.js` (3D: swap `buildCard()` for this project's object; delete file + canvas if no 3D)
- `.brain/` — decisions, tried, handoff

## Light-scene traps (paid for on 2026-07-04, Fantik stress test — apply when DESIGN.md says light theme)
- Bloom threshold must sit ABOVE the background luminance: on a paper bg, threshold 0.82-0.85 blooms
  the BACKGROUND and veils the product in white haze. Use threshold ~1.0, strength ~0.15.
- Vignette <=0.1 on light scenes or the whole canvas reads grayer than the page and the nav seam shows.
- No additive dust on light bg (invisible/dirty); depth = soft ink contact-shadow plane instead.
- Bright materials (white wraps/labels) blow out under RoomEnvironment: drop color to ~0xc4c9c3 and
  envMapIntensity to ~0.25.
- DOM grain overlay: 0.035 max on paper (0.05 reads dirty).
- DOM labels over 3D parts: place approximate CSS percents, screenshot, measure, re-aim. Expect one
  measuring iteration PER BREAKPOINT (desktop and mobile poses differ).
- Exploded-view offsets: parts need ~0.15 world-unit clearance at explode=1 or perspective makes them
  read as touching; verify against a screenshot, not the numbers.
- Giant mono numerals: a literal space at 10rem mono is ~1em wide — wrap units in a span at 0.45em.

## Council lessons (2026-07-04 Fantik round — generalize to every build)
- MATCH MOTION TO PRODUCT CHARACTER: precision/industrial object = indexed, stepped, mechanical
  motion (detent clicks, hard 1px button press); no idle bob, no dust, no halo, no magnetic hover
  unless the brand is soft. Atmosphere presets are the #1 "template tell".
- Count-up animations on static specs = cliché + screen-reader hostile. Numbers appear instantly.
- Accent budget: the accent appears on the product's accent part + primary CTA + ONE emphasis
  event per section. More = hierarchy collapse.
- Sticky scrub sections: ~130dvh max per idea. 240dvh to read 7 labels = pacing poison.
- Check secondary-text contrast on dark bg (#9aa39c on #121413 = 3.8:1 FAILS AA). Add :focus-visible.
- GSAP: tweening a property that doesn't exist yet on a plain object logs "Missing plugin?" —
  declare every scrubbed property in the target literal up front.

## Ship-readiness (2026-07-04 gap audit)
- Template head now ships OG tags + a placeholder favicon — REPLACE placeholders on any build whose
  link gets shared (OG card is what renders in chat previews). Concept-only builds can leave them.
- Image-heavy 2D sections (photos/galleries): compress, WebP/AVIF, srcset + lazy-load — the 3D skill
  covers Draco/KTX2 but nothing owned flat images until now.
- Perf bar if the build is real: LCP < 1.5s, CLS < 0.05, gzip < 3MB, device-tier gating.

## Perf traps (paid for on 2026-07-04 — Fantik perf panel)
- `antialias: true` is WASTED under EffectComposer (scene renders into composer targets, not the
  MSAA framebuffer) — omit it; DPR ≥1.5 smooths edges anyway. Verified zero visual change.
- Reduced-motion users must NOT get a perpetual render loop on a static scene: skip
  setAnimationLoop, render on demand (init + fonts.ready + resize). See fantik scene.js.
- Swapping a material's CanvasTexture (e.g. after fonts.ready) leaks the old one — `map.dispose()`
  before reassigning.
