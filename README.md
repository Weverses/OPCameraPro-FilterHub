# OPCameraPro FilterHub

Seed repository for the public `Weverses/OPCameraPro-FilterHub` GitHub Pages source.

## Layout

- `packages/*.opcfilter.zip`: reviewed filter packages committed by maintainers.
- `public/index/v1.json`: generated repository index consumed by OPCameraPro.
- `public/filters/<sha256>.opcfilter.zip`: generated package copies served by Pages.
- `public/previews/<sha256>.jpg`: generated preview images served by Pages when present.

## Maintainer Flow

1. Users submit `.opcfilter.zip` through the `Filter submission` issue form.
2. `Auto Accept Filter Submission` downloads and validates the package automatically.
3. Valid packages are committed into `packages/`, published to GitHub Pages, and the issue is closed automatically.
4. Invalid, unsafe, duplicate, or malformed packages get a failure comment and stay open for resubmission.

Manual validation is still available:

```bash
python3 tools/build_index.py --check
```
