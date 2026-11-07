---
name: cove-plugin-authoring
description: >-
  Specialist skill for authoring, developing, testing, and packaging Cove plugins
  and extensions that are not downloaders or scrapers. Covers native UI creation
  (React 19 ESM bundles, Tailwind v4, slots, pages, tabs, settings, dialogs),
  backend API surface (IApiExtension, minimal APIs, DI services, EF Core IDataExtension,
  IJobExtension background jobs, IEventExtension lifecycle events, IStatefulExtension store),
  security permissions, and instant recall of official Cove developer documentation.
---

# Cove Plugin & Extension Authoring Skill

Use this skill to autonomously design, scaffold, implement, test, and package Cove plugins, tools, and extensions that are **not downloaders or scrapers** in `/Users/kari/dev/kari-downloads`.

This skill covers the complete non-downloader/non-scraper extension spectrum:
- **Native UI Extensions**: Navigation pages, entity detail tabs, floating slots/modals, settings panels, and page overrides.
- **Backend API & Service Extensions**: ASP.NET Core Minimal APIs (`IApiExtension`), dependency injection, custom background services.
- **Stateful & Data Extensions**: Isolated key-value storage (`IExtensionStore`), EF Core database entities and SQL migrations (`IDataExtension`).
- **Automation & Background Jobs**: Scheduled/manual tasks (`IJobExtension`), entity lifecycle event hooks (`IEventExtension`), and action buttons (`IActionExtension`).
- **Custom List Filters & Sorts**: First-class filter criteria and sorting algorithms integrated into Cove's native list views.

---

## 1. Reference Library & Knowledge Recall

Consult the specialized references in this skill before and during authoring:
- **[references/cove-api-surface.md](references/cove-api-surface.md)**: Exhaustive backend contracts, minimal APIs, DI injection, EF migrations, background jobs, event handlers, and repository interfaces.
- **[references/cove-native-ui.md](references/cove-native-ui.md)**: Complete frontend runtime guide, `@cove/runtime/*` import map, React 19 ESM bundling, Tailwind v4 theming, and `@cove/runtime/components` shared library.
- **[references/cove-dev-docs-index.md](references/cove-dev-docs-index.md)**: Comprehensive knowledge base mapping official documentation (`yourcove.org/docs` / `cove-dev/upstream/docs-site`) and upstream production codebases (`cove-extensions-ui`, `AI.Extensions`, `recommendations`).

### Local Official Documentation & Upstream Sources
- Official documentation site sources: `/Users/kari/cove-dev/upstream/docs-site/src/content/docs/docs/developer/`
- Cove host source contracts: `/Users/kari/cove-dev/upstream/cove/src/` (`Cove.Sdk`, `Cove.Plugins`, `Cove.Core`)
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
| Custom backend HTTP endpoints | `IApiExtension` (`MapEndpoints`) | [references/cove-api-surface.md#2](references/cove-api-surface.md) |
| Lightweight preferences or state | `IStatefulExtension` (`SetStore`, `IExtensionStore`) | [references/cove-api-surface.md#3](references/cove-api-surface.md) |
| Database tables & SQL migrations | `IDataExtension`, `DataExtensionBase` (`ConfigureModel`, `Migration`) | [references/cove-api-surface.md#4](references/cove-api-surface.md) |
| Scheduled or long-running tasks | `IJobExtension`, `JobExtensionBase` (`Job`, `IJobProgress`) | [references/cove-api-surface.md#5](references/cove-api-surface.md) |
| React to video/performer changes | `IEventExtension`, `EventExtensionBase` (`OnCreated`, `OnUpdated`) | [references/cove-api-surface.md#6](references/cove-api-surface.md) |
| Contextual toolbar / bulk action buttons | `IActionExtension` (`GetActions`, `ExtensionAction`) | [references/cove-api-surface.md#7](references/cove-api-surface.md) |
| Multi-capability full-stack plugin | Inherit `FullExtensionBase` (combines all above) | [references/cove-api-surface.md](references/cove-api-surface.md) |

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
2. **Register DI Services**: Override `ConfigureServices(IServiceCollection services, ExtensionContext context)`.
3. **Map Endpoints**: If implementing `IApiExtension`, map routes under `/api/ext/<slug>`:
   ```csharp
   public void MapEndpoints(IEndpointRouteBuilder endpoints)
   {
       var group = endpoints.MapGroup("/api/ext/my-plugin");
       group.MapGet("/status", () => Results.Ok(new { status = "active" }));
   }
   ```
4. **Define UI Manifest**: Override `GetUIManifest()` using `ManifestBuilder()` to register pages, tabs, slots, or settings panels.

### Step 4: Implement Native UI Components

In `extensions/<Name>/ui/`:
1. **Import from `@cove/runtime/*` only**:
   ```tsx
   import React, { useState } from "@cove/runtime/react";
   import { extensionFetch } from "@cove/runtime/api";
   import { Wrench, CheckCircle } from "@cove/runtime/lucide-react";
   import { ListPage, EntityCardGrid, TagBadge } from "@cove/runtime/components";
   ```
2. **Export default components dictionary** in `ui/<Name>.tsx`:
   ```tsx
   import { MyPluginPage } from "./MyPluginPage";

   export default {
     components: {
       MyPluginPage,
     },
   };
   ```
3. **Use Cove Theme Tokens**: Use Tailwind utility classes combined with Cove CSS custom properties (`var(--bg-surface)`, `var(--text-primary)`, `var(--border-subtle)`, `var(--color-primary)`).

### Step 5: Manifest & Security Hardening

In `extensions/<Name>/extension.json`:
- Ensure `entryDll` points to `<Name>.dll`.
- If UI is included, set `"jsBundle": "dist/bundle.js"` and `"cssBundle": "dist/bundle.css"`.
- Declare minimal permissions:
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
