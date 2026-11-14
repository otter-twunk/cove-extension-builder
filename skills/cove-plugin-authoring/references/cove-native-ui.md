# Cove Native UI Creation & Frontend Runtime Reference

This reference details how to create native-feeling, production-grade frontend UI contributions in Cove extensions. Cove extensions execute within the host's frontend shell (including desktop native apps on Windows/macOS and browser interfaces) and integrate seamlessly with Cove's layout, theme variables, routing, and component library.

---

## 1. Frontend Runtime Architecture

Cove extensions provide frontend contributions as pre-compiled ECMAScript Modules (ESM) and CSS bundles:
- **`dist/bundle.js`**: ESM bundle exporting React components and action handlers.
- **`dist/bundle.css`**: Tailwind CSS v4 / custom styles inheriting host theme variables.

### The `@cove/runtime/*` Import Contract (`v1`)
Extension UI bundles must **never** bundle their own copies of React, React-DOM, React Query, or Lucide icons. Doing so causes dual-React instance crashes, broken Context hooks, and bundle bloat. The Cove host provides a virtual module import map resolved at runtime:

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

Compile-time types and definitions are available via `@cove/extension-sdk` (`npm i -D @cove/extension-sdk`).

---

## 2. Component Export & Lifecycle Contract

The entry point file (e.g. `ui/<ExtensionName>.tsx`) must export a default object containing:
- `components`: Dictionary of exported React components matching manifest names.
- `actionHandlers`: Dictionary of frontend action handlers (legacy `handlers` also supported).
- `onLoad`: Optional async hook invoked once extension bundle is loaded.
- `onUnload`: Optional async cleanup hook invoked before bundle replacement or extension unload.

```tsx
// ui/MyExtension.tsx
import { MyCustomPage } from "./MyCustomPage";
import { MyAnalyticsTab } from "./MyAnalyticsTab";
import { MyFloatingModal } from "./MyFloatingModal";
import { MyDashboardWidget, MyWidgetEditor } from "./MyDashboardWidget";

export default {
  components: {
    MyCustomPage,
    MyAnalyticsTab,
    MyFloatingModal,
    MyDashboardWidget,
    MyWidgetEditor,
  },
  actionHandlers: {
    handleBatchTagAction: async (action, payload) => {
      console.log("Executed action:", action.id, payload);
    },
  },
  onLoad: async () => {
    // Initialized when extension is activated
  },
  onUnload: async () => {
    // Clean up persistent DOM elements, intervals, or WebSocket subscriptions
  },
};
```

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
            // 1. Navigation Page (icon: "puzzle" or "music")
            .AddPage(
                route: "my-tool",
                label: "My Tool",
                componentName: "MyCustomPage",
                icon: "puzzle",
                showInNav: true,
                navOrder: 50
            )

            // 2. Entity Detail Tab (pageType: "video", "performer", "studio", "tag", "gallery", "group")
            .AddTab(
                key: "analytics-tab",
                label: "Analytics",
                pageType: "video",
                componentName: "MyAnalyticsTab",
                order: 100
            )

            // 3. Viewport-Level Floating Slot Overlay
            .AddSlot(
                slot: "app-floating-ui",
                componentName: "MyFloatingModal"
            )

            // 4. Media Player Overlay / Actions
            .AddSlot(
                slot: "media-player-actions",
                componentName: "PlayerSpeedButton"
            )

            // 5. Personal Dashboard Widget
            .AddDashboardWidget(
                id: "quick-metrics",
                label: "Quick Metrics",
                componentName: "MyDashboardWidget",
                editorComponentName: "MyWidgetEditor",
                description: "Shows library ingestion velocity and health.",
                icon: "activity"
            )

            // 6. Settings Panel inside Settings > Extensions
            .AddSettingsPanel(
                new UISettingsPanel(
                    Id: "my-tool-settings",
                    Title: "Tool Preferences",
                    ComponentName: "MySettingsPanel",
                    Order: 10
                )
            )

            // 7. Custom List Filter with Entity Multi-Picker
            .AddExtensionEntityListFilter(
                entityType: "video",
                id: "custom-status",
                label: "Custom Status",
                filterId: "status-filter",
                pickedEntityType: "tags",
                order: 100
            )

            // 8. Configurable Keyboard Action & Preset
            .AddKeyboardAction(
                id: "toggle-overlay",
                label: "Toggle Extension Overlay",
                defaultBindings: ["Ctrl+Shift+O"],
                scopes: [new UIKeyboardActionScope("global")],
                handlerName: "toggleOverlayHandler"
            )
            .AddKeyboardShortcutPreset(
                new UIKeyboardShortcutPreset(
                    SchemaVersion: 1,
                    Id: "custom-preset",
                    Name: "My Extension Shortcuts",
                    ExtensionId: Id,
                    UnmappedActions: "action-defaults",
                    Bindings: new() { ["toggle-overlay"] = ["Ctrl+Shift+O"] }
                )
            )

            .Build();
    }
}
```

> [!NOTE]
> Asset bundle paths are declared in `extension.json` (`jsBundle` and `cssBundle`), which the host resolves automatically. Avoid relying on `WithJsBundle`/`WithCssBundle` in code as packaging configuration.

---

## 4. Personal Dashboard Widgets (`UIDashboardWidgetContribution`)

Extensions can contribute widgets to personal dashboards.
- Users can arrange widgets in **Flow** (grid layout with configurable column widths: full, 1/2, 1/3, 1/4, 1/5) or **Canvas** (exclusive document-scrolling view).
- Components receive `DashboardWidgetProps` and `DashboardWidgetEditorProps`:

```tsx
import React from "@cove/runtime/react";
import type { DashboardWidgetProps, DashboardWidgetEditorProps } from "@cove/extension-sdk";

