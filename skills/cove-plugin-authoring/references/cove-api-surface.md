# Cove API Surface & Backend Extension Reference

This reference covers the backend extension contracts, DI lifecycles, and host APIs in Cove (`Cove.Sdk`, `Cove.Plugins`, and `Cove.Core` `v1.7.0`+), as implemented in the upstream host and deployed across native desktop applications (Windows/macOS native app desktop host) and containerized environments.

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
        services.AddScoped<LibraryProcessor>();
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
        // Keep idempotent because reinstall and hot-replacement paths may invoke it again.
        return Task.CompletedTask;
    }

    public override Task OnUninstallAsync(IServiceProvider services, CancellationToken ct = default)
    {
        // Clean up extension-specific external assets
        return Task.CompletedTask;
    }
}
```

### Provider Generations & Tracked Scopes (`IExtensionServiceScopeFactory`)
Cove builds an isolated service-provider generation for each runtime extension. Enable, disable, replacement, and unload transitions are serialized per extension. Requests, endpoints, middleware, events, jobs, scrapers, downloaders, scans, and workers stay bound to the exact generation on which their work started.

- **Do NOT inject the container engine's `IServiceScopeFactory`** for extension-owned background work because that bypasses generation tracking.
- **Inject `IExtensionServiceScopeFactory`** into extension services when nested or long-lived work needs a scope. Its `CreateScope` and `CreateAsyncScope` methods keep the selected provider generation alive until the returned scope is disposed:

```csharp
public sealed class BackgroundProcessor(IExtensionServiceScopeFactory scopeFactory)
{
    public async Task ProcessItemAsync(int itemId, CancellationToken ct)
    {
        await using var scope = scopeFactory.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<DbContext>();
        // Work runs against tracked provider generation
    }
}
```

---

## 2. API Endpoints & Authorization Conventions (`IApiExtension`)

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
        // Always namespace endpoints under /api/ext/<extension-slug>
        var group = endpoints.MapGroup("/api/ext/my-tool");

        group.MapGet("/stats", async (IExtensionStore store) =>
        {
            var countStr = await store.GetAsync("run_count") ?? "0";
            return Results.Ok(new { RunCount = int.Parse(countStr) });
        })
        .RequireCovePermission("my-tool.read");

        group.MapPost("/process/{videoId:int}", async (
            int videoId,
            IVideoRepository videoRepo,
            CancellationToken ct) =>
        {
            var video = await videoRepo.GetByIdAsync(videoId, ct);
            if (video is null) return Results.NotFound(new { message = "Video not found" });

            return Results.Ok(new { success = true, video.Title });
        })
        .RequireCoveEntityAccess("video", "videoId", "videos.write");
    }
}
```

### `EndpointAuthorizationExtensions` Policy Conventions:
The global MVC permission filter does not wrap minimal APIs. Use conventions from `Cove.Sdk`:
- `.RequireCovePermission(params string[] permissions)`: Requires an authenticated caller with every listed permission (`PermissionMode.All`).
- `.RequireCovePermission(PermissionMode mode, params string[] permissions)`: Supports `PermissionMode.Any` or `PermissionMode.All`.
- `.RequireCoveEntityAccess(string entityKind, string routeValueName, string? permission = null)`: Validates entity permission against the positive integer route value (respecting role content rules).
- `.AllowWithoutCovePermission()`: Explicitly permits any authenticated Cove session without checking role permissions.
- `.AllowCoveAnonymous()`: Explicitly permits anonymous calls (e.g. initial external auth redirects).

---

## 3. Contributing Role Permissions & Policies (`IPermissionContributor`)

### Assignable Role Permissions
Implement `IPermissionContributor` so administrators can assign extension capabilities to roles in **Settings → Security & Access → Roles**:

```csharp
using Cove.Core.Auth;
using Cove.Plugins;
using Cove.Sdk;

public sealed class MyExtension : CoveExtensionBase, IPermissionContributor
{
    public const string ReadPerm = "my-tool.read";
    public const string AdminPerm = "my-tool.admin";

    public IEnumerable<PermissionDefinition> ContributePermissions() =>
    [
        new(
            Key: ReadPerm,
            Category: "My Tool",
            Description: "View analytics and reports.",
            GrantToAdminsByDefault: true),
        new(
            Key: AdminPerm,
            Category: "My Tool",
            Description: "Configure integrations and trigger maintenance.",
            Dangerous: true)
    ];
}
```

*Rules*: Permission keys must start with the extension ID plus `.` (e.g. `my-tool.read`). Cove rejects `*` and unnamespaced keys.

### Content Visibility Policies (`IContentPolicyContributor`)
Implement `IContentPolicyContributor` when the extension contributes custom server-side content filtering predicates:
```csharp
public sealed class MyPolicyExtension : CoveExtensionBase, IContentPolicyContributor
{
    public IReadOnlyList<ContentPolicy> ContributePolicies() =>
    [
        new ContentPolicy(
            Id: "my-tool.work-safe",
            EntityKind: "video",
            Description: "Hides unapproved videos during work hours",
            CanRead: ctx => !IsWorkHours() || ctx.Principal.IsAdmin)
    ];
}
```

