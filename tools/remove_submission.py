#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import build_index
import ingest_submission

ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"
ISSUE_FIELD_ALIASES = {
    "filter_identifier": ("filter identifier", "滤镜标识"),
    "reason": ("reason", "原因"),
}
HEX_64_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")
ISSUE_NUMBER_RE = re.compile(r"issue\s+#(\d+)", re.IGNORECASE)


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


def extract_issue_fields(issue_body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    matches = list(ingest_submission.ISSUE_HEADING_RE.finditer(issue_body or ""))
    for index, match in enumerate(matches):
        heading = match.group(1).strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(issue_body or "")
        value = ingest_submission.clean_issue_field_value((issue_body or "")[start:end])
        if not value:
            continue
        for key, aliases in ISSUE_FIELD_ALIASES.items():
            if any(alias in heading for alias in aliases):
                fields[key] = value
                break
    return fields


def package_index_id(package_path: Path, package_sha: str) -> str:
    return f"{build_index.slugify(package_path.name.removesuffix('.opcfilter.zip'))}-{package_sha[:8]}"


def package_matches_identifier(package_path: Path, manifest: dict, package_sha: str, identifier: str) -> bool:
    needle = identifier.strip().lower()
    if not needle:
        return False
    cube_sha = manifest.get("cubeSha256", "").lower()
    candidates = {
        package_sha.lower(),
        cube_sha,
        package_path.name.lower(),
        str(package_path.relative_to(ROOT)).lower(),
        package_index_id(package_path, package_sha).lower(),
        manifest.get("displayName", "").lower(),
    }
    explicit_hashes = {value.lower() for value in HEX_64_RE.findall(identifier)}
    if explicit_hashes and (package_sha.lower() in explicit_hashes or cube_sha in explicit_hashes):
        return True
    return needle in candidates or package_sha.lower() in needle or cube_sha in needle


def find_matching_package(identifier: str) -> dict:
    matches = []
    for package_path in sorted(PACKAGES_DIR.glob("*.opcfilter.zip")):
        package = build_index.read_package(package_path)
        manifest = package["manifest"]
        package_sha = build_index.sha256_file(package_path)
        if package_matches_identifier(package_path, manifest, package_sha, identifier):
            matches.append(
                {
                    "path": package_path,
                    "manifest": manifest,
                    "packageSha256": package_sha,
                    "cubeSha256": manifest["cubeSha256"],
                }
            )
    if not matches:
        raise SystemExit("No matching filter package found")
    if len(matches) > 1:
        names = ", ".join(match["path"].name for match in matches)
        raise SystemExit(f"More than one filter matched; use packageSha256 or cubeSha256: {names}")
    return matches[0]


def git_log_subjects(package_path: Path) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%s", "--", str(package_path.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def submission_issue_from_git(package_path: Path) -> int:
    for subject in git_log_subjects(package_path):
        match = ISSUE_NUMBER_RE.search(subject)
        if match:
            return int(match.group(1))
    return 0


def resolve_submitter(match: dict, repo: str, token: str) -> tuple[str, int]:
    manifest = match["manifest"]
    submitter = str(manifest.get("submitterGitHub", "")).strip()
    issue_number = build_index.int_manifest_value(manifest, "submissionIssue")
    if submitter:
        return submitter, issue_number

    if issue_number <= 0:
        issue_number = submission_issue_from_git(match["path"])
    if issue_number <= 0:
        return "", 0

    issue = fetch_issue(repo, issue_number, token)
    return issue.get("user", {}).get("login", ""), issue_number


def remove_package(match: dict, dry_run: bool) -> dict:
    package_path = match["path"]
    manifest = match["manifest"]
    if not dry_run:
        package_path.unlink()
    return {
        "status": "ready" if dry_run else "removed",
        "displayName": manifest.get("displayName", ""),
        "target": str(package_path.relative_to(ROOT)),
        "packageSha256": match["packageSha256"],
        "cubeSha256": match["cubeSha256"],
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
    requestor = issue.get("user", {}).get("login", "")
    fields = extract_issue_fields(issue.get("body", ""))
    identifier = fields.get("filter_identifier", "")
    if not identifier:
        raise SystemExit("Missing filter identifier")

    match = find_matching_package(identifier)
    submitter, submission_issue = resolve_submitter(match, args.repo, args.token)
    if not submitter:
        raise SystemExit("Unable to determine original submitter for this filter")
    if submitter.lower() != requestor.lower():
        raise SystemExit(
            f"Requester @{requestor} is not the original submitter @{submitter}; self-service removal denied"
        )

    result = remove_package(match, dry_run=args.dry_run)
    result["requestor"] = requestor
    result["submitterGitHub"] = submitter
    result["submissionIssue"] = submission_issue
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
