using System.IO;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using MSFS.ContentWrangler.Core.Services;

namespace MSFS.ContentWrangler.App;

public sealed class ThumbnailLoader
{
    private readonly ThumbCache _cache;
    private readonly Dispatcher _dispatcher;
    private readonly SemaphoreSlim _throttle = new(3, 3);
    private readonly HashSet<string> _inFlight = new(StringComparer.OrdinalIgnoreCase);

    public ThumbnailLoader(ThumbCache cache, Dispatcher dispatcher)
    {
        _cache = cache;
        _dispatcher = dispatcher;
    }

    public async Task QueueAsync(PackageRowViewModel row)
    {
        if (!_inFlight.Add(row.Name))
        {
            return;
        }

        await _throttle.WaitAsync();
        try
        {
            await UpdateRowAsync(row);
        }
        finally
        {
            _throttle.Release();
            _inFlight.Remove(row.Name);
        }
    }

    public async Task RefreshAsync(PackageRowViewModel row)
    {
        _cache.Forget(row.Name);
        await UpdateOnUIAsync(() =>
        {
            row.ThumbnailImage = null;
            row.ThumbnailState = ThumbnailState.Loading;
            row.ThumbnailToolTip = "Refreshing thumbnail...";
        });
        await QueueAsync(row);
    }

    private async Task UpdateRowAsync(PackageRowViewModel row)
    {
        var directPath = row.Model.ThumbnailPath;
        if (!string.IsNullOrWhiteSpace(directPath) && File.Exists(directPath))
        {
            _cache.SetKnownPath(row.Name, directPath);
            await UpdateOnUIAsync(() =>
            {
                row.ThumbnailImage = new BitmapImage(new Uri(directPath!, UriKind.Absolute));
                row.ThumbnailState = ThumbnailState.Found;
                row.ThumbnailToolTip = $"Original: {directPath}";
            });
            return;
        }

        var knownPath = _cache.GetKnownPath(row.Name);
        if (!string.IsNullOrWhiteSpace(knownPath) && File.Exists(knownPath))
        {
            await UpdateOnUIAsync(() =>
            {
                row.ThumbnailImage = new BitmapImage(new Uri(knownPath!, UriKind.Absolute));
                row.ThumbnailState = ThumbnailState.Found;
                row.ThumbnailToolTip = $"Original: {knownPath}";
            });
            return;
        }

        var status = _cache.GetScanStatus(row.Name);
        if (status == "missing")
        {
            await UpdateOnUIAsync(() =>
            {
                row.ThumbnailImage = null;
                row.ThumbnailState = ThumbnailState.Missing;
                row.ThumbnailToolTip = "No thumbnail found (already scanned).";
            });
            return;
        }

        await UpdateOnUIAsync(() =>
        {
            row.ThumbnailImage = null;
            row.ThumbnailState = ThumbnailState.Loading;
            row.ThumbnailToolTip = "Thumbnail not cached yet.\n(Will appear once discovered.)";
        });

        await _cache.EnsureThumbnailPathAsync(row.Name, row.Source, row.Sim);

        knownPath = _cache.GetKnownPath(row.Name);
        if (!string.IsNullOrWhiteSpace(knownPath) && File.Exists(knownPath))
        {
            await UpdateOnUIAsync(() =>
            {
                row.ThumbnailImage = new BitmapImage(new Uri(knownPath!, UriKind.Absolute));
                row.ThumbnailState = ThumbnailState.Found;
                row.ThumbnailToolTip = $"Original: {knownPath}";
            });
        }
        else
        {
            await UpdateOnUIAsync(() =>
            {
                row.ThumbnailImage = null;
                row.ThumbnailState = ThumbnailState.Missing;
                row.ThumbnailToolTip = "No thumbnail found (already scanned).";
            });
        }
    }

    private Task UpdateOnUIAsync(Action action)
    {
        var tcs = new TaskCompletionSource<bool>();
        _dispatcher.InvokeAsync(() =>
        {
            try
            {
                action();
                tcs.SetResult(true);
            }
            catch (Exception ex)
            {
                tcs.SetException(ex);
            }
        });
        return tcs.Task;
    }
}
