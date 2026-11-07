# Cove API Surface & Backend Extension Reference

This reference covers the backend extension contracts and host APIs in Cove (`Cove.Sdk`, `Cove.Plugins`, and `Cove.Core` `v1.7.0`), as implemented in the upstream host and deployed in native desktop applications (e.g. Windows native app desktop host) and server environments.

---

## 1. Extension Anatomy & Lifecycle

Every compiled Cove extension implements `IExtension` from `Cove.Plugins`. In practice, C# extensions inherit from `CoveExtensionBase` or `FullExtensionBase` (`Cove.Sdk`), which implement `IManifestAware` to automatically inject properties from `extension.json`.

```csharp
using Cove.Plugins;
using Cove.Sdk;
using Microsoft.Extensions.DependencyInjection;

namespace MyExtension;

public sealed class MyExtension : CoveExtensionBase
{
    // Identity & metadata (Id, Name, Version, Description, etc.) are populated
    // automatically from extension.json by CoveExtensionBase. Never redeclare them in C#.

    public override void ConfigureServices(IServiceCollection services, ExtensionContext context)
    {
        // Register extension-scoped dependencies into DI
        services.AddSingleton<IMyService, MyService>();
    }

    public override async Task InitializeAsync(IServiceProvider services, CancellationToken ct = default)
    {
        // Executed once host DI container is built and extension is activated
    }

    public override Task ShutdownAsync(CancellationToken ct = default)
    {
        // Clean up unmanaged resources or graceful cancellation
        return Task.CompletedTask;
    }

    public override Task OnInstallAsync(IServiceProvider services, CancellationToken ct = default)
    {
        // Executed once after first install (seed initial config or default data)
        return Task.CompletedTask;
    }

    public override Task OnUninstallAsync(IServiceProvider services, CancellationToken ct = default)
    {
        // Clean up extension-specific external assets
        return Task.CompletedTask;
    }
}
```

### Desktop & Native App Environment
When running in a native desktop app (e.g., Windows native Cove app):
- The Cove backend runs as an embedded local process exposing endpoints over a local loopback port.
- Extensions run in isolated assembly load contexts with their own DI container.
- Storage and data operations hit the local SQLite or PostgreSQL database and local filesystem paths.
- Network permissions declared in `extension.json` (`permissions.network`) dictate permitted outbound network destinations.

---

## 2. API Endpoints (`IApiExtension`)

Extensions expose custom HTTP endpoints to the frontend or external clients by implementing `IApiExtension`. Cove uses ASP.NET Core Minimal APIs.

```csharp
using Cove.Plugins;
using Cove.Sdk;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;

namespace MyExtension;

public sealed class MyExtension : CoveExtensionBase, IApiExtension
{
    public void MapEndpoints(IEndpointRouteBuilder endpoints)
    {
        // Namespace endpoints under /api/ext/<extension-slug>
        var group = endpoints.MapGroup("/api/ext/my-tool");

        group.MapGet("/stats", async (IExtensionStore store) =>
        {
            var countStr = await store.GetAsync("run_count") ?? "0";
            return Results.Ok(new { RunCount = int.Parse(countStr) });
        });

        group.MapPost("/process", async (
            ProcessRequest request,
            IVideoRepository videoRepo,
            CancellationToken ct) =>
        {
            var video = await videoRepo.GetByIdAsync(request.VideoId, ct);
            if (video is null) return Results.NotFound(new { message = "Video not found" });

            return Results.Ok(new { success = true, video.Title });
        });
    }
}

public sealed record ProcessRequest(int VideoId);
```

### Endpoint Guidelines:
- Always prefix routes with `/api/ext/<slug>` to prevent route collisions with core Cove routes.
- Request parameters and bodies are deserialized using standard ASP.NET Core model binding and `System.Text.Json`.
- Injected parameters (like repositories or services) resolve from the DI container.
- Standard return types: `Results.Ok(...)`, `Results.NotFound(...)`, `Results.BadRequest(...)`, `Results.StatusCode(503)`.

