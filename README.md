# LYNAR — L-configuration landing page

Interactive product page for the LYNAR SDI profile in an L configuration with six luminaire families, built from the manufacturer CAD model.

- `index.html` — the page. Self-contained: model, three.js r170, GSAP 3.12.5 and Lenis 1.1.13 are bundled inside. Only Google Fonts loads externally. Open it in a browser or host it as a static file.
- `src.html` — editable source (uses a CDN import map).
- `lynar-l.glb` — extracted, simplified model (231k triangles, meshopt-compressed).
- `audit/` — build script, test scripts, screenshots and logs.
- `STATUS.md` — what is proven, unproven, blocked and placeholder.

## Rebuild
`audit/build.mjs` bundles `src.html` + `lynar-l.glb` into `index.html` with esbuild.
It needs `three@0.170.0`, `gsap@3.12.5`, `lenis@1.1.13` and `esbuild@0.24.0` installed, and its two path constants edited for your machine.

## Interaction
- Drag (or use the arrow keys) to rotate on any axis.
- Scroll to move through the chapters.
- Light 1/0 toggles all lights; chapter 08 switches colour temperature.

Product name and CAD geometry belong to their manufacturer. Confirm usage rights before publishing.
