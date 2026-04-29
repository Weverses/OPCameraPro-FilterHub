# OPCameraPro FilterHub

Seed repository for the public `Weverses/OPCameraPro-FilterHub` GitHub Pages source.

## Layout

- `packages/*.opcfilter.zip`: reviewed filter packages committed by maintainers.
- `public/index/v1.json`: generated repository index consumed by OPCameraPro.
- `public/filters/<sha256>.opcfilter.zip`: generated package copies served by Pages.
- `public/previews/<sha256>.jpg`: generated preview images served by Pages when present.

## Maintainer Flow

1. Review a user submission from the `Filter submission` issue form.
2. Add the approved `.opcfilter.zip` to `packages/`.
3. Run `python3 tools/build_index.py --check`.
4. Merge the PR. GitHub Actions validates and deploys `public/` to Pages.