---

## 4. HTTP Middleware & Background Workers

### HTTP Request Interception (`IMiddlewareExtension`)
Implement `IMiddlewareExtension` to inspect, transform, authenticate, or short-circuit incoming HTTP requests before routing:

```csharp
using Cove.Plugins;
using Microsoft.AspNetCore.Http;

public sealed class CustomAuthMiddlewareExtension : CoveExtensionBase, IMiddlewareExtension
{
    public async Task InvokeAsync(HttpContext context, RequestDelegate next)
    {
        // Inspect headers, forward authentication assertions, or add tracing
        await next(context);
    }
}
```

### Long-Lived Background Workers (`IBackgroundExtension`)
Implement `IBackgroundExtension` for host-managed continuous services:

```csharp
using Cove.Plugins;
using Microsoft.Extensions.DependencyInjection;

public sealed class FileWatcherExtension : CoveExtensionBase, IBackgroundExtension
{
    public async Task RunAsync(IServiceProvider services, CancellationToken ct)
    {
        var scopeFactory = services.GetRequiredService<IExtensionServiceScopeFactory>();
        while (!ct.IsCancellationRequested)
        {
            await using (var scope = scopeFactory.CreateAsyncScope())
            {
                // Execute unit of work with tracked DI scope
            }
            await Task.Delay(TimeSpan.FromMinutes(5), ct);
        }
    }
}
```

---

## 5. Library Scan Participation (`IScanParticipant`)

Implement `IScanParticipant` to join Cove's core library scanner:

```csharp
using Cove.Plugins;

public sealed class AudioBookScanExtension : CoveExtensionBase, IScanParticipant
{
    public async Task ScanAsync(ScanContext context, CancellationToken ct = default)
    {
        foreach (var pathInfo in context.Paths)
        {
            if (pathInfo.ExcludeAudio) continue;
            // Scan and ingest extension-owned file types
            context.Progress.Report(50.0, $"Scanning {pathInfo.Path}...");
        }
    }
}
```

---

## 6. Extension Entity List Filters (`IExtensionEntityFilterProvider`)

Contribute executable filter predicates to native list views (Tag list, Tag graph, Video list):

```csharp
using Cove.Plugins;

public sealed class VideoStatusFilterProvider : IExtensionEntityFilterProvider
{
    public IReadOnlyCollection<ExtensionEntityFilterDefinition> Filters =>
    [
        new ExtensionEntityFilterDefinition("status-filter", "videos")
    ];

    public async Task<ExtensionEntityFilterResult> ResolveAsync(
        ExtensionEntityFilterRequest request,
        CancellationToken ct)
    {
        // CandidateIds are pre-authorized by host in batches of 256
        var matches = new List<int>();
        foreach (var id in request.CandidateIds)
        {
            if (CheckStatus(id, request.Modifier, request.Value))
                matches.Add(id);
        }

        // Revision must remain identical across every batch within a single query
        return new ExtensionEntityFilterResult(matches, Revision: "rev-20261107");
    }
}
```

---

## 7. Video Shot Boundaries & Segment Services

### Gapless Shot Boundaries (`IVideoShotService`)
Cove stores gapless partitions of video file timelines into shots:
- Resolve `IVideoShotService` from DI.
- Key methods: `GetSetForFileAsync`, `GetSummariesForFilesAsync`, `WriteSetAsync`, `SplitAsync`, `MergeAsync`, `ReplaceShotsAsync`.
- `VideoShotWriteMode`: `SkipIfExists` (default) or `Replace`.
- Video shots contain `StartSec`, `EndSec`, optional `StartFrame`/`EndFrame`, `ShotType`, and `TransitionIn`.

### Segment Span Cache Invalidation (`ISegmentSpanCacheInvalidator`)
Extensions that mutate video segments outside Cove's standard controllers must invalidate projection caches:
- Resolve `ISegmentSpanCacheInvalidator`.
- Call `InvalidateVideo(videoId)` after the database transaction commits.
- Call `InvalidateAll()` for bulk unidentifiable mutations.

### Video File Maintenance (`IVideoFileMaintenanceService`)
Perform unattended file operations safely:
- `MakePrimaryWhenSameContentAsync(int videoId, int fileId, ct)`: Switches primary file only if perceptual hashes and durations match.
- `DeleteFileAsync(int fileId, bool deleteFromDisk, ct)`: Removes file, declining if it is still a video's primary file.

---

## 8. Persistent Key-Value Storage (`IStatefulExtension`, `IExtensionStore`)

```csharp
using Cove.Plugins;
using Cove.Sdk;

public sealed class MyExtension : CoveExtensionBase, IStatefulExtension
{
    private IExtensionStore? _store;
    public void SetStore(IExtensionStore store) => _store = store;

    public async Task SaveAsync(string k, string v) => await (_store?.SetAsync(k, v) ?? Task.CompletedTask);
    public async Task<string?> ReadAsync(string k) => _store != null ? await _store.GetAsync(k) : null;
}
```

