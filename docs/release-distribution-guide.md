# Static Rolling Releases & Extension Manifest Feeds Guide

This guide describes the standard distribution pattern for Cove extension repositories to support **static rolling-release URLs** and a **repo-wide `latest-manifest.json` feed** alongside normal versioned GitHub Releases.

---

## 1. Architectural Motivation

### Cove Host Installation Semantics
Cove installs extensions via the endpoint:
```http
POST /api/extensions/install-from-url
Content-Type: application/json

{
  "url": "https://github.com/<owner>/<repo>/releases/download/.../my-ext.zip",
  "trustUnverified": true
}
```

During installation:
1. Cove streams and extracts the `.zip` archive into memory.
2. It verifies that exactly **one** `extension.json` manifest is located at the archive root.
3. It validates manifest schemas, security permissions, compatibility constraints (`minCoveVersion`), and dependencies.
4. It copies assets to the local extensions directory and registers the extension in the running host.

### The Problem: Remote Update Tracking
- Cove does **not** persist the origin URL inside `extension.json` or track remote download sources.
- Cove does **not** natively poll upstream GitHub repositories for newer tags or versions.
- Replacing Cove's official registry configuration (`ExtensionRegistryBaseUrl`) is heavy-handed and breaks official community catalog integrations.

### The Solution: Static Rolling Releases + Manifest Feed
By configuring the repository's GitHub Actions release workflow to maintain a rolling `latest` release (`--latest=false`), multi-extension repositories provide two stable, permanent endpoints:

1. **Per-Extension Static Rolling ZIP**:
   `https://github.com/<owner>/<repo>/releases/download/latest/<extensionId>-latest.zip`
   - Always delivers the most recent build of `<extensionId>`.
   - Perfect for static bookmarks, direct curl installations, and automated single-package updaters.

2. **Repo-Wide Static Manifest Feed**:
   `https://github.com/<owner>/<repo>/releases/download/latest/latest-manifest.json`
   - Machine-readable index of all extensions published by the repository.
   - Enables in-app updaters (such as `ExtensionUpdater`) to inspect all available extensions, compare versions against installed extensions (`GET /api/extensions`), and perform one-click batch updates without hardcoding version numbers.

---

## 2. Manifest Schema (`schemaVersion: 1`)

The `latest-manifest.json` file adheres to the following specification:

```json
{
  "schemaVersion": 1,
  "updatedAt": "2026-11-14T22:00:00.000Z",
  "extensions": {
    "my-downloader-id": {
      "id": "my-downloader-id",
      "name": "My Downloader",
      "version": "0.1.2",
      "description": "Downloader for ExampleSite media streams",
      "minCoveVersion": "1.8.0",
      "downloadUrl": "https://github.com/my-org/cove-extensions/releases/download/latest/my-downloader-id-latest.zip",
      "versionedUrl": "https://github.com/my-org/cove-extensions/releases/download/my-downloader/v0.1.2/my-downloader-id-0.1.2.zip",
      "updatedAt": "2026-11-14T22:00:00.000Z"
    }
  }
}
```

### Field Definitions

| Field | Type | Description |
|---|---|---|
| `schemaVersion` | `integer` | Manifest format version (currently `1`). |
| `updatedAt` | `string` | ISO-8601 UTC timestamp of the most recent catalog update. |
| `extensions` | `object` | Dictionary of extension metadata keyed by lowercase extension `id`. |
| `extensions[id].id` | `string` | Unique extension identifier matching `extension.json`. |
| `extensions[id].name` | `string` | Human-readable extension title. |
| `extensions[id].version` | `string` | Semantic version of the latest published release. |
| `extensions[id].description` | `string` | Extension description from `extension.json`. |
| `extensions[id].minCoveVersion` | `string \| null` | Minimum compatible Cove host version. |
| `extensions[id].downloadUrl` | `string` | Static rolling-release URL (`<id>-latest.zip`). |
| `extensions[id].versionedUrl` | `string` | Specific versioned release URL for auditability or rollback. |
| `extensions[id].updatedAt` | `string` | ISO-8601 timestamp when this extension was last released. |

