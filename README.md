# OPCameraPro FilterHub

Seed repository for the public `Weverses/OPCameraPro-FilterHub` GitHub Pages source.

## Copyright Disclaimer / 版权免责声明

Community submissions are provided by their submitters, not by OPCameraPro. OPCameraPro does not claim ownership of submitted LUTs, does not guarantee their copyright status, license status, source, legality, quality, or fitness for any purpose, and does not endorse them as official content.

投稿滤镜由投稿者提供，并非 OPCameraPro 官方内容。OPCameraPro 不声明拥有投稿 LUT 的版权，也不对其版权状态、授权状态、来源、合法性、质量或用途适配性作担保。

Each submitter must confirm that they created the LUT themselves or have explicit permission to redistribute it. The submitter is solely responsible for copyright, licensing, legality, and related disputes.

每位投稿者必须确认该 LUT 由自己创作，或已获得明确的再分发授权。版权、授权、合法性及相关争议责任由投稿者自行承担。

Automation in this repository only validates technical package format, checksums, size limits, duplicate content, and required files. Passing automation is not copyright, license, or legal approval.

本仓库的自动流程只校验技术格式、校验和、大小限制、重复内容和必要文件。自动校验通过不代表版权、授权或法律审核通过。

## Layout

- `packages/*.opcfilter.zip`: reviewed filter packages committed by maintainers.
- `public/index/v1.json`: generated repository index consumed by OPCameraPro.
- `public/filters/<sha256>.opcfilter.zip`: generated package copies served by Pages.
- `public/previews/<sha256>.jpg`: generated preview images served by Pages when present.

Package manifests must retain `author`, `license`, and `source` fields so attribution and permission context stay visible in the generated index.

滤镜包的 `manifest.json` 必须保留 `author`、`license`、`source` 字段，以便生成索引时继续展示署名、授权和来源信息。

## Maintainer Flow

1. Users submit `.opcfilter.zip` through the `Filter submission` issue form.
2. `Auto Accept Filter Submission` downloads and validates the package automatically.
3. Valid packages are committed into `packages/`, published to GitHub Pages, and the issue is closed automatically.
4. Invalid, unsafe, duplicate, or malformed packages get a failure comment and stay open for resubmission.

Manual validation is still available:

```bash
python3 tools/build_index.py --check
```

## Takedown Flow / 投诉删除流程

Original submitters can remove their own filters automatically by opening the `Filter removal request` issue form from the same GitHub account that submitted the filter. Provide the package SHA-256, cube SHA-256, package URL, or exact filter name. If the requester matches the recorded submitter, GitHub Actions deletes the matching file from `packages/`, rebuilds Pages, comments on the issue, and closes it automatically.

原投稿者可以使用同一个 GitHub 账号打开 `Filter removal request / 滤镜删除申请` 表单来自助删除自己的滤镜。填写包 SHA-256、cube SHA-256、包链接或准确滤镜名称即可。若申请账号与记录的原投稿账号一致，GitHub Actions 会自动删除 `packages/` 中对应文件、重新部署 Pages、评论并关闭 issue。

If you believe a published filter infringes your rights or violates its license, open a takedown issue in this repository and include:

- Filter name or package URL.
- Package SHA-256, cube SHA-256, or any identifying link from `public/index/v1.json`.
- The reason for the complaint and enough information to verify your claim.
- Your preferred contact method if private follow-up is needed.

如果你认为已发布滤镜侵犯了你的权利或违反授权，请在本仓库提交删除请求，并提供：

- 滤镜名称或包下载链接。
- `public/index/v1.json` 中的包 SHA-256、cube SHA-256 或其它可定位信息。
- 投诉原因，以及足以核实主张的信息。
- 如需私下跟进，请提供联系方式。

Maintainers can remove a package quickly by deleting the matching file from `packages/` and pushing to `main`. The publish workflow rebuilds `public/index/v1.json`, `public/filters/`, and `public/previews/`, so the removed package disappears from the app index after Pages redeploys.

维护者可通过删除 `packages/` 中对应的包并推送到 `main` 来快速下架。发布 workflow 会重新生成 `public/index/v1.json`、`public/filters/` 和 `public/previews/`，Pages 重新部署后 App 索引中将不再出现该包。

```bash
rm packages/<package>.opcfilter.zip
python3 tools/build_index.py --check
git add packages public
git commit -m "Remove filter: <name>"
git push origin main
```