interface WidgetConfig {
  metricType: string;
}

export function MyDashboardWidget({
  dashboardId,
  instanceId,
  configuration,
  presentation,
  onNavigate,
}: DashboardWidgetProps<WidgetConfig>) {
  return (
    <div className="p-4 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-subtle)]">
      <h3 className="font-semibold text-[var(--text-primary)]">Widget #{instanceId}</h3>
      <p className="text-sm text-[var(--text-secondary)]">Presentation: {presentation}</p>
    </div>
  );
}

export function MyWidgetEditor({
  configuration,
  onChange,
  onValidityChange,
}: DashboardWidgetEditorProps<WidgetConfig>) {
  return (
    <div className="space-y-4">
      <label className="block text-sm font-medium">Metric Type</label>
      <input
        type="text"
        className="input"
        value={configuration.metricType || ""}
        onChange={(e) => {
          onChange({ ...configuration, metricType: e.target.value });
          onValidityChange(e.target.value.length > 0);
        }}
      />
    </div>
  );
}
```

---

## 5. Published Slot Locations & Contexts

### Viewport Slot
- **`app-floating-ui`** (`APP_FLOATING_UI_SLOT`): Viewport-level layer persisting across route navigation. Use `position: fixed` for modals, toast containers, or floating action bars.

### Media Player Slots
- **`media-player-actions`** (`MEDIA_PLAYER_ACTIONS_SLOT`): Custom controls beside native media playback controls.
- **`media-player-overlay`** (`MEDIA_PLAYER_OVERLAY_SLOT`): Overlaid directly atop video media.
- Component receives `MediaPlayerExtensionContext`:
  - `currentTime`, `duration`, `playing`, `playbackRate`, `intrinsicWidth`, `intrinsicHeight`, `contentRect`.
  - Control functions: `play()`, `pause()`, `seek(seconds)`, `setPlaybackRate(rate)`.
  - `acquireInteractionMode(options)`: Temporarily hide native controls or pause watch tracking during interactive tools.

### Cover Editor Slot
- **`entity-cover-editor`** (`ENTITY_COVER_EDITOR_SLOT`): Rendered inside Cove's native cover dialog.
- Component receives `EntityCoverEditorContext`: `entityType`, `entityId`, `coverKey` (`primary` | `front` | `back`), `currentImageUrl`, `canEdit`.

### Detail & Card Slots
- Detail actions: `video-detail-actions`, `performer-detail-actions`, `studio-detail-actions`, `tag-detail-actions`, `gallery-detail-actions`, `group-detail-actions`.
- Card regions: `video-card-content`, `tag-card-footer`, `performer-card-footer`, `studio-card-footer`.
- List toolbar ends: `list-page-toolbar-end`, `<page-key>-list-toolbar-end`.

---

## 6. Immersive VR Playback (`@cove/runtime/webxr`)

Cove supports native WebXR VR video playback:

```tsx
import { getImmersiveVrSupport, startImmersiveVideo } from "@cove/runtime/webxr";

