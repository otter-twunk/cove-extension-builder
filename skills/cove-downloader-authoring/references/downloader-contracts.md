# Cove Downloader SDK Contracts & Reference Patterns (`v1.7.0`+)

## 1. Exact C# Downloader Contracts (`Cove.Plugins`)

```csharp
namespace Cove.Plugins;

[Flags]
public enum DownloaderCapabilities
{
    None = 0,
    ResumeSupported = 1 << 0,
    RangeRequests = 1 << 1,
    MultiQuality = 1 << 2,
    InlineMetadata = 1 << 3
}

public enum DownloaderEntity
{
    Video,
    Image,
    Gallery,
    Audio,
    Text
}

public sealed record DownloaderPermissions(
    IReadOnlyList<string>? AllowNetworkHosts = null);

public sealed record DownloaderDescriptor(
    string Id,
    string Name,
    DownloaderEntity SupportedEntity,
    IReadOnlyList<string> SupportedUrlPatterns,
    DownloaderCapabilities Capabilities = DownloaderCapabilities.None);

public sealed record DownloaderQualityOption(
    string Id,
    string Label,
    string? Description = null)
{
    public int? Width { get; init; }
    public int? Height { get; init; }
}

public sealed record DownloaderUrlMatch(
    string DownloaderId,
    string NormalizedUrl,
    IReadOnlyList<DownloaderQualityOption>? QualityOptions = null,
    string? Label = null,
    string? SourceUrl = null,
    bool Divert = false);

public sealed record DownloaderRequest(
    string DownloaderId,
    string Url,
    DownloaderEntity Entity,
    DownloaderPermissions Permissions,
    string? QualityId = null,
    string? SourceUrl = null)
{
    /// <summary>
    /// Highest frame height to download, from the server's download settings. Set only when
    /// QualityId does not already name a specific resolution.
    /// </summary>
    public int? MaxHeight { get; init; }
}

public sealed record DownloaderImportRequest(
    string DownloaderId,
    string Url,
    DownloaderEntity Entity,
    int? EntityId = null,
    string? QualityId = null,
    string? SourceUrl = null)
{
    /// <summary>
    /// Download even when EntityId already has files or the URL is already in the library.
    /// </summary>
    public bool AllowDuplicateDownload { get; init; }
}

public sealed record DownloaderImportResult(string LibraryPath, int? EntityId);

public sealed record DownloaderResult(
    string LocalPath,
    string? OriginalFilename = null,
    IReadOnlyDictionary<string, string>? Headers = null,
    ScrapedVideoDto? InlineVideoMetadata = null,
    ScrapedGalleryDto? InlineGalleryMetadata = null,
    ScrapedImageDto? InlineImageMetadata = null);

public interface IDownloaderHost
{
    string TempDirectory { get; }
    IHttpClientFactory HttpClients { get; }
    ILogger CreateLogger(string categoryName);
    void ReportProgress(double progress, string? message = null); // 0.0 to 100.0
}

public interface IDownloaderProvider : IExtension
{
    IReadOnlyList<DownloaderDescriptor> GetDownloaders();

    Task<DownloaderUrlMatch?> MatchAsync(string url, CancellationToken ct)
        => Task.FromResult<DownloaderUrlMatch?>(null);

    async Task<IReadOnlyList<DownloaderUrlMatch>> MatchAllAsync(string url, CancellationToken ct)
    {
        var match = await MatchAsync(url, ct);
        return match == null ? [] : [match];
    }

    Task<DownloaderResult?> DownloadAsync(
        DownloaderRequest request,
        IDownloaderHost host,
        CancellationToken ct)
        => Task.FromResult<DownloaderResult?>(null);
}

/// <summary>Site credentials saved in Cove's Downloader Settings.</summary>
public sealed record DownloaderSiteLogin(string Site, string Username, string Password)
{
    public DateTime? SavedAt { get; init; }
}

/// <summary>Resolves site logins configured in Cove Settings.</summary>
public interface IDownloaderSiteLoginProvider
{
    DownloaderSiteLogin? FindForUrl(string url);
}

/// <summary>Performs post-download file maintenance (primary file reassignment, duplicate removal).</summary>
public interface IVideoFileMaintenanceService
{
    Task<VideoFileOperationResult> MakePrimaryWhenSameContentAsync(int videoId, int fileId, CancellationToken ct);
    Task<VideoFileOperationResult> DeleteFileAsync(int fileId, bool deleteFromDisk, CancellationToken ct);
}

public sealed record VideoFileOperationResult(bool Applied, string? Reason);
```

---

## 2. Downloader Implementation Archetypes

### Archetype A: Direct HTTP Media Stream
Stream response content directly to `Path.Combine(host.TempDirectory, filename)` with progress reporting:

```csharp
using var response = await client.GetAsync(mediaStreamUrl, HttpCompletionOption.ResponseHeadersRead, ct);
response.EnsureSuccessStatusCode();

var totalBytes = response.Content.Headers.ContentLength;
using var contentStream = await response.Content.ReadAsStreamAsync(ct);
using var fileStream = File.Create(tempFile);

var buffer = new byte[81920];
long totalRead = 0;
int read;

while ((read = await contentStream.ReadAsync(buffer, ct)) > 0)
{
    await fileStream.WriteAsync(buffer.AsMemory(0, read), ct);
    totalRead += read;
    if (totalBytes.HasValue && totalBytes.Value > 0)
    {
        double pct = (double)totalRead / totalBytes.Value * 100.0;
        host.ReportProgress(pct, $"{totalRead / 1048576} MB / {totalBytes.Value / 1048576} MB");
    }
}
```

### Archetype B: External Binary Delegation (`Divert = true`)
For services where an external tool (e.g. `yt-dlp` or `ffmpeg`) handles token generation or segmented streams, return `Divert = true` in `DownloaderUrlMatch`. Cove delegates execution to the external runtime while maintaining progress hooks.

### Archetype C: Multi-Image Gallery ZIP
For multi-image photo sets, download individual images into a temporary folder and package them into a `.zip` archive:
```csharp
var zipPath = Path.Combine(host.TempDirectory, $"{galleryCode}.zip");
ZipFile.CreateFromDirectory(imagesDir, zipPath);
return new DownloaderResult(
    LocalPath: zipPath,
    OriginalFilename: $"{galleryCode}.zip",
    InlineGalleryMetadata: scrapedGallery
);
```