---

## 9. Database Entities & SQL Migrations (`IDataExtension`, `DataExtensionBase`)

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
        });
    }

    protected override void DefineMigrations()
    {
        Migration("001_initial_schema", """
            CREATE TABLE IF NOT EXISTS my_records (
                id SERIAL PRIMARY KEY,
                title VARCHAR(256) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
        """);
    }
}

public class MyRecord
{
    public int Id { get; set; }
    public string Title { get; set; } = string.Empty;
}
```

---

## 10. Background Tasks & Jobs (`IJobExtension`, `JobExtensionBase`)

```csharp
using Cove.Plugins;
using Cove.Sdk;

public sealed class MyJobExtension : JobExtensionBase
{
    protected override void DefineJobs()
    {
        Job(
            id: "sync-catalog",
            name: "Sync External Catalog",
            handler: ExecuteSyncAsync,
            description: "Synchronizes external metadata catalog",
            supportsParameters: true,
            showInTaskList: true
        );
    }

    private async Task ExecuteSyncAsync(
        IReadOnlyDictionary<string, string>? parameters,
        IJobProgress progress,
        CancellationToken ct)
    {
        progress.Report(0.0, "Starting...");
        // Bounded work loop with cancellation check
        progress.Report(100.0, "Complete");
    }
}
```

---

## 11. Entity Lifecycle & Rating Events (`IEventExtension`, `EventExtensionBase`)

Event routing in Cove uses canonical `noun.verb` identifiers:
- `video.created`, `video.updated`, `video.deleted`
- `performer.created`, `performer.updated`, `performer.deleted`
- `studio.created`, `studio.updated`, `studio.deleted`
- `tag.created`, `tag.updated`, `tag.deleted`
- `gallery.created`, `gallery.updated`, `gallery.deleted`
- `image.created`, `image.updated`, `image.deleted`
- `group.created`, `group.updated`, `group.deleted`
- `audio.created`, `audio.updated`, `audio.deleted` (legacy wire `audiocreated` forwarded automatically)
- `text.created`, `text.updated`, `text.deleted` (legacy wire `textcreated` forwarded automatically)
- `rating.created`, `rating.updated`, `rating.deleted` (carries `userId`, `aspect`, `value` in `Data["entity"]`)

```csharp
using Cove.Plugins;
using Cove.Sdk;

public sealed class MyEventExtension : EventExtensionBase
{
    protected override void RegisterHandlers()
    {
        OnCreated("video", OnVideoCreatedAsync);
        OnUpdated("audio", OnAudioUpdatedAsync);
        On("rating.updated", OnRatingUpdatedAsync);
    }

    private Task OnVideoCreatedAsync(ExtensionEvent evt, CancellationToken ct) => Task.CompletedTask;
    private Task OnAudioUpdatedAsync(ExtensionEvent evt, CancellationToken ct) => Task.CompletedTask;
    private Task OnRatingUpdatedAsync(ExtensionEvent evt, CancellationToken ct) => Task.CompletedTask;
}
```

---

## 12. Host Repositories & Services in `Cove.Core`

Extensions can inject standard host interfaces into DI:

| Interface | Primary Responsibilities |
|---|---|
| `IVideoRepository` | Video queries (`FindAsync`, `FindIdsAsync`, `AggregateAsync`, `GetByIdWithRelationsAsync`, `skipCount`) |
| `IPerformerRepository` | Performer queries, aliases, birthdates, `CountryCriterion` |
| `ITagRepository` | Tag queries, hierarchy, aliases |
| `IStudioRepository` | Studio hierarchy, networks, parent studios |
| `IGalleryRepository` | Gallery queries and image items |
| `IImageRepository` | Image queries (`FindAsync`, `FindIdsAsync`) |
| `IAudioRepository` | Audio queries (`FindAsync`, `FindIdsAsync`, `AggregateAsync`) |
| `ITextDocumentRepository`| Text documents (`FindAsync`, `FindIdsAsync`, `AggregateAsync`) |
| `ISegmentRepository` | Video segments (`FindAsync`, `AggregateAsync`, `DoubleCriterion`) |
| `IFaceRepository` | Faces (`FindAsync`, detection relations, appearances) |
| `IVideoShotService` | Video shot sets, cuts, frames, and edit versions |
| `ISegmentSpanCacheInvalidator` | Invalidation of raw and projected segment caches |
| `IVideoFileMaintenanceService` | Primary file reassignment and duplicate deletion |
| `IUserEngagementService` | Per-user ratings, favorites, watch history, play dates (`UserId`) |
| `ICustomFieldRepository` | Custom field values and definitions |
| `IBlobService` | Binary asset blobs (`GetBlobAsync`, seekable streams) |
| `IDownloaderService` | URL matching and intake downloads |
| `IJobService` | Host job queueing and inspection |
