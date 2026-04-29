#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import build_index

ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"
MAX_DOWNLOAD_BYTES = 24 * 1024 * 1024
ATTACHMENT_URL_RE = re.compile(r"https://[^\s)\]]+\.opcfilter\.zip", re.IGNORECASE)
ISSUE_HEADING_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)

ISSUE_FIELD_ALIASES = {
    "display_name": ("display name", "显示名称"),
    "author": ("author", "作者"),
    "description": ("description", "描述"),
    "source": ("source", "来源"),
    "license": ("license", "授权"),
}


def github_request(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "OPCameraPro-FilterHub",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_issue(repo: str, issue_number: int, token: str) -> dict:
    return github_request(f"https://api.github.com/repos/{repo}/issues/{issue_number}", token)


def extract_package_urls(issue_body: str) -> list[str]:
    urls = []
    for match in ATTACHMENT_URL_RE.finditer(issue_body or ""):
        url = match.group(0).strip().rstrip(".,")
        if url not in urls:
            urls.append(url)
    return urls


def clean_issue_field_value(value: str, max_length: int = 2000) -> str:
    normalized = "\n".join(line.rstrip() for line in value.splitlines()).strip()
    return normalized[:max_length].strip()


def extract_issue_fields(issue_body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    matches = list(ISSUE_HEADING_RE.finditer(issue_body or ""))
    for index, match in enumerate(matches):
        heading = match.group(1).strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(issue_body or "")
        value = clean_issue_field_value((issue_body or "")[start:end])
        if not value:
            continue
        for key, aliases in ISSUE_FIELD_ALIASES.items():
            if any(alias in heading for alias in aliases):
                fields[key] = value
                break
    return fields


def metadata_value(fields: dict[str, str], key: str, fallback: str = "", max_length: int = 2000) -> str:
    return clean_issue_field_value(fields.get(key, fallback), max_length=max_length)


def rewrite_package_metadata(
    source_path: Path,
    target_path: Path,
    issue_fields: dict[str, str],
    submitter_github: str = "",
    submission_issue: int = 0,
) -> None:
    package = build_index.read_package(source_path)
    manifest = dict(package["manifest"])

    display_name = metadata_value(issue_fields, "display_name", manifest.get("displayName", ""), 120)
    author = metadata_value(issue_fields, "author", manifest.get("author", ""), 120)
    description = metadata_value(issue_fields, "description", manifest.get("description", ""), 2000)
    source = metadata_value(issue_fields, "source", manifest.get("source", ""), 2000)
    license_name = metadata_value(issue_fields, "license", manifest.get("license", ""), 200)

    if display_name:
        manifest["displayName"] = display_name
    manifest["author"] = author
    manifest["description"] = description
    manifest["source"] = source
    manifest["license"] = license_name
    manifest["submitterGitHub"] = submitter_github
    manifest["submissionIssue"] = submission_issue

    with zipfile.ZipFile(source_path) as archive:
        entries = {
            build_index.normalize_package_path(name): archive.read(name)
            for name in archive.namelist()
            if not name.endswith("/")
        }

    entries["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=True, indent=2) + "\n"
    ).encode("utf-8")
    if manifest.get("licensePath") == "LICENSE.txt":
        existing_license = entries.get("LICENSE.txt", b"").decode("utf-8", errors="replace")
        if "unspecified" in existing_license.lower() or not existing_license.strip():
            entries["LICENSE.txt"] = (
                f"License: {license_name or 'Unspecified'}\n"
                f"Author: {author or 'Unknown'}\n"
                f"Source: {source or 'Unspecified'}\n"
            ).encode("utf-8")

    ordered_names = ["manifest.json", "filter.cube", "preview.jpg", "LICENSE.txt"]
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ordered_names:
            if name in entries:
                archive.writestr(name, entries[name])


def download_package(url: str, target: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "OPCameraPro-FilterHub"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise RuntimeError(f"HTTP {status}")
            total = 0
            with target.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise RuntimeError("Package attachment is too large")
                    output.write(chunk)
    except urllib.error.URLError as error:
        raise RuntimeError(f"Unable to download package attachment: {error}") from error


def existing_cube_hashes() -> set[str]:
    hashes = set()
    for package_path in sorted(PACKAGES_DIR.glob("*.opcfilter.zip")):
        package = build_index.read_package(package_path)
        hashes.add(package["manifest"]["cubeSha256"])
    return hashes


def ingest_package(source_path: Path, dry_run: bool) -> dict:
    package = build_index.read_package(source_path)
    manifest = package["manifest"]
    package_sha = build_index.sha256_file(source_path)
    cube_sha = manifest["cubeSha256"]
    duplicate = cube_sha in existing_cube_hashes()
    if duplicate:
        return {
            "status": "duplicate",
            "displayName": manifest["displayName"],
            "packageSha256": package_sha,
            "cubeSha256": cube_sha,
        }

    target_name = f"{build_index.slugify(manifest['displayName'])}-{package_sha[:12]}.opcfilter.zip"
    target_path = PACKAGES_DIR / target_name
    if target_path.exists():
        return {
            "status": "exists",
            "displayName": manifest["displayName"],
            "target": str(target_path.relative_to(ROOT)),
            "packageSha256": package_sha,
            "cubeSha256": cube_sha,
        }

    if not dry_run:
        PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)

    return {
        "status": "ready" if dry_run else "added",
        "displayName": manifest["displayName"],
        "author": manifest.get("author", ""),
        "license": manifest.get("license", ""),
        "submitterGitHub": manifest.get("submitterGitHub", ""),
        "submissionIssue": manifest.get("submissionIssue", 0),
        "target": str(target_path.relative_to(ROOT)),
        "packageSha256": package_sha,
        "cubeSha256": cube_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.repo:
        raise SystemExit("Missing --repo or GITHUB_REPOSITORY")
    if not args.token:
        raise SystemExit("Missing --token or GITHUB_TOKEN")

    issue = fetch_issue(args.repo, args.issue, args.token)
    submitter_github = issue.get("user", {}).get("login", "")
    issue_fields = extract_issue_fields(issue.get("body", ""))
    issue_fields.setdefault("author", submitter_github)
    urls = extract_package_urls(issue.get("body", ""))
    if not urls:
        raise SystemExit("No .opcfilter.zip attachment URL found in the issue body")
    if len(urls) > 1:
        raise SystemExit("Please submit exactly one .opcfilter.zip attachment per issue")

    with tempfile.TemporaryDirectory(prefix="filterhub_submission_") as temp_dir:
        package_path = Path(temp_dir) / "submission.opcfilter.zip"
        enriched_path = Path(temp_dir) / "submission_enriched.opcfilter.zip"
        download_package(urls[0], package_path)
        rewrite_package_metadata(
            package_path,
            enriched_path,
            issue_fields,
            submitter_github=submitter_github,
            submission_issue=args.issue,
        )
        result = ingest_package(enriched_path, dry_run=args.dry_run)

    print(json.dumps(result, ensure_ascii=True, indent=2))
    if result["status"] in {"duplicate", "exists"}:
        raise SystemExit("This LUT or package already exists in packages/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
