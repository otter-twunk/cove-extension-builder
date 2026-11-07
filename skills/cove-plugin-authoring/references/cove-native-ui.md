# Cove Native UI Creation & Frontend Runtime Reference

This reference details how to create native-feeling, production-grade frontend UI contributions in Cove extensions. Cove extensions execute within the host's frontend shell (including desktop native apps on Windows/macOS and browser interfaces) and integrate seamlessly with Cove's layout, theme variables, routing, and component library.

---

## 1. Frontend Runtime Architecture

Cove extensions provide frontend contributions as pre-compiled ECMAScript Modules (ESM) and CSS bundles:
- **`dist/bundle.js`**: ESM bundle exporting React components.
- **`dist/bundle.css`**: Tailwind CSS v4 / custom styles inheriting host theme variables.

### The `@cove/runtime/*` Import Contract
Extension UI bundles must **never** bundle their own copies of React, React-DOM, React Query, or Lucide icons. Doing so causes dual-React instance crashes, broken Context hooks, and bundle bloat. Instead, the Cove host provides a virtual module import map resolved at runtime:

| Specifier | Runtime Target | Purpose |
|---|---|---|
| `@cove/runtime/react` | `react` (v19) | Hooks (`useState`, `useEffect`, `useMemo`, `useCallback`, `useRef`, etc.) |
| `@cove/runtime/react-dom` | `react-dom` | DOM rendering primitives |
| `@cove/runtime/react-dom-client` | `react-dom/client` | Root creation |
| `@cove/runtime/react-query` | `@tanstack/react-query` | Data fetching, cache queries (`useQuery`, `useMutation`, `useQueryClient`) |
| `@cove/runtime/lucide-react` | `lucide-react` | Vector icons matching Cove's native iconography |
| `@cove/runtime/components` | Host Component Barrel | Official native Cove components and layouts |
| `@cove/runtime/api` | Host API Client | `extensionFetch` with automatic session auth & error handling |
| `@cove/runtime/webxr` | WebXR Subsystem | Headset VR and immersive playback controls |

---

## 2. Component Export Contract

The entry point file (e.g. `ui/<ExtensionName>.tsx`) must export a default object containing a `components` dictionary mapping component names to their React definitions:

```tsx
// ui/MyExtension.tsx
import { MyCustomPage } from "./MyCustomPage";
import { MySceneAnalyticsTab } from "./MySceneAnalyticsTab";
import { MyFloatingModal } from "./MyFloatingModal";

export default {
  components: {
    MyCustomPage,
    MySceneAnalyticsTab,
    MyFloatingModal,
  },
};
```

The host looks up component names declared in your C# `UIManifest` against this `components` map.

---

## 3. Registering UI in C# (`UIManifestBuilder`)

In your extension class (inheriting `CoveExtensionBase`), implement `GetUIManifest()` using the fluent `UIManifestBuilder`:

```csharp
using Cove.Plugins;
using Cove.Sdk;

public sealed class MyExtension : CoveExtensionBase, IUIExtension
{
    public override UIManifest GetUIManifest()
    {
        return ManifestBuilder()
            .WithRuntimeVersion("v1")
            .WithJsBundle("dist/bundle.js")
            .WithCssBundle("dist/bundle.css")

            // 1. Full Navigation Page
            .AddPage(
                route: "my-tool",
                label: "My Tool",
                componentName: "MyCustomPage",
                icon: "wrench",
                showInNav: true,
                navOrder: 50
            )

            // 2. Entity Detail Tab (for scenes/videos, performers, studios, tags, galleries)
            .AddTab(
                key: "analytics-tab",
                label: "Analytics",
                pageType: "scene",              // "scene" | "performer" | "studio" | "tag"
                componentName: "MySceneAnalyticsTab",
                order: 100
            )

            // 3. Floating Slot Overlay
            .AddSlot(
                slot: "app-floating-ui",
                componentName: "MyFloatingModal"
            )

            // 4. Settings Panel inside Settings > Extensions
            .AddSettingsPanel(
                id: "my-tool-settings",
                title: "Tool Preferences",
                componentName: "MySettingsPanel",
                order: 10
            )

            // 5. Custom List Filter
            .AddExtensionListFilter(
                entityType: "video",
                id: "custom-status",
                label: "Custom Status",
                criterionType: "string",
                filterId: "status-filter",
                order: 100
            )

            .Build();
    }
}
```

