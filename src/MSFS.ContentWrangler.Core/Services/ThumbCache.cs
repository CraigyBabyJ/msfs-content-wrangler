using System.Text.Json;
using System.Text.RegularExpressions;

namespace MSFS.ContentWrangler.Core.Services;

public sealed class ThumbCache
{
    private const string CacheDirName = "cache";
    private const string CacheFileName = "thumbnails.json";
    private static readonly string[] ThumbExts = [".png", ".jpg", ".jpeg", ".webp"];

    private readonly object _dbLock = new();
    private Dictionary<string, ThumbEntry> _db = new(StringComparer.OrdinalIgnoreCase);
    private DateTime _lastSave = DateTime.MinValue;
    private bool _pending;

    public ThumbCache(string contentXmlPath)
    {
        ContentXmlPath = contentXmlPath;
        LocalCache = FindLocalCacheRoot(contentXmlPath);
        InstalledRoot = InstalledPackagesRoot(LocalCache);

        var appDir = AppContext.BaseDirectory;
        CacheDir = Path.Combine(appDir, CacheDirName);
        Directory.CreateDirectory(CacheDir);
        CachePath = Path.Combine(CacheDir, CacheFileName);

        if (!File.Exists(CachePath))
        {
            File.WriteAllText(CachePath, "{}");
        }

        _db = LoadDb();

        Fs20LocalCache = FindMsStoreLocalCache("Microsoft.FlightSimulator_8wekyb3d8bbwe");
        Fs20Installed = InstalledPackagesRoot(Fs20LocalCache);
    }

    public string ContentXmlPath { get; }
    public string CacheDir { get; }
    public string CachePath { get; }
    public string LocalCache { get; }
    public string? InstalledRoot { get; }
    public string? Fs20LocalCache { get; }
    public string? Fs20Installed { get; }

    public void SetKnownPath(string name, string path)
    {
        if (string.IsNullOrWhiteSpace(name) || string.IsNullOrWhiteSpace(path))
        {
            return;
        }
        if (!File.Exists(path))
        {
            return;
        }

        var mtime = File.GetLastWriteTimeUtc(path).ToOADate();
        lock (_dbLock)
        {
            _db[name] = new ThumbEntry { Path = path, MTime = mtime, Source = "content.xml" };
        }
        SaveDbThrottled();
    }

    public void Forget(string name)
    {
        lock (_dbLock)
        {
            _db.Remove(name);
        }
        var png = Path.Combine(CacheDir, "thumbs", $"{name}.png");
        if (File.Exists(png))
        {
            try { File.Delete(png); } catch { }
        }
        SaveDbNow();
    }

    public void ClearAll()
    {
        lock (_dbLock)
        {
            _db.Clear();
        }
        var thumbsDir = Path.Combine(CacheDir, "thumbs");
        if (Directory.Exists(thumbsDir))
        {
            foreach (var p in Directory.EnumerateFiles(thumbsDir, "*.png"))
            {
                try { File.Delete(p); } catch { }
            }
        }
        SaveDbNow();
    }

    public async Task EnsureThumbnailPathAsync(string packageName, string source, string sim)
    {
        await Task.Run(() => EnsureThumbnailPath(packageName, source, sim));
    }

    public string? GetKnownPath(string name)
    {
        lock (_dbLock)
        {
            if (_db.TryGetValue(name, out var entry))
            {
                return string.IsNullOrWhiteSpace(entry.Path) ? null : entry.Path;
            }
        }
        return null;
    }

    public string GetScanStatus(string name)
    {
        lock (_dbLock)
        {
            if (!_db.TryGetValue(name, out var entry))
            {
                return "unknown";
            }
            if (string.IsNullOrWhiteSpace(entry.Path))
            {
                return "missing";
            }
            return File.Exists(entry.Path) ? "found" : "missing";
        }
    }

