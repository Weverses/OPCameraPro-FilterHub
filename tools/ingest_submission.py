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
from pathlib import Path

import build_index

ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"
MAX_DOWNLOAD_BYTES = 24 * 1024 * 1024
ATTACHMENT_URL_RE = re.compile(r"https://[^\s)\]]+\.opcfilter\.zip", re.IGNORECASE)


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
    urls = extract_package_urls(issue.get("body", ""))
    if not urls:
        raise SystemExit("No .opcfilter.zip attachment URL found in the issue body")
    if len(urls) > 1:
        raise SystemExit("Please submit exactly one .opcfilter.zip attachment per issue")

    with tempfile.TemporaryDirectory(prefix="filterhub_submission_") as temp_dir:
        package_path = Path(temp_dir) / "submission.opcfilter.zip"
        download_package(urls[0], package_path)
        result = ingest_package(package_path, dry_run=args.dry_run)

    print(json.dumps(result, ensure_ascii=True, indent=2))
    if result["status"] == "duplicate":
        raise SystemExit("This LUT already exists in packages/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