### Supported Manifest Contributions:
- **`AddPage(route, label, componentName, icon, detailRoute, showInNav, navOrder)`**: Full route registered in Cove router.
- **`AddTab(key, label, pageType, componentName, order)`**: Tabs on detail pages (`"scene"` / `"video"`, `"performer"`, `"studio"`, `"tag"`, `"gallery"`, `"audio"`). Component receives entity prop (e.g. `{ sceneId: number, scene?: Video }`).
- **`AddSlot(slot, componentName, id, order)`**:
  - `app-floating-ui`: Global overlay for modals, drawers, and floating panels.
  - `media-player-actions`: Custom buttons inside video/audio player controls.
  - `media-player-overlay`: Visual overlays atop video playback surfaces.
- **`AddPageOverride(targetPage, componentName, priority)`**: Replace standard pages (e.g. `"home"` dashboard).
- **`AddSettingsTab(...)` & `AddSettingsPanel(...)`**: Extension configuration pages.
- **`AddListSort(entityType, id, label, sortKey, order)`**: Add sort options to list views.

---

## 4. Communicating with APIs (`@cove/runtime/api`)

Extensions make authenticated HTTP calls to their backend endpoints via `extensionFetch`:

```tsx
import { useState, useEffect } from "react";
import { extensionFetch } from "@cove/runtime/api";

export function MyComponent() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await extensionFetch("/api/ext/my-tool/stats");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setData(json);
      } catch (err) {
        console.error("Failed to load stats:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div>Loading...</div>;
  return <div>Run Count: {data?.runCount}</div>;
}
```

`extensionFetch` enforces same-origin validation, transparently forwards session auth cookies/headers, and supports `timeoutMs`.

---

## 5. Official Shared Components (`@cove/runtime/components`)

To keep extensions looking like native parts of Cove rather than alien add-ons, import Cove's standard UI primitives:

### Common Component Reference:

```tsx
import {
  // Navigation & Formatting
  navigateToUrl,
  TagBadge,
  formatDuration,
  formatFileSize,
  formatDate,
  getResolutionLabel,

  // Ratings
  InteractiveRating,
  RatingBadge,

  // Dialogs & Modals
  ConfirmDialog,
  EditModal,
  Field,
  TextInput,
  TextArea,
  NumberInput,
  SelectInput,
  SaveButton,
  NarrativeText,

  // Entity Pickers & Selectors
  EntityReferenceSelector,
  EntityReferenceMultiSelector,

  // Media Players & Cards
  VideoCard,
  VideoTile,
  PerformerTile,
  EntityTileFrame,
  EntityCardGrid,
  ListPage,
  MediaDetailLayout,
} from "@cove/runtime/components";
```

### Example: Entity Selector Usage
```tsx
import { useState } from "react";
import { EntityReferenceMultiSelector, type EntityReferenceOption } from "@cove/runtime/components";

export function PerformerPicker() {
  const [selected, setSelected] = useState<EntityReferenceOption[]>([]);

  return (
    <EntityReferenceMultiSelector
      entityType="performer"
      placeholder="Select performers..."
      selected={selected}
      onChange={setSelected}
    />
  );
}
```

---

## 6. Styling with Tailwind CSS & Cove Design System

Cove extensions inherit the host theme variables automatically:

```tsx
<div className="bg-[var(--bg-surface)] text-[var(--text-primary)] border border-[var(--border-subtle)] rounded-xl p-4 shadow-sm">
  <h2 className="text-lg font-semibold mb-2">Native Extension Card</h2>
  <p className="text-[var(--text-secondary)] text-sm">
    Styled with host theme tokens and Tailwind classes.
  </p>
</div>
```

### Key Host Theme Variables:
- **Backgrounds**: `var(--bg-page)`, `var(--bg-surface)`, `var(--bg-surface-hover)`, `var(--bg-elevated)`
- **Text**: `var(--text-primary)`, `var(--text-secondary)`, `var(--text-muted)`
- **Borders**: `var(--border-subtle)`, `var(--border-default)`, `var(--border-strong)`
- **Accents**: `var(--color-primary)`, `var(--color-primary-hover)`, `var(--color-accent)`
- **Status**: `var(--color-success)`, `var(--color-warning)`, `var(--color-danger)`

---

## 7. Compiling the UI Bundle

In `kari-downloads`, running:

```bash
npm run build:ui
# or verify everything:
npm run verify
```

Executes `scripts/build-extension-ui.mjs`. It scans any extension directory containing a `ui/` folder, bundles the TypeScript/JSX entry into `dist/bundle.js` with all `@cove/runtime/*` externals properly aliased, and creates `dist/bundle.css`.
