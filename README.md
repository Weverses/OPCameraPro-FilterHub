# OPCameraPro FilterHub

Seed repository for the public `Weverses/OPCameraPro-FilterHub` GitHub Pages source.

## Layout

- `packages/*.opcfilter.zip`: reviewed filter packages committed by maintainers.
- `public/index/v1.json`: generated repository index consumed by OPCameraPro.
- `public/filters/<sha256>.opcfilter.zip`: generated package copies served by Pages.
- `public/previews/<sha256>.jpg`: generated preview images served by Pages when present.

## Maintainer Flow

1. Users submit `.opcfilter.zip` through the `Filter submission` issue form.
2. `Validate Filter Submission` checks the attachment automatically and comments with the result.
3. If the package looks acceptable, add the `accepted` label to the issue.
4. `Accept Filter Submission` downloads the package, validates it again, commits it into `packages/`, and closes the issue.
5. `Publish FilterHub` rebuilds `public/index/v1.json` and deploys GitHub Pages.

Manual validation is still available:

```bash
python3 tools/build_index.py --check
```