---

## 3. Persistent Key-Value Storage (`IStatefulExtension`, `IExtensionStore`)

For lightweight extension state, preferences, counters, and caching, implement `IStatefulExtension`. Cove automatically provides an isolated, persistent `IExtensionStore`.

```csharp
using Cove.Plugins;
using Cove.Sdk;

public sealed class MyExtension : CoveExtensionBase, IStatefulExtension
{
    private IExtensionStore? _store;

    public void SetStore(IExtensionStore store) => _store = store;

    public async Task SaveConfigAsync(string key, string value)
    {
        if (_store != null)
        {
            await _store.SetAsync(key, value);
        }
    }

    public async Task<string?> ReadConfigAsync(string key)
    {
        return _store != null ? await _store.GetAsync(key) : null;
    }
}
```

### `IExtensionStore` Contract:
- `Task<string?> GetAsync(string key)`
- `Task SetAsync(string key, string value)`
- `Task DeleteAsync(string key)`
- `Task<IReadOnlyDictionary<string, string>> GetAllAsync()`

---

## 4. Database Entities & Migrations (`IDataExtension`, `DataExtensionBase`)

For structured tabular data, extensions can contribute tables to Cove's database via Entity Framework Core and SQL migrations.

```csharp
using Cove.Plugins;
using Cove.Sdk;
using Microsoft.EntityFrameworkCore;

public sealed class MyDataExtension : DataExtensionBase
{
    public override void ConfigureModel(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<MyRecord>(entity =>
        {
            entity.ToTable("my_records");
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Title).IsRequired().HasMaxLength(256);
            entity.Property(e => e.CreatedAt).IsRequired();
            entity.HasIndex(e => e.CreatedAt);
        });
    }

    protected override void DefineMigrations()
    {
        Migration("001_create_my_records", """
            CREATE TABLE IF NOT EXISTS my_records (
                id SERIAL PRIMARY KEY,
                title VARCHAR(256) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS ix_my_records_created_at ON my_records(created_at);
        """);
    }
}

public class MyRecord
{
    public int Id { get; set; }
    public string Title { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
```

### Migration Rules:
- Names must be sortable and deterministic (e.g. `001_initial_schema`, `002_add_status_column`).
- Cove runs migrations sequentially and commits each SQL script and name receipt atomically.

---

## 5. Background Jobs (`IJobExtension`, `JobExtensionBase`)

Extensions register background tasks executed by Cove's job scheduler by implementing `IJobExtension` or inheriting `JobExtensionBase`.

```csharp
using Cove.Plugins;
using Cove.Sdk;

public sealed class MyJobExtension : JobExtensionBase
{
    protected override void DefineJobs()
    {
        Job(
            id: "sync-external-catalog",
            name: "Sync External Catalog",
            handler: ExecuteSyncJobAsync,
            description: "Synchronizes local tags and performers with external catalog",
            supportsParameters: true,
            showInTaskList: true
        );
    }

    private async Task ExecuteSyncJobAsync(
        IReadOnlyDictionary<string, string>? parameters,
        IJobProgress progress,
        CancellationToken ct)
    {
        progress.Report(0.0, "Starting sync...");

        for (int i = 1; i <= 10; i++)
        {
            ct.ThrowIfCancellationRequested();
            await Task.Delay(500, ct);
            progress.Report(i * 10.0, $"Processing batch {i} of 10...");
        }

        progress.Report(100.0, "Sync complete!");
    }
}
```

### Job Progress Contract:
- `IJobProgress.Report(double percentage, string? statusMessage)`:
  - `percentage`: `0.0` to `100.0`.
  - Supports cooperative cancellation via `CancellationToken`.

---

## 6. Entity Lifecycle Events (`IEventExtension`, `EventExtensionBase`)