    private void EnsureThumbnailPath(string packageName, string source, string sim)
    {
        ThumbEntry? entry = null;
        lock (_dbLock)
        {
            _db.TryGetValue(packageName, out entry);
        }

        if (entry != null && !string.IsNullOrWhiteSpace(entry.Path) && File.Exists(entry.Path))
        {
            try
            {
                var mtime = File.GetLastWriteTimeUtc(entry.Path).ToOADate();
                if (Math.Abs(mtime - entry.MTime) < 0.001)
                {
                    if (_pending)
                    {
                        SaveDbThrottled();
                    }
                    return;
                }
            }
            catch
            {
                // continue to rescan
            }
        }

        string? found = null;
        try
        {
            found = DiscoverThumbnail(packageName, source, sim);
        }
        catch
        {
            found = null;
        }

        if (string.IsNullOrWhiteSpace(found))
        {
            lock (_dbLock)
            {
                _db[packageName] = new ThumbEntry { Path = string.Empty, MTime = 0.0, Source = "none" };
            }
            SaveDbThrottled();
            return;
        }

        var sourceTag = found.ToLowerInvariant().Contains("contentinfo") || Path.GetFileName(found).StartsWith("thumbnail", StringComparison.OrdinalIgnoreCase)
            ? "layout.json"
            : "search";

        var mtimeFound = File.GetLastWriteTimeUtc(found).ToOADate();
        lock (_dbLock)
        {
            _db[packageName] = new ThumbEntry { Path = found, MTime = mtimeFound, Source = sourceTag };
        }
        SaveDbThrottled();
    }

    private Dictionary<string, ThumbEntry> LoadDb()
    {
        try
        {
            var json = File.ReadAllText(CachePath);
            var data = JsonSerializer.Deserialize<Dictionary<string, ThumbEntry>>(json);
            return data ?? new Dictionary<string, ThumbEntry>(StringComparer.OrdinalIgnoreCase);
        }
        catch
        {
            return new Dictionary<string, ThumbEntry>(StringComparer.OrdinalIgnoreCase);
        }
    }

    private void SaveDbNow()
    {
        Dictionary<string, ThumbEntry> snapshot;
        lock (_dbLock)
        {
            snapshot = new Dictionary<string, ThumbEntry>(_db, StringComparer.OrdinalIgnoreCase);
        }

        var json = JsonSerializer.Serialize(snapshot, new JsonSerializerOptions { WriteIndented = true });
        var tmp = Path.Combine(CacheDir, $"{Path.GetFileNameWithoutExtension(CachePath)}.{Environment.ProcessId}.{Thread.CurrentThread.ManagedThreadId}.tmp");

        try
        {
            File.WriteAllText(tmp, json);
            File.Copy(tmp, CachePath, true);
        }
        catch
        {
            try { File.WriteAllText(CachePath, json); } catch { }
        }
        finally
        {
            try { File.Delete(tmp); } catch { }
        }

        _lastSave = DateTime.UtcNow;
        _pending = false;
    }

    private void SaveDbThrottled()
    {
        if ((DateTime.UtcNow - _lastSave).TotalSeconds >= 0.5)
        {
            SaveDbNow();
        }
        else
        {
            _pending = true;
        }
    }

    private static string FindLocalCacheRoot(string contentXmlPath)
    {
        var dir = Path.GetDirectoryName(contentXmlPath) ?? string.Empty;
        var current = new DirectoryInfo(dir);
        while (current != null)
        {
            if (current.Name.Equals("LocalCache", StringComparison.OrdinalIgnoreCase))
            {
                return current.FullName;
            }
            current = current.Parent;
        }

        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(local, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache");
    }

    private static string? FindMsStoreLocalCache(string packageId)
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var cand = Path.Combine(local, "Packages", packageId, "LocalCache");
        return Directory.Exists(cand) ? cand : null;
    }

    private static string? InstalledPackagesRoot(string? localCache)
    {
        if (string.IsNullOrWhiteSpace(localCache))
        {
            return null;
        }

        var candidates = new List<string>
        {
            Path.Combine(localCache, "UserCfg.opt"),
            Path.Combine(Directory.GetParent(localCache)!.FullName, "LocalCache", "UserCfg.opt")
        };

        foreach (var f in candidates)
        {
            if (!File.Exists(f)) continue;
            try
            {
                var txt = File.ReadAllText(f);
                var m = Regex.Match(txt, "InstalledPackagesPath\\s+\"([^\"]+)\"");
                if (m.Success)
                {
                    var path = Environment.ExpandEnvironmentVariables(m.Groups[1].Value);
                    if (Directory.Exists(path))
                    {
                        return path;
                    }
                }
            }
            catch
            {
                // ignore
            }
        }

        var fallback = Path.Combine(localCache, "Packages");
        return Directory.Exists(fallback) ? fallback : null;
    }