---

## 3. GitHub Actions Release Workflow Integration

In `.github/workflows/build.yml`, the release job runs after tagged builds (`*/v*`):

```yaml
  release:
    needs: build
    if: startsWith(github.ref, 'refs/tags/')
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v8
        with:
          merge-multiple: true

      # 1. Publish standard versioned release (e.g., my-ext/v1.0.1)
      - uses: softprops/action-gh-release@v3
        with:
          files: '*.zip'
          generate_release_notes: true

      # 2. Update rolling 'latest' release and latest-manifest.json
      - name: Update rolling latest release & manifest
        env:
          GH_TOKEN: ${{ github.token }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_REF_NAME: ${{ github.ref_name }}
        run: |
          set -euo pipefail

          # Ensure the rolling 'latest' release exists (--latest=false prevents masking primary releases)
          if ! gh release view latest >/dev/null 2>&1; then
            gh release create latest \
              --title "Latest Rolling Releases" \
              --notes "Static rolling-release ZIPs and latest-manifest.json for automatic/static-URL updates." \
              --latest=false
          fi

          # Download existing latest-manifest.json if present, or initialize empty schema
          if ! gh release download latest -p "latest-manifest.json" -O latest-manifest.json 2>/dev/null; then
            echo '{"schemaVersion":1,"extensions":{}}' > latest-manifest.json
          fi

          UPLOAD_FILES=("latest-manifest.json")

          for zip in *.zip; do
            [ -f "$zip" ] || continue
            [[ "$zip" == *-latest.zip ]] && continue

            # Extract extension.json from built package
            unzip -p "$zip" extension.json > current-extension.json
            LATEST_ZIP=$(node -e '
              const fs = require("fs");
              const ext = JSON.parse(fs.readFileSync("current-extension.json", "utf8"));
              const manifest = JSON.parse(fs.readFileSync("latest-manifest.json", "utf8"));
              manifest.schemaVersion = 1;
              manifest.updatedAt = new Date().toISOString();
              manifest.extensions = manifest.extensions || {};
              const latestZipName = `${ext.id}-latest.zip`;
              const repo = process.env.GITHUB_REPOSITORY;
              const tag = process.env.GITHUB_REF_NAME;
              manifest.extensions[ext.id] = {
                id: ext.id,
                name: ext.name || ext.id,
                version: ext.version,
                description: ext.description || "",
                minCoveVersion: ext.minCoveVersion || null,
                downloadUrl: `https://github.com/${repo}/releases/download/latest/${latestZipName}`,
                versionedUrl: `https://github.com/${repo}/releases/download/${tag}/${process.argv[1]}`,
                updatedAt: new Date().toISOString()
              };
              fs.writeFileSync("latest-manifest.json", JSON.stringify(manifest, null, 2) + "\n");
              process.stdout.write(latestZipName);
            ' "$zip")

            cp "$zip" "$LATEST_ZIP"
            UPLOAD_FILES+=("$LATEST_ZIP")
          done

          # Upload both *-latest.zip and latest-manifest.json with clobber
          gh release upload latest "${UPLOAD_FILES[@]}" --clobber
```

---

## 4. Client & In-App Updater Consumption

### How Updaters Use the Feed
Extensions such as `ExtensionUpdater` provide in-app update checks:
1. **Fetch Feed**: HTTP GET `https://github.com/<owner>/<repo>/releases/download/latest/latest-manifest.json`.
2. **Fetch Installed**: HTTP GET `/api/extensions` on the Cove host.
3. **Compare Versions**: Parse semver strings. If `manifest.version > installed.version`, an update is available.
4. **Trigger Installation**: HTTP POST to `/api/extensions/install-from-url`:
   ```json
   {
     "url": "https://github.com/<owner>/<repo>/releases/download/latest/<id>-latest.zip",
     "trustUnverified": true
   }
   ```
5. **Reload**: Cove hot-reloads or prompts the user to reload the desktop window.
