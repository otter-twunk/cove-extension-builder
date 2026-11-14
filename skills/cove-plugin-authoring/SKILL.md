---
name: cove-plugin-authoring
description: >-
  Specialist skill for authoring, developing, testing, and packaging Cove plugins
  and extensions that are not downloaders or scrapers. Covers native UI creation
  (React 19 ESM bundles, Tailwind v4, personal dashboard widgets, slots, WebXR, pages,
  tabs, settings, dialogs), backend API surface (IApiExtension, minimal APIs with
  endpoint authorization conventions, DI services with tracked IExtensionServiceScopeFactory,
  EF Core IDataExtension, IJobExtension background jobs, IEventExtension lifecycle events,
  IScanParticipant scan hooks, IMiddlewareExtension HTTP middleware, IBackgroundExtension workers,
  IPermissionContributor role permissions, IStatefulExtension store), security permissions,
  and instant recall of official Cove developer documentation.
---

# Cove Plugin & Extension Authoring Skill

Use this skill to autonomously design, scaffold, implement, test, and package Cove plugins, tools, and extensions that are **not downloaders or scrapers** in `/Users/kari/dev/kari-downloads`.

This skill covers the complete non-downloader/non-scraper extension spectrum:
- **Native UI Extensions**: Navigation pages, personal dashboard widgets (`UIDashboardWidgetContribution`), entity detail tabs, floating slots/modals (`app-floating-ui`, `entity-cover-editor`, `media-player-actions`), WebXR VR playback (`@cove/runtime/webxr`), settings panels, keyboard actions, and page overrides.
- **Backend API & Service Extensions**: ASP.NET Core Minimal APIs (`IApiExtension`) with authorization conventions (`RequireCovePermission`, `RequireCoveEntityAccess`), dependency injection with tracked scopes (`IExtensionServiceScopeFactory`), custom background services (`IBackgroundExtension`), HTTP middleware (`IMiddlewareExtension`).
- **Stateful & Data Extensions**: Isolated key-value storage (`IExtensionStore`), EF Core database entities and SQL migrations (`IDataExtension`).
- **Automation & Background Jobs**: Scheduled/manual tasks (`IJobExtension`), library scan participation (`IScanParticipant`), canonical entity lifecycle events (`IEventExtension`), and action buttons (`IActionExtension`).
- **Permissions & Content Policies**: Contributed role permissions (`IPermissionContributor`) and server-side content visibility policies (`IContentPolicyContributor`).
- **Custom List Filters & Sorts**: First-class filter criteria, multi-ID entity pickers, and sorting algorithms integrated into Cove's native list views (`IExtensionEntityFilterProvider`).

---

## 1. Reference Library & Knowledge Recall

Consult the specialized references in this skill before and during authoring:
- **[references/cove-api-surface.md](references/cove-api-surface.md)**: Exhaustive backend contracts, minimal APIs, authorization conventions, tracked DI scopes, EF migrations, background jobs, event handlers, and repository interfaces.
- **[references/cove-native-ui.md](references/cove-native-ui.md)**: Complete frontend runtime guide, `@cove/runtime/*` import map, React 19 ESM bundling, personal dashboard widgets, WebXR, Tailwind v4 theming, and `@cove/runtime/components` shared library.
- **[references/cove-dev-docs-index.md](references/cove-dev-docs-index.md)**: Comprehensive knowledge base mapping official documentation (`yourcove.org/docs` / `cove-dev/upstream/docs-site`) and upstream production codebases (`cove-extensions-ui`, `AI.Extensions`, `recommendations`).

### Local Official Documentation & Upstream Sources
- Official documentation site sources: `/Users/kari/cove-dev/upstream/docs-site/src/content/docs/docs/developer/`
- Cove host source contracts: `/Users/kari/cove-dev/upstream/cove/src/` (`Cove.Sdk`, `Cove.Plugins`, `Cove.Core` `v1.7.0`+)
- Real-world UI extensions: `/Users/kari/cove-dev/upstream/cove-extensions-ui/extensions/`
- Real-world background job & ML extensions: `/Users/kari/cove-dev/upstream/AI.Extensions/extensions/`
- Real-world recommendation & filter extensions: `/Users/kari/cove-dev/upstream/recommendations/extensions/`

