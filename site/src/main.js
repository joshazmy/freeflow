import Lenis from 'lenis'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { SplitText } from 'gsap/SplitText'

gsap.registerPlugin(ScrollTrigger, SplitText)

const html = document.documentElement
html.classList.add('js')

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ---------- smooth scroll: Lenis owns scroll, ScrollTrigger reads it ----------
if (!reducedMotion) {
  const lenis = new Lenis()
  lenis.on('scroll', ScrollTrigger.update)
  gsap.ticker.add((time) => lenis.raf(time * 1000))
  gsap.ticker.lagSmoothing(0)
}

// ---------- hero load choreography (one orchestrated sequence) ----------
// split AFTER fonts load, otherwise the line masks are measured on the fallback font and clip
if (!reducedMotion) {
  document.fonts.ready.then(() => {
    const split = new SplitText('.hero-title', { type: 'lines', mask: 'lines' })
    gsap.set('.hero-title', { opacity: 1 })
    gsap
      .timeline({ defaults: { ease: 'expo.out' } })
      .from(split.lines, { yPercent: 110, duration: 1, stagger: 0.08, delay: 0.1 })
      .from('.hero-sub', { opacity: 0, y: 12, duration: 0.6 }, '-=0.5')
      .from('.hero-cta', { opacity: 0, y: 12, duration: 0.6 }, '-=0.45')
      .from('.pill-demo', { opacity: 0, y: 12, duration: 0.6 }, '-=0.4')
  })
}

// ---------- section reveals: 12px rise + fade once per element ----------
if (!reducedMotion) {
  for (const el of document.querySelectorAll('.reveal')) {
    gsap.to(el, {
      opacity: 1,
      y: 0,
      duration: 0.6,
      ease: 'expo.out',
      scrollTrigger: { trigger: el, start: 'top 88%', once: true },
    })
  }
}
// reduced-motion path: CSS never hides .reveal (guarded by no-preference), so nothing to do.

// fonts shift layout; recalc trigger positions once they are in
document.fonts.ready.then(() => ScrollTrigger.refresh())