    private IEnumerable<string> Official24Roots()
    {
        return new[]
        {
            Path.Combine(InstalledRoot ?? string.Empty, "Official2024", "OneStore"),
            Path.Combine(InstalledRoot ?? string.Empty, "Official", "OneStore"),
            Path.Combine(LocalCache, "Packages", "Official2024", "OneStore"),
            Path.Combine(LocalCache, "Packages", "Official", "OneStore"),
            Path.Combine(Directory.GetParent(LocalCache)!.FullName, "LocalState", "packages", "Official2024", "OneStore"),
            Path.Combine(Directory.GetParent(LocalCache)!.FullName, "LocalState", "packages", "Official", "OneStore"),
        };
    }

    private IEnumerable<string> Official20Roots()
    {
        var roots = new List<string>
        {
            Path.Combine(InstalledRoot ?? string.Empty, "Official2020", "OneStore"),
            Path.Combine(InstalledRoot ?? string.Empty, "Official", "OneStore"),
            Path.Combine(LocalCache, "Packages", "Official2020", "OneStore"),
            Path.Combine(LocalCache, "Packages", "Official", "OneStore"),
            Path.Combine(Directory.GetParent(LocalCache)!.FullName, "LocalState", "packages", "Official2020", "OneStore"),
            Path.Combine(Directory.GetParent(LocalCache)!.FullName, "LocalState", "packages", "Official", "OneStore"),
        };

        if (!string.IsNullOrWhiteSpace(Fs20Installed))
        {
            roots.Add(Path.Combine(Fs20Installed, "Official2020", "OneStore"));
            roots.Add(Path.Combine(Fs20Installed, "Official", "OneStore"));
        }

        if (!string.IsNullOrWhiteSpace(Fs20LocalCache))
        {
            roots.Add(Path.Combine(Fs20LocalCache, "Packages", "Official2020", "OneStore"));
            roots.Add(Path.Combine(Fs20LocalCache, "Packages", "Official", "OneStore"));
            roots.Add(Path.Combine(Directory.GetParent(Fs20LocalCache)!.FullName, "LocalState", "packages", "Official2020", "OneStore"));
            roots.Add(Path.Combine(Directory.GetParent(Fs20LocalCache)!.FullName, "LocalState", "packages", "Official", "OneStore"));
        }

        roots.AddRange(new[]
        {
            @"C:\XboxGames\Microsoft Flight Simulator\Content\Official2020\OneStore",
            @"C:\XboxGames\Microsoft Flight Simulator\Content\Official\OneStore",
            @"C:\XboxGames\Microsoft Flight Simulator Premium Deluxe\Content\Official2020\OneStore",
            @"C:\XboxGames\Microsoft Flight Simulator Premium Deluxe\Content\Official\OneStore",
        });

        return roots;
    }

    private IEnumerable<string> CommunityRoots()
    {
        return new[]
        {
            Path.Combine(InstalledRoot ?? string.Empty, "Community2024"),
            Path.Combine(InstalledRoot ?? string.Empty, "Community"),
            Path.Combine(LocalCache, "Packages", "Community2024"),
            Path.Combine(LocalCache, "Packages", "Community"),
            Path.Combine(Directory.GetParent(LocalCache)!.FullName, "LocalState", "packages", "Community2024"),
            Path.Combine(Directory.GetParent(LocalCache)!.FullName, "LocalState", "packages", "Community"),
        };
    }

