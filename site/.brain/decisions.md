# Decisions — Freeflow landing page

- 2026-07-04 Stitch-mode: design authority = the approved app mockup (design/mockup.html).
  Cream/ink/lavender, Sentient + General Sans. No new art direction.
- No WebGL: paper/print brand; CSS pill demo instead (the product's own overlay IS the hero visual).
- Fonts SELF-HOSTED (public/fonts) so the page makes zero third-party requests — on-brand for a
  privacy product. Fontshare CDN link removed from template head.
- Green #2e7d4f allowed as SEMANTIC status color only (all-local dot); lavender stays the one accent.
- Deploy: GitHub Pages via Actions (site/ → dist, vite base '/freeflow/'). Never a second repo.
- Gates waived by Josh for this run ("push ... make public ... then make a website ... then check").
- 2026-07-04 check findings: "Local history" site claim was RIGHT, README table was stale (fixed
  README). Mobile nav keeps Install (primary CTA) not GitHub; DESIGN.md amended to match.
- 2026-07-04 logo: Josh picked wordmark option 1a (Jura lowercase + dashed wave) from his logo
  sheet; recolored to site ink, Jura self-hosted, wave animation paused under reduced-motion.
