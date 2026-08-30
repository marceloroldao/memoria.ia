# Memoria.ia brand assets

This directory is the canonical visual identity source for Memoria.ia.

## Master files

- `logo-primary.svg` — original primary lockup.
- `logo-horizontal.svg` — preferred horizontal lockup.
- `logo-stacked.svg` — vertical/stacked lockup.
- `symbol.svg` — original symbol master.
- `symbol-square.svg` — app/avatar square.
- `favicon.svg` — small-size optimized icon.
- `logo-monochrome-light.svg` — white mark on dark background.
- `logo-monochrome-dark.svg` — dark mark on light background.
- `banner-github.svg` — 1280×640 repository/social banner.
- `brand-tokens.css` — reusable design tokens.
- `BRAND_GUIDE.md` — identity rules and rationale.

## Raster exports

`assets/brand/raster/` is generated automatically from the SVG masters by `.github/workflows/brand-raster.yml`.

Expected exports include 512, 1024 and 2048 px symbol PNGs, a horizontal logo PNG, GitHub banner PNG and favicon PNG/ICO.

Do not edit generated raster files manually. Change the SVG master and regenerate.
