# OG (Open Graph) Image Template

Each public repo gets a custom social-preview image used by GitHub when the repo URL is shared on LinkedIn, Slack, Twitter, or in a recruiter email. **This is the highest-leverage visual asset for recruiter-facing presentation** — it's the first thing anyone sees in a link preview.

## Specs

- **Dimensions:** 1280 × 640 PNG
- **Max size:** 1 MB
- **Format:** PNG with sRGB color profile
- **GitHub upload:** Settings → Social preview → Upload an image

## Layout (consistent across all 6 module repos + alpha-engine-docs)

```
┌────────────────────────────────────────────────────────────┐
│  [LOGO]  Nous Ergon                                        │
│                                                             │
│  alpha-engine-<module>                                      │
│  <module one-liner — same as repo description>              │
│                                                             │
│  [System architecture mini-diagram with this module        │
│   highlighted in brand-primary; siblings dimmed]            │
│                                                             │
│  Autonomous Multi-Agent Trading System  ·  Phase 2          │
└────────────────────────────────────────────────────────────┘
```

## Visual rules

- **Palette:** strictly from `design_tokens.json`/`design_tokens.css` — no off-palette colors
- **Typography:** `font_family_sans` from tokens — same font family as the public site
- **Canvas:** `background` (`#000000`) — matches public site
- **Module highlight color:** `brand_primary` (`#1a73e8` Google-blue)
- **Sibling modules in diagram:** `text_muted` (`#888888`)
- **Body text:** `text_primary` (`#fafafa`)
- **Phase tag color:** `phase_2` (`#e9c46a`) for current state; updates when phase changes

## How to generate

Two paths — pick one and stick with it for consistency.

### Option A — Figma template (recommended)
1. Create one Figma file with 7 frames (one per repo)
2. Each frame uses the same components, different module highlight
3. Export 1280×640 PNG per frame
4. Commit exports under `branding/og_images/<repo-name>.png`

### Option B — HTML-to-image script
1. Single HTML template with template variables for module name + one-liner + highlight position
2. `playwright` or `puppeteer` to render to PNG at 1280×640
3. Loop over all 7 repos in CI to regenerate on demand
4. Script committed under `branding/scripts/generate_og_images.py`

## Per-repo content

| Repo | Module name in image | One-liner |
|------|----------------------|-----------|
| `alpha-engine` | Executor | Risk-gated position sizing + intraday execution |
| `alpha-engine-research` | Research | LangGraph multi-agent investment research pipeline |
| `alpha-engine-predictor` | Predictor | Stacked meta-ensemble: Layer-1 GBMs + Layer-2 Ridge |
| `alpha-engine-data` | Data | Centralized ArcticDB feature store + macro + alt data |
| `alpha-engine-backtester` | Backtester | Signal quality + autonomous parameter optimization |
| `alpha-engine-dashboard` | Dashboard | Read-only system monitoring (Streamlit) |
| `alpha-engine-docs` | System Overview | Canonical entry point — links all modules |

## Maintenance

When the system architecture changes (new module, retired module, renamed module):
1. Update the architecture mini-diagram in the Figma file or HTML template
2. Regenerate all 7 OG images
3. Re-upload to each repo's social preview settings

When phase changes (Phase 2 → Phase 3):
1. Update phase tag color in tokens
2. Update phase tag text in OG template
3. Regenerate all 7 OG images
