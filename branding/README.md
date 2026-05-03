# Nous Ergon Branding

Shared design system for Nous Ergon / Alpha Engine. Public folder, public repo. Updates here propagate to every public surface — repo READMEs, OG social-preview images, the public website, and the private dashboard.

## Contents

| File | Purpose |
|------|---------|
| [`design_tokens.json`](design_tokens.json) | Canonical color palette, typography, spacing — single source of truth for all surfaces |
| [`design_tokens.css`](design_tokens.css) | Same tokens as CSS custom properties (for the public site + Streamlit dashboard CSS injection) |
| [`brand_banner.md`](brand_banner.md) | One-line README banner snippet — copy-paste into every public repo |
| [`badge_bar.md`](badge_bar.md) | Standardized README badge bar — brand · CI · tests · python · stack · license · phase |
| [`og_image_template.md`](og_image_template.md) | OG (social-preview) image generation guidance + template |
| [`plotly_template.json`](plotly_template.json) | Shared Plotly chart template — used by dashboard so charts match the public site palette |
| `logos/` | Logo files (PNG, SVG) at multiple sizes |

## Naming + brand

- **Public brand:** Nous Ergon (νοῦς ἔργον)
- **Underlying project name:** Alpha Engine (used in repo and S3 names: `alpha-engine`, `alpha-engine-research`, etc.)
- **Canonical tagline:** *"Autonomous Multi-Agent Trading System"* (matches resume; locked)
- **Phase positioning:** Phase 2 — Reliability Buildout (current as of 2026-05)

## How to use

- Repo READMEs → copy `brand_banner.md` snippet to top, copy `badge_bar.md` for badges, set OG image per `og_image_template.md`
- Streamlit dashboard → reference `design_tokens.css` via custom CSS injection; load `plotly_template.json` for charts
- Public website → reference `design_tokens.css` directly
- New surfaces → start by reading this folder

## Updating

Single source of truth. If you change the palette, change it here first; downstream surfaces inherit. Don't fork tokens per surface.
