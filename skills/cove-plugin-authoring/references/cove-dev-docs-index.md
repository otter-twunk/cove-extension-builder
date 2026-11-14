# Cove Developer Documentation & Knowledge Recall Index

This index provides instant recall and fast lookup of official Cove developer documentation, architecture guides, and production reference implementations available in the local upstream repositories and documentation sites.

---

## 1. Official Documentation Structure (`docs-site`)

The official documentation site sources are located at `/Users/kari/cove-dev/upstream/docs-site/src/content/docs/docs/` (matching `https://yourcove.org/docs/` and `https://yourcove.net/docs/`).

### Developer Core Guides

| Document Path | Topic & Key Concepts |
|---|---|
| `docs/developer/index.mdx` | **Developer Overview**: Architectural philosophy, local-first design, extensibility principles. |
| `docs/developer/extensions/overview.mdx` | **Extension Architecture**: Host boundaries, capabilities (UI pages, panels, tabs, backend APIs, jobs, themes, storage). |
| `docs/developer/extensions/extension-points.mdx` | **Extension Point Catalog**: Exhaustive catalog of backend capabilities (`IApiExtension`, `IMiddlewareExtension`, `IJobExtension`, `IBackgroundExtension`, `IEventExtension`, `IScanParticipant`, `IExtensionEntityFilterProvider`), service exchange, and SDK bases. |
| `docs/developer/extensions/ui-extension-points.mdx` | **UI Extension Points**: Additive UI, personal dashboard widgets (`UIDashboardWidgetContribution`), login methods, named slots, entity media overrides (`entity.media`), settings tabs/panels, keyboard actions, and in-app feature guides. |
| `docs/developer/extensions/frontend-runtime.mdx` | **Frontend Runtime API**: Virtual module map (`@cove/runtime/*`), WebXR immersive playback (`@cove/runtime/webxr`), `extensionFetch` client, and shared components barrel (`@cove/runtime/components`). |
| `docs/developer/extensions/events.mdx` | **Extension Events**: Best-effort process-local event delivery, canonical `noun.verb` event naming (`video.created`, `audio.updated`, `rating.deleted`), and rating data payloads. |
| `docs/developer/extensions/permissions.mdx` | **Permissions & Security**: Manifest declarations (`network`, `scraperRuntime`, `downloaderRuntime`), assignable role permissions (`IPermissionContributor`), and Minimal API endpoint authorization conventions (`RequireCovePermission`, `RequireCoveEntityAccess`). |
| `docs/developer/extensions/packaging.mdx` | **Packaging Specifications**: Archive layout rules, manifest single source of truth in `extension.json`, semantic dependencies, `minCoveVersion` enforcement, release validation, static rolling-release URLs (`<id>-latest.zip`), and repo-wide manifest feeds (`latest-manifest.json`). |
| `docs/developer/extensions/create-extension.mdx` | **Create an Extension**: Defining user-facing behavior, splitting frontend vs backend, pre-built artifact packaging. |
| `docs/developer/extensions/create-downloader.mdx` | **Downloader Guide**: `IDownloaderProvider`, progress reporting, quality options (`Width`, `Height`), max resolution clamping (`MaxHeight`), temporary file handling. |
| `docs/developer/extensions/create-scraper.mdx` | **Scraper Guide**: `IScraperProvider`, native YAML scrapers, URL and text querying, provenance attribution, `ScraperPermissions.AllowNetworkHosts`. |
| `docs/developer/api/overview.mdx` | **API Surface Principles**: Unversioned `/api/` base routes, OpenAPI discovery at `/openapi/v1.json` (dev mode only), bearer API tokens with scoped permissions, pagination, and `skipCount`. |
| `docs/developer/getting-started/local-development.mdx` | **Local Environment**: Running Cove backend (.NET 10) & frontend (Vite/React 19), dev environment configuration. |
| `docs/developer/architecture/logging.mdx` | **Logging Architecture**: Structured logging, category names, log levels, and performance tracing. |

---

## 2. Cove Host Architecture & In-Tree Documentation

Located at `/Users/kari/cove-dev/upstream/cove/docs/`:

### Key Specifications & Contracts
- **Feature Guides Schema**: `/Users/kari/cove-dev/upstream/cove/docs/feature-guides/schema.json`
  - JSON schema for writing in-app User Guide topics and articles packaged via `featureGuides: [...]` in `extension.json`.
- **Entity Merging & Deduplication**: `/Users/kari/cove-dev/upstream/cove/docs/contributing/entity-merge-contract.md`
  - Explains how performers, tags, and scenes merge while preserving metadata provenance and custom field values.
- **Video Cutting & Shot Boundaries**: `/Users/kari/cove-dev/upstream/cove/docs/video-cutting.md`
  - Explains video trim previews, cutting jobs, and gapless partition storage (`IVideoShotService`).
- **Interactive Feature Guides & Storyboards**: `/Users/kari/cove-dev/upstream/cove/docs/feature-guides/`
  - Contains over 40 structured JSON definitions detailing Cove user flows, UI layouts, keyboard shortcuts, filters, and custom fields.

---

## 3. Native Desktop App Context (Windows / macOS)

In the user's environment, Cove runs as a native desktop application rather than a remote cloud server. This imposes specific constraints:

1. **Embedded Host Process**:
   - The backend runs as a local process serving an embedded loopback API.
   - Frontend React components render in an embedded WebView shell.
2. **Local Storage**:
   - Databases are local (embedded SQLite or local PostgreSQL instance).
   - `IExtensionStore` writes to the local Cove data directory.
   - File downloads and processing occur on the local workstation filesystem.
3. **Packaging & Installation**:
   - Packaged `.zip` files are installed via **Settings › Extensions › Install from URL / File**.
   - The package must be completely self-contained: compiled C# DLLs, bundled ESM frontend (`dist/bundle.js` + `dist/bundle.css`), and `extension.json` at the root.
   - Host assemblies (`Cove.Sdk.dll`, `Cove.Core.dll`, `Cove.Plugins.dll`, EF Core, Npgsql) must **never** be included in the zip.

---

## 4. Production Reference Implementations in Upstream Repositories

When designing new extensions, inspect these real-world upstream implementations for battle-tested patterns:

### UI & Tool Extensions (`cove-extensions-ui`)
Path: `/Users/kari/cove-dev/upstream/cove-extensions-ui/extensions/`
- **`CustomHomePage`**: Overriding standard Cove pages (`UIPageOverride` targeting `"home"` at Priority 200) with a custom React dashboard.
- **`SceneAnalytics`**: Multi-capability extension combining `IUIExtension` (detail tab), `IApiExtension` (minimal endpoints), and `IStatefulExtension` (`IExtensionStore` play count tracking).
- **`Audios`**: Full entity management extension adding dedicated list pages, player controls, custom filter criteria, and settings panels.

### AI, Background Jobs & Vector Embeddings (`AI.Extensions`)
Path: `/Users/kari/cove-dev/upstream/AI.Extensions/extensions/`
- **`AI.Core`**: Extension service exchange patterns, custom database entities, and migrations via `DataExtensionBase`.
- **`AI.Visual` / `AI.Faces` / `AI.Audio`**: Registering background jobs via `JobExtensionBase`, reporting progress with `IJobProgress`, and subscribing to entity events with `EventExtensionBase`.

### Recommendation Engine (`recommendations`)
Path: `/Users/kari/cove-dev/upstream/recommendations/extensions/`
- **`Recommendations.Core`**: Precomputed background jobs, custom list filters (`AddExtensionListFilter`), custom list sorts (`AddListSort`), and multi-tab frontend integration.