---

## 2. Autonomous 6-Step Workflow

### Step 1: Capability & Architecture Selection

Determine which host capabilities the extension needs:

| Requirement | Required Interfaces / Base Classes | Reference |
|---|---|---|
| Native UI page, tab, slot, or settings | `IUIExtension`, `CoveExtensionBase`, `UIManifestBuilder` | [references/cove-native-ui.md](references/cove-native-ui.md) |
| Personal dashboard widget | `IUIExtension`, `AddDashboardWidget`, `DashboardWidgetProps` | [references/cove-native-ui.md#4](references/cove-native-ui.md) |
| WebXR immersive VR playback | `@cove/runtime/webxr` (`startImmersiveVideo`, `getImmersiveVrSupport`) | [references/cove-native-ui.md#6](references/cove-native-ui.md) |
| Custom backend HTTP endpoints | `IApiExtension` (`MapEndpoints`, `RequireCovePermission`) | [references/cove-api-surface.md#2](references/cove-api-surface.md) |
| Role permissions for settings | `IPermissionContributor` (`ContributePermissions`) | [references/cove-api-surface.md#3](references/cove-api-surface.md) |
| Server-side content policies | `IContentPolicyContributor` (`ContributePolicies`) | [references/cove-api-surface.md#3](references/cove-api-surface.md) |
| HTTP request/response middleware | `IMiddlewareExtension` (`InvokeAsync`) | [references/cove-api-surface.md#4](references/cove-api-surface.md) |
| Continuous background worker | `IBackgroundExtension` (`RunAsync`, `IExtensionServiceScopeFactory`) | [references/cove-api-surface.md#4](references/cove-api-surface.md) |
| Join core library scans | `IScanParticipant` (`ScanAsync`, `ScanContext`) | [references/cove-api-surface.md#5](references/cove-api-surface.md) |
| Executable list filters / pickers | `IExtensionEntityFilterProvider`, `AddExtensionEntityListFilter` | [references/cove-api-surface.md#6](references/cove-api-surface.md) |
| Video file maintenance / shots | `IVideoFileMaintenanceService`, `IVideoShotService` | [references/cove-api-surface.md#7](references/cove-api-surface.md) |
| Lightweight preferences or state | `IStatefulExtension` (`SetStore`, `IExtensionStore`) | [references/cove-api-surface.md#8](references/cove-api-surface.md) |
| Database tables & SQL migrations | `IDataExtension`, `DataExtensionBase` (`ConfigureModel`, `Migration`) | [references/cove-api-surface.md#9](references/cove-api-surface.md) |
| Scheduled or manual tasks | `IJobExtension`, `JobExtensionBase` (`Job`, `IJobProgress`) | [references/cove-api-surface.md#10](references/cove-api-surface.md) |
| React to library changes | `IEventExtension`, `EventExtensionBase` (canonical `OnCreated`, `OnUpdated`) | [references/cove-api-surface.md#11](references/cove-api-surface.md) |
| Contextual toolbar / bulk action buttons | `IActionExtension` (`GetActions`, `ExtensionAction`) | [references/cove-api-surface.md](references/cove-api-surface.md) |
| Multi-capability full-stack plugin | Inherit `FullExtensionBase` (combines data, API, UI, events, jobs, store, scan) | [references/cove-api-surface.md](references/cove-api-surface.md) |

### Step 2: Scaffold the Extension

Scaffold a plugin/tool extension using `scripts/new-extension.mjs`:

```bash
node scripts/new-extension.mjs \
  --kind plugin \
  --name <PascalCaseName> \
  --title "<Human Readable Name>" \
  [--categories "ui,tools"] \
  [--description "Description of the plugin"]
```

This generates:
- `extensions/<Name>/extension.json` with entry DLL and UI bundle links
- `extensions/<Name>/<Name>.csproj` configured with compile-only Cove host contracts
- `extensions/<Name>/<Name>Extension.cs` implementing `CoveExtensionBase, IUIExtension, IApiExtension`
- `extensions/<Name>/ui/<Name>.tsx` and `extensions/<Name>/ui/<Name>Page.tsx`
- Registration in `extensions/catalog.json` and `MultiExtensionTemplate.slnx`
- Unit test scaffold in `tests/KariDownloads.Tests/<Name>Tests.cs`

### Step 3: Implement Backend Logic

In `extensions/<Name>/<Name>Extension.cs`:
1. **Never redeclare metadata**: `Id`, `Name`, `Version`, `Description`, `Author`, and `Categories` are loaded automatically from `extension.json` by `CoveExtensionBase`.
2. **Register DI Services**: Override `ConfigureServices(IServiceCollection services, ExtensionContext context)`. Use `IExtensionServiceScopeFactory` when creating scopes for background operations.
3. **Map Endpoints with Authorization**: If implementing `IApiExtension`, map routes under `/api/ext/<slug>` and attach Cove permission conventions:
   ```csharp
   public void MapEndpoints(IEndpointRouteBuilder endpoints)
   {
       var group = endpoints.MapGroup("/api/ext/my-plugin");
       group.MapGet("/status", () => Results.Ok(new { status = "active" }))
            .RequireCovePermission("my-plugin.read");
       group.MapPost("/process/{videoId:int}", ProcessHandler)
            .RequireCoveEntityAccess("video", "videoId", "videos.write");
   }
   ```
4. **Define UI Manifest**: Override `GetUIManifest()` using `ManifestBuilder()` to register pages, tabs, dashboard widgets, slots, keyboard actions, or settings panels.

### Step 4: Implement Native UI Components

In `extensions/<Name>/ui/`:
1. **Import from `@cove/runtime/*` only**:
   ```tsx
   import React, { useState } from "@cove/runtime/react";
   import { extensionFetch } from "@cove/runtime/api";
   import { Wrench, CheckCircle } from "@cove/runtime/lucide-react";
   import {
     MediaDetailLayout,
     DetailListToolbar,
     DetailListPagination,
     EntityMedia,
     GroupItemFeed,
     NarrativeText,
     useDocumentTitle,
     TagBadge
   } from "@cove/runtime/components";
   ```
2. **Export default components & handlers dictionary** in `ui/<Name>.tsx`:
   ```tsx
   import { MyPluginPage } from "./MyPluginPage";

   export default {
     components: {
       MyPluginPage,
     },
     actionHandlers: {},
     onLoad: async () => {},
     onUnload: async () => {},
   };
   ```
3. **Use Cove Theme Tokens**: Use Tailwind utility classes combined with Cove CSS custom properties (`var(--bg-surface)`, `var(--text-primary)`, `var(--border-subtle)`, `var(--color-primary)`).

### Step 5: Manifest & Security Hardening

In `extensions/<Name>/extension.json`:
- Ensure `entryDll` points to `<Name>.dll`.
- If UI is included, set `"jsBundle": "dist/bundle.js"` and `"cssBundle": "dist/bundle.css"`.
- If providing in-app User Guide articles, declare `"featureGuides": ["docs/guides/overview.json"]`.
- Declare minimal runtime permissions:
  - If contacting external APIs: add domains to `permissions.network`.
  - If internal only: keep `permissions.network` empty `[]`.
- If using settings: use the standard schema `{ "name": "...", "displayName": "...", "type": "STRING|NUMBER|BOOLEAN", "description": "..." }`.

### Step 6: Test, Verify & Package

Execute the repository verification suite:

```bash
npm run verify
```

This verifies:
1. `validate-extension-repo.mjs`: Manifest schemas, catalog consistency, version floors.
2. `build-extension-ui.mjs`: Bundles TypeScript React UI into `dist/bundle.js` + `dist/bundle.css`.
3. `dotnet test`: Runs offline fixture tests in `tests/KariDownloads.Tests/`.
4. `package-extension.mjs`: Publishes Release binaries, verifies zero leaked host DLLs, and builds `artifacts/packages/<id>-<version>.zip`.
