# DESIGN.md — Freeflow landing page

Authority file. Every visual/motion decision defers to this. If code and this file disagree, this file wins.
Source of the look: the APPROVED app mockup `../design/mockup.html` (cream/ink/lavender Wispr-Flow
language) — this page is the same product wearing the same clothes. Stitch-mode translation, not a
new art direction.

## Design read
Product landing page for privacy-minded Linux users, warm paper-and-ink editorial language with
one lavender accent, leaning print/stationery calm (the anti-SaaS look).
Dials: VARIANCE 6 / MOTION 3 / DENSITY 4

## References
- `design/mockup.html` (the app itself) · cream paper, ink 1px borders, pill radius 999, card
  radius 20 with hard offset shadow, serif display + sans body.
- Wispr Flow marketing language · short verb-first claims, generous air, product does the talking.

## Type (self-hosted in /public/fonts — ZERO third-party requests, it's a privacy product)
- Display: Sentient (Fontshare), 400/500/700 — big serif headlines, italic for the wordmark,
  tight leading (0.95-1.05), sizes clamp(2.6rem, 7vw, 6.5rem) hero.
- Body: General Sans (Fontshare) 400/500/600, max 62ch, 1rem/1.06rem.
- Numerals/terminal: ui-monospace stack in the mono chips. All commands mono.

## Color (locked — light theme, whole page; ONE accent)
- --cream #FFFEF0 (page bg) · --cream-2 #FDFCE9 (alt band) · --card #FFFFFF
- --ink #111110 (text + all 1px borders) · --border-soft #ddd6b8 (hairlines on cream)
- --accent #E7D4F9 lavender (the ONLY accent: primary CTA fill, active pills, ONE emphasis/section)
- --ok #2e7d4f green: SEMANTIC status only (the "all local" dot + check marks), never decorative.
- Hard shadow: 3px 3px 0 rgba(17,17,16,0.12). WCAG AA: ink on cream = 17:1; muted = ink at 62% min.

## Motion rules (restrained, 3/10 — paper does not bounce)
- Enter ease-out cubic-bezier(0.23, 1, 0.32, 1); UI < 300ms; reveal staggers 50ms.
- Lenis owns scroll. Reveals: 12px rise + fade once per section, no scrub theatrics.
- ONE hero load sequence: wordmark, headline lines (SplitText inside fonts.ready), then the pill demo.
- The ONLY looping motion: the hero pill's mic bars (the product's own overlay, CSS keyframes,
  4 bars, subtle) — justified: it IS the product. Pauses under prefers-reduced-motion.
- NO count-ups, NO magnetic hover, NO parallax, NO sticky scrub. prefers-reduced-motion = static
  editorial (reveals become instant, bars frozen mid-pose).

## Hero visual
Type-only + a CSS recreation of Freeflow's on-screen dictation pill (rounded pill, ink border,
4 animated lavender-tinted bars, caption "hold ⌃ ⌥ ⇧ … speak … release"). No WebGL, no video.

## Layout (sections, in order)
1. **Nav**: logo lockup left (Josh's wordmark option 1a: lowercase Jura "freeflow", 0.34em
   tracking, animated dashed wave underneath, ink on cream, self-hosted Jura, wave pauses under
   reduced-motion); right: GitHub pill (ink border) + accent pill "Install". Footer reuses the lockup.
2. **Hero** (~92dvh): eyebrow mono chip "$ 100% local dictation for Linux"; H1 serif "Speak.
   It types." two lines; sub one sentence; CTA row: accent pill "Get Freeflow" (→ GitHub) + ghost
   pill "How it works" (→ #how); below: the animated dictation pill demo.
3. **How it works**: 3 pill-numbered steps in a row (hold hotkey / talk / release), each a card:
   whisper.cpp transcribes on your machine, a small local AI tidies, text lands at your cursor.
4. **Features**: asymmetric 2-column card grid (radius 20, hard shadow): AI cleanup (before/after
   sample), Tones per app (Formal/Neutral/Casual pills), Personal dictionary, Local history,
   Dark mode (mini theme swatch), Tray and hotkey. Lavender emphasis: exactly one active pill per card.
5. **Privacy band** (bg --cream-2, top/bottom 1px --border-soft): huge serif "100% local." + 4
   check rows (audio never leaves this machine / no accounts / no telemetry / works offline) +
   mono chip `$ freeflow status → ● all local` (green dot).
6. **Install**: mono terminal card (radius 16, ink bg, cream text — the single dark surface on
   the page): 3-command quickstart; caption row: "Fedora, Arch and Debian friendly · MIT ·
   uninstall.sh removes every trace". Secondary link "Read the install guide" → GitHub README.
7. **Footer**: wordmark, MIT License, GitHub link, "Built for Linux (Wayland). No cloud anywhere."

Mobile (390): single column, steps stack, feature grid 1-col, pill demo shrinks, nav collapses to
wordmark + Install pill (keep the primary CTA; GitHub stays reachable via hero + footer).

## Copy rules
Plain English, verb-first, no em-dashes anywhere in page copy, no marketing superlatives the app
can't prove. Numbers appear instantly (no count-ups).

## Ship-readiness
Title "Freeflow: 100% local dictation for Linux"; meta description; OG tags; favicon = lavender
rounded square with ink "F" serif (inline SVG data URI). base '/freeflow/' for GitHub Pages.
gzip budget tiny (<300KB incl. fonts). pa11y AA clean. Keyboard: focus-visible ink outline on
every link/button.

## Bans (standing + this page)
Lenis owns scroll · one accent (lavender) · no em-dashes in copy · no Inter/Roboto · no WebGL ·
no atmosphere presets, dust, halos · no glassmorphism (paper brand = solid surfaces + hairlines).
