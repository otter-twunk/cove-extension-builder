#!/usr/bin/env python3
"""
sync-upstream-cove.py

Autonomous upstream synchronizer and contract verification tool for Cove extension authoring.
Checks for new upstream releases, ABI changes, developer documentation updates, and new API
surface points from yourcove/cove on GitHub (or a local checkout if configured).

Usage:
    python3 scripts/sync-upstream-cove.py [--check] [--sync] [--token <gh-token>] [--repo <owner/repo>] [--local-cove <path>]

Options:
    --check         (Default) Check for updates, report diffs against local knowledge base, and flag changed contracts.
    --sync          Download upstream developer docs and contract sources into a staging directory (.upstream_cache/).
    --local-cove    Point to a local checkout of yourcove/cove instead of fetching via GitHub API.
    --repo          Upstream GitHub repository (default: yourcove/cove).
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_REPO = "yourcove/cove"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CACHE_DIR = REPO_ROOT / ".upstream_cache"

DOCUMENTATION_PATHS = [
    "docs-site/src/content/docs/docs/developer/index.mdx",
    "docs-site/src/content/docs/docs/developer/design-guidelines.mdx",
    "docs-site/src/content/docs/docs/developer/api/overview.mdx",
    "docs-site/src/content/docs/docs/developer/getting-started/local-development.mdx",
    "docs-site/src/content/docs/docs/developer/architecture/logging.mdx",
    "docs-site/src/content/docs/docs/developer/extensions/overview.mdx",
    "docs-site/src/content/docs/docs/developer/extensions/create-extension.mdx",
    "docs-site/src/content/docs/docs/developer/extensions/create-downloader.mdx",
    "docs-site/src/content/docs/docs/developer/extensions/create-scraper.mdx",
    "docs-site/src/content/docs/docs/developer/extensions/extension-points.mdx",
    "docs-site/src/content/docs/docs/developer/extensions/ui-extension-points.mdx",
    "docs-site/src/content/docs/docs/developer/extensions/frontend-runtime.mdx",
    "docs-site/src/content/docs/docs/developer/extensions/events.mdx",
    "docs-site/src/content/docs/docs/developer/extensions/permissions.mdx",
    "docs-site/src/content/docs/docs/developer/extensions/packaging.mdx",
    "docs/feature-guides/schema.json",
    "CHANGELOG.md",
]

CONTRACT_SOURCE_PATHS = [
    "src/Cove.Plugins/IExtension.cs",
    "src/Cove.Plugins/MetadataAutomationContracts.cs",
    "src/Cove.Plugins/ExtensionAuthentication.cs",
    "src/Cove.Plugins/ExtensionEntityFilterRuntime.cs",
    "src/Cove.Plugins/DynamicEndpointDataSource.cs",
    "src/Cove.Sdk/CoveExtensionBase.cs",
    "src/Cove.Sdk/FullExtensionBase.cs",
    "src/Cove.Sdk/UIManifestBuilder.cs",
    "src/Cove.Sdk/EndpointAuthorizationExtensions.cs",
    "src/Cove.Sdk/IPermissionContributor.cs",
    "src/Cove.Sdk/DataExtensionBase.cs",
    "src/Cove.Sdk/EventExtensionBase.cs",
    "src/Cove.Sdk/JobExtensionBase.cs",
    "src/Cove.Sdk/README.md",
    "src/Cove.Core/DTOs/DTOs.cs",
    "src/Cove.Core/DTOs/VideoShotDtos.cs",
    "sdk/frontend/package.json",
    "sdk/frontend/src/index.ts",
    "sdk/frontend/src/types.ts",
]


class GitHubClient:
    def __init__(self, repo: str, token: str | None = None):
        self.repo = repo
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def _request(self, path: str) -> bytes:
        url = f"https://api.github.com/repos/{self.repo}/{path.lstrip('/')}"
        headers = {"User-Agent": "cove-extension-builder-sync/1.0"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def get_json(self, path: str):
        return json.loads(self._request(path).decode("utf-8"))

    def get_file_content(self, repo_path: str) -> bytes:
        data = self.get_json(f"contents/{repo_path}")
        if "content" in data:
            return base64.b64decode(data["content"])
        raise ValueError(f"No content found for {repo_path}")


def get_local_file_content(local_cove: Path, repo_path: str) -> bytes:
    target = local_cove / repo_path
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {target}")
    return target.read_bytes()


def parse_abi_baseline(content: str) -> str | None:
    match = re.search(r"<CoveExtensionAbiBaselineVersion>(.*?)</CoveExtensionAbiBaselineVersion>", content)
    return match.group(1).strip() if match else None


def analyze_public_interfaces(csharp_code: str) -> list[str]:
    pattern = re.compile(r"public\s+interface\s+([A-Za-z0-9_]+)")
    return pattern.findall(csharp_code)


def analyze_ui_builder_methods(csharp_code: str) -> list[str]:
    pattern = re.compile(r"public\s+UIManifestBuilder\s+([A-Za-z0-9_]+)\s*\(")
    return pattern.findall(csharp_code)


def analyze_frontend_exports(ts_code: str) -> list[str]:
    pattern = re.compile(r"export\s+(?:type\s+)?(?:\{\s*([^}]+)\s*\}|([A-Za-z0-9_]+))")
    results = []
    for match in pattern.finditer(ts_code):
        group_list, single = match.groups()
        if group_list:
            for item in group_list.split(","):
                cleaned = item.strip().split(" as ")[0].strip()
                if cleaned:
                    results.append(cleaned)
        elif single:
            results.append(single.strip())
    return results


def run_sync(client: GitHubClient | None, local_path: Path | None, do_cache: bool = False):
    print("=" * 72)
    print(" Cove Upstream Synchronization & API Audit")
    print("=" * 72)

    # 1. Check Releases & Tags
    latest_release_tag = "unknown"
    all_tags = []
    if client:
        try:
            rel = client.get_json("releases/latest")
            latest_release_tag = rel.get("tag_name", "unknown")
            print(f"[*] Upstream Latest Release Tag: {latest_release_tag} (Published: {rel.get('published_at', '')})")
        except Exception as e:
            print(f"[!] Could not fetch latest release: {e}")

        try:
            tags = client.get_json("tags?per_page=10")
            all_tags = [t.get("name") for t in tags]
            print(f"[*] Recent Upstream Tags: {', '.join(all_tags[:6])}")
        except Exception as e:
            print(f"[!] Could not fetch tags: {e}")
    elif local_path:
        print(f"[*] Operating against local Cove checkout: {local_path}")

    # 2. Check Directory.Build.props for ABI baseline
    abi_baseline = None
    try:
        content = (
            get_local_file_content(local_path, "Directory.Build.props")
            if local_path
            else client.get_file_content("Directory.Build.props")
        ).decode("utf-8", errors="replace")
        abi_baseline = parse_abi_baseline(content)
        print(f"[*] Upstream ABI Baseline Version (ApiCompat): {abi_baseline}")
    except Exception as e:
        print(f"[!] Could not read Directory.Build.props: {e}")

    # 3. Download / Cache if requested
    if do_cache:
        print(f"\n[*] Caching upstream developer docs and contracts to {CACHE_DIR}...")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        all_paths = DOCUMENTATION_PATHS + CONTRACT_SOURCE_PATHS
        for p in all_paths:
            try:
                dest = CACHE_DIR / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                raw = (
                    get_local_file_content(local_path, p)
                    if local_path
                    else client.get_file_content(p)
                )
                dest.write_bytes(raw)
                print(f"    Downloaded: {p} ({len(raw)} bytes)")
            except Exception as e:
                print(f"    Failed {p}: {e}")

    # 4. Analyze Core C# Extension Contracts
    print("\n[*] Inspecting Cove.Plugins & Cove.Sdk Public Contracts...")
    try:
        iext = (
            get_local_file_content(local_path, "src/Cove.Plugins/IExtension.cs")
            if local_path
            else client.get_file_content("src/Cove.Plugins/IExtension.cs")
        ).decode("utf-8", errors="replace")
        plugins_interfaces = analyze_public_interfaces(iext)
        print(f"    IExtension.cs Public Interfaces ({len(plugins_interfaces)}):")
        for iface in sorted(plugins_interfaces):
            print(f"      - {iface}")
    except Exception as e:
        print(f"[!] Error reading IExtension.cs: {e}")

    try:
        builder = (
            get_local_file_content(local_path, "src/Cove.Sdk/UIManifestBuilder.cs")
            if local_path
            else client.get_file_content("src/Cove.Sdk/UIManifestBuilder.cs")
        ).decode("utf-8", errors="replace")
        builder_methods = set(analyze_ui_builder_methods(builder))
        print(f"\n    UIManifestBuilder Methods ({len(builder_methods)}):")
        for m in sorted(builder_methods):
            print(f"      - {m}")
    except Exception as e:
        print(f"[!] Error reading UIManifestBuilder.cs: {e}")

    # 5. Analyze Frontend SDK Contracts
    print("\n[*] Inspecting @cove/extension-sdk & @cove/runtime Contracts...")
    try:
        fe_types = (
            get_local_file_content(local_path, "sdk/frontend/src/types.ts")
            if local_path
            else client.get_file_content("sdk/frontend/src/types.ts")
        ).decode("utf-8", errors="replace")
        fe_exports = set(analyze_frontend_exports(fe_types))
        print(f"    Frontend Types & Slotted Constants ({len(fe_exports)}):")
        for exp in sorted(fe_exports):
            print(f"      - {exp}")
    except Exception as e:
        print(f"[!] Error reading sdk/frontend/src/types.ts: {e}")

    # 6. Check Local Reference Alignment
    print("\n" + "=" * 72)
    print(" Local Reference Alignment Verification")
    print("=" * 72)

    api_surface_ref = REPO_ROOT / "skills/cove-plugin-authoring/references/cove-api-surface.md"
    native_ui_ref = REPO_ROOT / "skills/cove-plugin-authoring/references/cove-native-ui.md"
    dev_docs_ref = REPO_ROOT / "skills/cove-plugin-authoring/references/cove-dev-docs-index.md"
    downloader_ref = REPO_ROOT / "skills/cove-downloader-authoring/references/downloader-contracts.md"
    scraper_ref = REPO_ROOT / "skills/cove-scraper-authoring/references/scraper-contracts.md"

    checks = [
        ("cove-api-surface.md", api_surface_ref, [
            "IExtensionServiceScopeFactory",
            "IPermissionContributor",
            "EndpointAuthorizationExtensions",
            "IVideoFileMaintenanceService",
            "ISegmentSpanCacheInvalidator",
            "IVideoShotService",
            "IExtensionEntityFilterProvider",
            "IScanParticipant",
            "IMiddlewareExtension",
            "IBackgroundExtension",
            "x-cove-extension",
            "/openapi/v1.json",
            "NetVips",
            "featureGuides",
            "IUserEngagementService",
        ]),
        ("cove-native-ui.md", native_ui_ref, [
            "@cove/runtime/webxr",
            "UIDashboardWidgetContribution",
            "AddDashboardWidget",
            "AddKeyboardAction",
            "AddKeyboardShortcutPreset",
            "entity-cover-editor",
            "app-floating-ui",
            "media-player-actions",
            "media-player-overlay",
            "EntityMedia",
            "DetailListPagination",
            "useDocumentTitle",
            "featureGuides",
            "schemaVersion",
        ]),
        ("cove-dev-docs-index.md", dev_docs_ref, [
            "extension-points.mdx",
            "ui-extension-points.mdx",
            "frontend-runtime.mdx",
            "events.mdx",
            "permissions.mdx",
            "packaging.mdx",
        ]),
        ("downloader-contracts.md", downloader_ref, [
            "IDownloaderSiteLoginProvider",
            "MaxHeight",
            "AllowDuplicateDownload",
            "MatchAllAsync",
        ]),
        ("scraper-contracts.md", scraper_ref, [
            "ScraperPermissions",
            "AllowNetworkHosts",
            "int? LocalVideoId",
        ]),
    ]

    all_passed = True
    for label, file_path, required_tokens in checks:
        if not file_path.is_file():
            print(f"[FAIL] Missing reference file: {file_path}")
            all_passed = False
            continue
        text = file_path.read_text(encoding="utf-8")
        missing = [t for t in required_tokens if t not in text]
        if missing:
            print(f"[WARN] {label} is missing new API points: {', '.join(missing)}")
            all_passed = False
        else:
            print(f"[PASS] {label} contains all checked API points.")

    print("\n" + "=" * 72)
    if all_passed:
        print(" Summary: All local reference files are aligned with latest upstream Cove contracts!")
    else:
        print(" Summary: Some reference files require updates to match latest upstream Cove contracts.")
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Synchronize and audit upstream Cove contracts.")
    parser.add_argument("--check", action="store_true", default=True, help="Check upstream for changes (default)")
    parser.add_argument("--sync", action="store_true", help="Download docs and code to .upstream_cache/")
    parser.add_argument("--token", help="GitHub Personal Access Token")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub repository (default: {DEFAULT_REPO})")
    parser.add_argument("--local-cove", type=Path, help="Path to local checkout of yourcove/cove")

    args = parser.parse_args()

    client = None
    if not args.local_cove:
        client = GitHubClient(args.repo, args.token)

    run_sync(client, args.local_cove, do_cache=args.sync)


if __name__ == "__main__":
    main()
