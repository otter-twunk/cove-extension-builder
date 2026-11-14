# Cove Upstream Synchronization & Versioning Guide

This guide establishes the recurring procedure and architectural rules for reviewing, auditing, and synchronizing `cove-extension-builder` with upstream updates to [Cove](https://github.com/yourcove/cove) (`yourcove/cove`).

---

## 1. Upstream Versioning Architecture

Understanding Cove's versioning model is essential for writing compatible extensions and maintaining this authoring suite:

```mermaid
graph TD
    Host[Running Cove Host e.g. v1.7.0] -->|Enforces minCoveVersion| Package[Extension Package: extension.json]
    Host -->|Loads in isolated ALC| ExtALC[Extension AssemblyLoadContext]
    Host -->|Supplies compile-only closure| SharedABI[Extension ABI: Cove.Core / Cove.Plugins / Cove.Sdk]
    SharedABI -->|ApiCompat checked against| Baseline[ABI Baseline: v1.4.1]
    Host -->|Supplies Virtual ESM Map| RuntimeMap[@cove/runtime/* v1]
```

### Core Release Lifecycle & Semantic Versioning
- **Release Versioning**: Follows Semantic Versioning (`MAJOR.MINOR.PATCH`). Stable releases are tagged on GitHub (e.g. `v1.6.0`, `v1.6.1`, `v1.7.0`).
- **Development Builds**: Prereleases use suffixes such as `1.7.1-dev.42` or `1.6.1-rc.1`.
- **`minCoveVersion`**: Declared in `extension.json`.
  - Compared against the **running Cove version** at install time.
  - The native ZIP and URL installers (`POST /api/extensions/install-zip`, `POST /api/extensions/install-url`) and extension registry reject packages when `minCoveVersion` exceeds the running host.
  - Set `minCoveVersion` to the oldest Cove version on which all used features and contracts have been tested.

### Extension Binary Compatibility (ABI Baseline)
- The trio `Cove.Core`, `Cove.Plugins`, and `Cove.Sdk` constitutes the compiled extension ABI.
- Upstream uses Microsoft's **ApiCompat** tool against a baseline release package on NuGet.org (`CoveExtensionAbiBaselineVersion`, currently `1.4.1` in `Directory.Build.props`).
- **Strict ABI Rules**:
  1. **Never ship host assemblies**: Host-provided assemblies (`Cove.Core.dll`, `Cove.Plugins.dll`, `Cove.Sdk.dll`, EF Core, Npgsql, Pgvector) are provided exclusively by the host process. Packaging them causes `InvalidCastException` due to duplicate AssemblyLoadContext type identities.
  2. **Never change existing method arity without shims**: Adding an optional parameter (`= null`) changes the binary method signature in IL and causes runtime `MissingMethodException` on already-compiled extensions. Upstream preserves binary compatibility via `[EditorBrowsable(EditorBrowsableState.Never)]` forwarding overloads.
  3. **Record positional parameters**: Adding positional parameters to public records breaks the primary constructor and `Deconstruct`. New members must be added as `init` properties.
  4. **Interface members**: New members added to interfaces implemented by extensions (`IExtension`, `IUIExtension`, `IScraperProvider`, `IDownloaderProvider`) must provide default interface implementations.

### REST API Route Versioning
- Cove's HTTP API is served at an unversioned `/api/` base (e.g., `/api/videos`, `/api/performers`, `/api/tags`).
- There is **no `/api/v1` prefix** or version negotiation. The `v1` in `/openapi/v1.json` identifies the OpenAPI document, not a route prefix.
- Extension endpoints must be namespaced under `/api/ext/<extension-id>/...` to avoid collisions.
- Cove Minimal API endpoints evaluate conventions from `Cove.Sdk` (`RequireCovePermission`, `RequireCoveEntityAccess`, `AllowWithoutCovePermission`, `AllowCoveAnonymous`).

### Frontend Runtime Versioning
- The frontend runtime contract is currently `v1`.
- Extensions import exclusively from virtual `@cove/runtime/*` specifiers (`react`, `react-dom`, `react-query`, `lucide-react`, `components`, `api`, `webxr`).
- Extension packages use `@cove/extension-sdk` (`0.1.0`) at compile-time with peer dependency `react >= 18.0.0`.

---

## 2. Automated Upstream Sync Script (`sync-upstream-cove.py`)

A specialized synchronization and contract audit script is included at [`scripts/sync-upstream-cove.py`](../scripts/sync-upstream-cove.py).

### Quick Usage

```bash
# 1. Audit upstream releases and check alignment with local references:
python3 scripts/sync-upstream-cove.py

# 2. Download upstream developer documentation and C#/TS contracts to .upstream_cache/:
python3 scripts/sync-upstream-cove.py --sync

# 3. Audit against a local checkout of yourcove/cove:
python3 scripts/sync-upstream-cove.py --local-cove /path/to/cove
```

### What the Script Verifies
1. **GitHub Releases & Tags**: Checks latest released version, recent release notes, and tags.
2. **Directory.Build.props**: Checks `CoveExtensionAbiBaselineVersion` for current ApiCompat gate.
3. **`Cove.Plugins/IExtension.cs`**: Extracts and validates all public extension interfaces (`IExtension`, `IMiddlewareExtension`, `IBackgroundExtension`, `IScanParticipant`, `IExtensionEntityFilterProvider`, `IExtensionServiceScopeFactory`, etc.).
4. **`Cove.Sdk/UIManifestBuilder.cs`**: Extracts all builder methods (`AddPage`, `AddSlot`, `AddTab`, `AddDashboardWidget`, `AddKeyboardAction`, `AddKeyboardShortcutPreset`, `AddExtensionListFilter`, `AddExtensionEntityListFilter`, `AddLoginMethod`, `OverrideComponent`).
5. **`sdk/frontend/src/types.ts`**: Extracts and checks frontend types, slots (`APP_FLOATING_UI_SLOT`, `ENTITY_COVER_EDITOR_SLOT`, `MEDIA_PLAYER_ACTIONS_SLOT`, `MEDIA_PLAYER_OVERLAY_SLOT`), and widget presentation types.
6. **Local Reference Alignment**: Automatically tests reference files in `skills/**/references/` to ensure all newly introduced API points are documented.

---

## 3. Repetition Checklist for Upstream Updates

Whenever a new version of Cove is released or significant commits merge into upstream `main`, execute this checklist:

### Phase 1: Reconnaissance
- [ ] Run `python3 scripts/sync-upstream-cove.py --sync`.
- [ ] Read `CHANGELOG.md` in `.upstream_cache/CHANGELOG.md` focusing on:
  - New release sections (e.g. `[1.7.0]`, `[Unreleased]`).
  - Lines mentioning "Breaking change", "extensions", "minCoveVersion", or new features.
- [ ] Inspect new developer documentation in `.upstream_cache/docs-site/src/content/docs/docs/developer/extensions/`:
  - `extension-points.mdx` (backend catalog)
  - `ui-extension-points.mdx` (frontend UI catalog)
  - `frontend-runtime.mdx` (runtime modules & components)
  - `events.mdx` (entity lifecycle & rating events)
  - `permissions.mdx` (permissions & auth)
  - `packaging.mdx` (archive & manifest requirements)

### Phase 2: Backend API Surface Audit (`Cove.Plugins` & `Cove.Sdk`)
- [ ] Check for new interfaces deriving from `IExtension` or `IExtensionContributionProvider`.
- [ ] Check `CoveExtensionBase`, `FullExtensionBase`, `DataExtensionBase`, `JobExtensionBase`, `EventExtensionBase`.
- [ ] Check repository interfaces in `src/Cove.Core/Interfaces/`:
  - `IVideoRepository`, `IPerformerRepository`, `ITagApplicationRepository`.
  - Recently added: `IAudioRepository`, `ITextDocumentRepository`, `ISegmentRepository`, `IFaceRepository`, `IVideoShotService`, `ISegmentSpanCacheInvalidator`, `IVideoFileMaintenanceService`.
- [ ] Check authorization conventions in `EndpointAuthorizationExtensions.cs`.
- [ ] Update `skills/cove-plugin-authoring/references/cove-api-surface.md`.

### Phase 3: Frontend UI Surface Audit (`@cove/runtime/*` & SDK)
- [ ] Check runtime modules in `frontend-runtime.mdx`:
  - `@cove/runtime/webxr` for VR / immersive video playback.
  - `@cove/runtime/api` (`extensionFetch`).
  - `@cove/runtime/components` for newly exported primitives (`EntityMedia`, `GroupItemFeed`, `NarrativeText`, `useDocumentTitle`, `DetailListPagination`, `VideoPlayer` control hooks).
- [ ] Check new UI extension points:
  - Personal dashboard widgets (`UIDashboardWidgetContribution`, `AddDashboardWidget`, `DashboardWidgetProps`).
  - Configurable keyboard actions & presets (`AddKeyboardAction`, `AddKeyboardShortcutPreset`).
  - Native cover editor slot (`entity-cover-editor` / `ENTITY_COVER_EDITOR_SLOT`).
  - Feature Guides (`featureGuides: [...]` in `extension.json`).
- [ ] Update `skills/cove-plugin-authoring/references/cove-native-ui.md`.

### Phase 4: Downloaders & Scrapers Audit
- [ ] Check `MetadataAutomationContracts.cs`:
  - Downloader: `IDownloaderSiteLoginProvider`, `MaxHeight`, `Width`/`Height`, `AllowDuplicateDownload`, `MatchAllAsync`.
  - Scraper: `ScraperPermissions.AllowNetworkHosts`, `ProductionDate`, `int? LocalVideoId` input types.
- [ ] Update `skills/cove-downloader-authoring/references/downloader-contracts.md` and `SKILL.md`.
- [ ] Update `skills/cove-scraper-authoring/references/scraper-contracts.md` and `SKILL.md`.

### Phase 5: Verification & Version Bump
- [ ] Run `python3 scripts/sync-upstream-cove.py` to confirm all reference alignment checks pass with `[PASS]`.
- [ ] Update `agents/cove-extension-builder.md` with new capabilities.
- [ ] Update `README.md` badge and capabilities overview.
- [ ] Bump version in `plugin.json`.
- [ ] Commit changes with clear upstream reference notes.