    private string? DiscoverThumbnail(string packageName, string source, string sim)
    {
        var folderName = StripPrefix(packageName);
        var baseFolder = Regex.Split(folderName, "-livery-", RegexOptions.IgnoreCase)[0];

        IEnumerable<string> roots = source switch
        {
            "official" when sim == "fs24" => Official24Roots(),
            "official" when sim == "fs20" => Official20Roots(),
            _ => CommunityRoots(),
        };

        var want = Tokens(baseFolder);

        foreach (var root in roots)
        {
            if (string.IsNullOrWhiteSpace(root)) continue;

            var exacts = new[]
            {
                Path.Combine(root, baseFolder),
                Path.Combine(root, folderName),
                Path.Combine(root, packageName)
            };

            var foundDir = exacts.FirstOrDefault(Directory.Exists);

            if (foundDir == null && Directory.Exists(root))
            {
                try
                {
                    foreach (var dir in Directory.EnumerateDirectories(root))
                    {
                        var tokens = Tokens(Path.GetFileName(dir));
                        if (want.All(tokens.Contains))
                        {
                            foundDir = dir;
                            break;
                        }
                    }
                }
                catch
                {
                    // ignore
                }
            }

            if (foundDir == null)
            {
                continue;
            }

            var viaLayout = DiscoverViaLayout(foundDir);
            if (!string.IsNullOrWhiteSpace(viaLayout))
            {
                return viaLayout;
            }

            var contentInfo = Path.Combine(foundDir, "ContentInfo");
            if (Directory.Exists(contentInfo))
            {
                foreach (var ext in ThumbExts)
                {
                    var files = Directory.EnumerateFiles(contentInfo, "*" + ext, SearchOption.AllDirectories).ToList();
                    if (files.Count > 0)
                    {
                        return files[0];
                    }
                }
            }
        }

        return null;
    }

    private string? DiscoverViaLayout(string pkgDir)
    {
        var layout = Path.Combine(pkgDir, "layout.json");
        if (!File.Exists(layout))
        {
            return null;
        }

        JsonElement content;
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(layout));
            if (!doc.RootElement.TryGetProperty("content", out content))
            {
                return null;
            }
        }
        catch
        {
            return null;
        }

        var relPaths = new List<string>();
        if (content.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in content.EnumerateArray())
            {
                if (item.ValueKind == JsonValueKind.Object && item.TryGetProperty("path", out var pathProp))
                {
                    if (pathProp.ValueKind == JsonValueKind.String)
                    {
                        relPaths.Add(pathProp.GetString() ?? string.Empty);
                    }
                }
                else if (item.ValueKind == JsonValueKind.String)
                {
                    relPaths.Add(item.GetString() ?? string.Empty);
                }
            }
        }

        if (relPaths.Count == 0)
        {
            return null;
        }

        static bool IsImg(string p)
        {
            var low = p.ToLowerInvariant();
            return ThumbExts.Any(ext => low.EndsWith(ext));
        }

        var pairs = relPaths.Select(rp => (Raw: rp, Low: rp.ToLowerInvariant())).ToList();

        foreach (var (raw, low) in pairs)
        {
            if (IsImg(low) && low.StartsWith("contentinfo/") && low.Contains("/thumbnail") && Path.GetFileName(low).StartsWith("thumbnail"))
            {
                var full = Path.Combine(pkgDir, raw);
                if (File.Exists(full)) return full;
            }
        }

        foreach (var (raw, low) in pairs)
        {
            if (IsImg(low) && low.StartsWith("contentinfo/") && low.Contains("/screenshot"))
            {
                var full = Path.Combine(pkgDir, raw);
                if (File.Exists(full)) return full;
            }
        }

        foreach (var (raw, low) in pairs)
        {
            if (IsImg(low) && low.StartsWith("contentinfo/"))
            {
                var full = Path.Combine(pkgDir, raw);
                if (File.Exists(full)) return full;
            }
        }

        foreach (var (raw, low) in pairs)
        {
            if (IsImg(low) && low.StartsWith("simobjects/airplanes/") && low.Contains("thumbnail"))
            {
                var full = Path.Combine(pkgDir, raw);
                if (File.Exists(full)) return full;
            }
        }

        return null;
    }

    private static HashSet<string> Tokens(string? input)
    {
        return new HashSet<string>(
            Regex.Split(input ?? string.Empty, "[-_\\s]+")
                .Where(s => !string.IsNullOrWhiteSpace(s))
                .Select(s => s.ToLowerInvariant()),
            StringComparer.OrdinalIgnoreCase);
    }

    private static string StripPrefix(string name)
    {
        foreach (var pref in new[] { "fs24-", "fs20-", "communityfs24-", "communityfs20-" })
        {
            if (name.StartsWith(pref, StringComparison.OrdinalIgnoreCase))
            {
                return name[pref.Length..];
            }
        }
        return name;
    }

    private sealed class ThumbEntry
    {
        public string Path { get; set; } = string.Empty;
        public double MTime { get; set; }
        public string Source { get; set; } = string.Empty;
    }
}
