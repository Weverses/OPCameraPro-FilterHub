#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import shutil
import time
import zipfile
from pathlib import Path

SCHEMA_VERSION = 1
BUNDLE_TYPE = "opcamerapro-filter"
ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"
PUBLIC_DIR = ROOT / "public"
PUBLIC_INDEX_DIR = PUBLIC_DIR / "index"
PUBLIC_FILTERS_DIR = PUBLIC_DIR / "filters"
PUBLIC_PREVIEWS_DIR = PUBLIC_DIR / "previews"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-._")
    return slug or "filter"


def read_package(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if len(names) != len(set(names)):
            raise ValueError(f"{path}: duplicate zip entries")
        if "manifest.json" not in names or "filter.cube" not in names:
            raise ValueError(f"{path}: missing manifest.json or filter.cube")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if manifest.get("schemaVersion") != SCHEMA_VERSION:
            raise ValueError(f"{path}: unsupported schema")
        if manifest.get("bundleType") != BUNDLE_TYPE:
            raise ValueError(f"{path}: unsupported bundleType")
        cube = archive.read("filter.cube")
        if sha256_bytes(cube) != manifest.get("cubeSha256"):
            raise ValueError(f"{path}: cube checksum mismatch")
        if len(cube) != manifest.get("cubeSize"):
            raise ValueError(f"{path}: cube size mismatch")
        preview = None
        preview_path = manifest.get("previewPath")
        if preview_path:
            preview = archive.read(preview_path)
            if sha256_bytes(preview) != manifest.get("previewSha256"):
                raise ValueError(f"{path}: preview checksum mismatch")
            if len(preview) != manifest.get("previewSize"):
                raise ValueError(f"{path}: preview size mismatch")
        return {"manifest": manifest, "preview": preview}


def build_index() -> dict:
    shutil.rmtree(PUBLIC_FILTERS_DIR, ignore_errors=True)
    shutil.rmtree(PUBLIC_PREVIEWS_DIR, ignore_errors=True)
    PUBLIC_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_FILTERS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)

    filters = []
    for package_path in sorted(PACKAGES_DIR.glob("*.opcfilter.zip")):
        package = read_package(package_path)
        manifest = package["manifest"]
        package_sha = sha256_file(package_path)
        package_size = package_path.stat().st_size
        public_package = PUBLIC_FILTERS_DIR / f"{package_sha}.opcfilter.zip"
        shutil.copyfile(package_path, public_package)

        preview_url = None
        preview_sha = None
        if package["preview"] is not None:
            preview_sha = sha256_bytes(package["preview"])
            public_preview = PUBLIC_PREVIEWS_DIR / f"{package_sha}.jpg"
            public_preview.write_bytes(package["preview"])
            preview_url = f"../previews/{package_sha}.jpg"

        filters.append(
            {
                "id": f"{slugify(package_path.name.removesuffix('.opcfilter.zip'))}-{package_sha[:8]}",
                "displayName": manifest["displayName"],
                "author": manifest.get("author", ""),
                "description": manifest.get("description", ""),
                "version": "1",
                "tags": manifest.get("tags", []),
                "license": manifest.get("license", ""),
                "packageUrl": f"../filters/{package_sha}.opcfilter.zip",
                "packageSha256": package_sha,
                "packageSize": package_size,
                "cubeSha256": manifest["cubeSha256"],
                "previewUrl": preview_url,
                "previewSha256": preview_sha,
            }
        )

    index = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": int(time.time() * 1000),
        "filters": filters,
    }
    (PUBLIC_INDEX_DIR / "v1.json").write_text(
        json.dumps(index, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Build and validate the index")
    parser.parse_args()
    index = build_index()
    print(f"Built {len(index['filters'])} filter entries")


if __name__ == "__main__":
    main()