export async function enterVrMode(videoElement: HTMLVideoElement, videoVrMetadata: any) {
  const support = await getImmersiveVrSupport();
  if (support.supported) {
    await startImmersiveVideo(videoElement, videoVrMetadata, {
      onEnd: () => console.log("Exited VR"),
    });
  }
}
```

Functions provided:
- `getImmersiveVrSupport()`: Checks headset capabilities and secure context.
- `startImmersiveVideo(element, vrConfig, options)`: Starts full WebXR session.
- `playVideoInSession(session, element, vrConfig, options)`: Plays video into an existing extension XR session.
- `offerSessionHandoff(session, options)`: Hands active session over to video page.

---

## 7. Communicating with APIs (`@cove/runtime/api`)

Extensions make authenticated HTTP calls to their backend endpoints via `extensionFetch`:

```tsx
import { extensionFetch } from "@cove/runtime/api";

export async function fetchStats() {
  const res = await extensionFetch("/api/ext/my-tool/stats", {
    timeoutMs: 10000,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}
```

- Enforces same-origin URL validation (`/api/...`).
- Automatically handles bearer credentials, cookie sessions, and token refresh.
- Forces `redirect: "error"` to prevent unintended redirects outside the host boundary.

---

## 8. Official Shared Components (`@cove/runtime/components`)

Import standard host primitives from `@cove/runtime/components`:

### Essential Layout & Display
- **`MediaDetailLayout`**: Responsive detail page shell (`title`, `backLabel`, `onGoBack`, `backAlternative`, sidebar tabs).
- **`DetailListToolbar`**: Full-featured list toolbar (search, sort, filter dialog, view modes, selection).
- **`DetailListPagination`**: Independent list paginator with ARIA accessibility and page-clamp correction.
- **`EntityMedia`**: Host boundary for rendering primary entity media with override support.
- **`GroupItemFeed`**: Infinite-scrolling mixed-media feed for groups.
- **`NarrativeText`**: Interface preference-aware description/bio rendering with safe Markdown support.
- **`useDocumentTitle(title)`**: Updates browser tab title dynamically (`<title> | <page> | Cove`).
- **`useMarkdownRenderingEnabled()`**: Checks if user enabled Markdown rendering in Interface settings.
- **`VideoPlayer`**: Reusable video player with `onSeekRegister` and `onPlaybackControlRegister`.
- **Audio primitives**: `AudioPlayer`, `AudioTile`, `AUDIO_CRITERIA`, `AUDIO_SORT_OPTIONS`.
- **Entity pickers**: `EntityReferenceSelector`, `EntityReferenceMultiSelector`.
- **Rating badges**: `InteractiveRating`, `RatingBadge`, `RatingField`.

---

## 9. Feature Guides (`featureGuides: [...]`)

Extensions can contribute rich, in-app User Guide articles using Cove's shared JSON feature-guide format:
- Declare in `extension.json`: `"featureGuides": ["docs/guides/overview.json"]`.
- Format matches `docs/feature-guides/schema.json` with sections, steps, tables, notes, and recipes.
- Supports packaged `.webp` images and cross-links.
- Nested under other topics via `parentTopicId`.