React to create, update, and delete events across Cove's core entities (videos, performers, tags, studios, galleries, images) by implementing `IEventExtension` or inheriting `EventExtensionBase`.

```csharp
using Cove.Plugins;
using Cove.Sdk;

public sealed class MyEventExtension : EventExtensionBase
{
    protected override void RegisterHandlers()
    {
        OnCreated("video", OnVideoCreatedAsync);
        OnUpdated("performer", OnPerformerUpdatedAsync);
        OnDeleted("video", OnVideoDeletedAsync);
        On("library.scan_completed", OnScanCompletedAsync);
    }

    private async Task OnVideoCreatedAsync(ExtensionEvent evt, CancellationToken ct)
    {
        // evt.Payload contains serialized JSON representation of the entity
        int videoId = evt.EntityId;
        // Perform automation, thumbnail extraction, notification, or analysis
    }

    private async Task OnPerformerUpdatedAsync(ExtensionEvent evt, CancellationToken ct)
    {
        int performerId = evt.EntityId;
    }

    private async Task OnVideoDeletedAsync(ExtensionEvent evt, CancellationToken ct)
    {
        int deletedId = evt.EntityId;
    }

    private async Task OnScanCompletedAsync(ExtensionEvent evt, CancellationToken ct)
    {
    }
}
```

---

## 7. Action Contributions (`IActionExtension`)

Contribute contextual action buttons to entity detail pages, toolbar menus, or bulk action selection bars in the Cove UI.

```csharp
using Cove.Plugins;
using Cove.Sdk;

public sealed class MyActionExtension : CoveExtensionBase, IActionExtension
{
    public IReadOnlyList<ExtensionAction> GetActions()
    {
        return
        [
            new ExtensionAction(
                Id: "batch-audio-normalize",
                Label: "Normalize Audio",
                ExtensionId: Id,
                ActionType: "bulk",       // "bulk" or "item"
                EntityTypes: ["video", "audio"],
                Icon: "volume-2",
                HandlerName: "openNormalizeModal",
                Order: 50,
                SuppressSuccessAlert: true
            )
        ];
    }
}
```

---

## 8. Cross-Extension Service Exchange (`IExtensionServiceExchange`)

Cove isolates each extension in its own dependency injection container. To share services across extensions (e.g. an AI provider or analytics service consumed by another extension), publish and resolve contracts via `IExtensionServiceExchange`:

```csharp
// Publisher Extension:
public override Task InitializeAsync(IServiceProvider services, CancellationToken ct = default)
{
    PublishContributions<IMySharedContract>(services);
    return Task.CompletedTask;
}

// Consumer Extension:
public override Task InitializeAsync(IServiceProvider services, CancellationToken ct = default)
{
    var exchange = services.GetService<IExtensionServiceExchange>();
    var sharedServices = exchange?.Resolve<IMySharedContract>();
    return Task.CompletedTask;
}
```

---

## 9. Core Repositories & Services in `Cove.Core`

Extensions can inject any of the following standard host interfaces into their services or minimal API endpoints:

| Interface | Primary Responsibilities |
|---|---|
| `IVideoRepository` | Query, filter, aggregate, fetch relations for videos (`FindAsync`, `GetByIdWithRelationsAsync`) |
| `IPerformerRepository` | Manage performers, aliases, birthdates, and relations |
| `ITagRepository` | Query and assign hierarchical tags |
| `IStudioRepository` | Manage studios, parent studios, and networks |
| `IGalleryRepository` | Query galleries and associated image items |
| `IAudioRepository` | Query audio files, tracks, and metadata |
| `ISegmentRepository` | Manage video time-slices, bookmarks, and compilations |
| `ICustomFieldRepository` | Read and write custom fields attached to entities |
| `IDownloaderService` | Programmatically trigger or match downloaders |
| `IJobService` | Enqueue or query host background jobs |
| `IBlobService` | Store and retrieve binary image blobs and media assets |
