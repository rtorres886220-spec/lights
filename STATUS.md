# STATUS — LYNAR L-configuration landing page (2026-11-25)

Deliverable: `/home/user/lynar-landing/index.html` — single self-contained file (2.44 MB raw / 1.03 MB gzip / 0.89 MB brotli). Model, three.js r170, GSAP 3.12.5, Lenis 1.1.13 bundled inside. Only external request: Google Fonts (Bricolage Grotesque + IBM Plex Mono).
Source: `lynar-landing/src.html` (CDN import map, for editing) → built with `audit/build.mjs` (esbuild).
Evidence: `lynar-landing/audit/` (screenshots, logs, test scripts).

## PROVEN (command + output in audit/)
- Model: the `Intra-lighting_LYNAR_SDI` subtree only (3 profiles, 90° corner, 6 luminaire families). Simplified to 231,193 tris with EYE bodies protected from faceting; 1.07 MB GLB.
- Interaction (`audit/dragtest.js` → `interaction_test.log`):
  - Free rotation on all 3 axes, with inertia.
  - Arrow-key rotation.
  - Light 1/0 toggle (spot intensity goes to 0.00).
  - Kelvin buttons drive the scene lights and the CSS accent.
  - The product returns exactly to its reference orientation on chapter change (q = 0,0,0,±1).
  - 0 errors.
- Performance (`audit/perf.js` → `performance_audit.log`), after optimization:

  | Metric | Before | After |
  |---|---|---|
  | Draw calls / frame | 353 | 66 |
  | Triangles / frame | 1.31M | 442k |
  | JS frame cost, 1× CPU (p50 / p95) | — | 1.4 / 2.5 ms |
  | JS frame cost, 4× CPU throttle (p50 / p95 / max) | — / 29.7 / 42 ms (failed) | 6.2 / 12.1 / 13.8 ms (under 16.7 ms) |
  | Emulated GPU frame time (relative comparison only) | 3.0 s | 1.63 s (−46%) |

  - CLS 0.001–0.002.
  - JS heap 22–48 MB.
  - 0 console errors.
- Accessibility: axe-core 4.10.2 reports 0 violations; Lighthouse accessibility 100 (pre-fix run).
- Visual audit: every chapter rendered at 1440×900 and 390×844 and checked against the brief. Fixed during the audit:
  - beam haze and sawtooth beam edges;
  - grey-reading profile;
  - geometry over the copy (KALIS, EYE, specs);
  - hotspot labels colliding or clipping;
  - mobile framing;
  - orientation return being slow at low frame rates;
  - favicon 404 (the only Lighthouse best-practices failure).
- Fonts load from Google Fonts: URL fetched, HTTP 200, 15 font faces.
- All on-page dimensions are measured from the CAD bounding boxes: 2103×1075, 40×66, 3×1000, 731, 75, 565, 36, 106, 178, 16 LEDs / 566, 640.

## UNPROVEN
- Real-GPU frame rate (60fps target). This container renders with SwiftShader (software). The CPU side is proven within budget; the GPU side needs a real device.
- Real-device touch feel (horizontal-start drag rotates; vertical swipe scrolls). Logic is implemented; not tested on a phone.
- Lighthouse performance score: the only run (score 49, TBT 57 s) was pre-optimization and dominated by software-GPU blocking. Not meaningful; re-run on real hardware.

## BLOCKED
- Loading the libraries from public CDNs: jsDelivr, unpkg and cdnjs are refused by this container's proxy (403). Worked around by bundling, so `index.html` doesn't need them. `src.html`'s import-map URLs exist in the npm tarballs but weren't loaded live.

## FAKE (placeholder, labelled)
- The "Request photometrics" CTA links to `#contact`, which is a placeholder target.
- Kelvin buttons are labelled on-page "Visualisation only · not a product specification".

## Changed from the brief
- No refractive glass: the product's only glass-like parts are millimetre-wide diffusers. Their transmission pass cost a full extra scene render, so they're emissive-lit instead.
- No anisotropic brushed metal: the L-frame subtree contains none, so none was invented.

## Locks touched
- Locks not loaded (no DECISIONS.md / DESIGN_SPEC.md).

## Next action
- Open `index.html` on your laptop and phone: check 60fps, the drag feel and the scroll.
- Then decide the branding/rights question (Intra-lighting's name and CAD) before publishing anywhere.
