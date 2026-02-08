using System.Globalization;
using System.Xml;
using System.Xml.Linq;
using MSFS.ContentWrangler.Core.Models;

namespace MSFS.ContentWrangler.Core.Services;

public static class ContentXmlService
{
    private const string LimitlessPkg = "Microsoft.Limitless_8wekyb3d8bbwe";
    private static readonly string[] ThumbnailPatterns =
    [
        "thumbnail.jpg",
        "thumbnail.png",
        "screenshot.jpg",
        "screenshot.png",
        "*.jpg",
        "*.png"
    ];

    public static string LocalCacheDir()
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(local, "Packages", LimitlessPkg, "LocalCache");
    }

    public static IReadOnlyList<ProfileFile> ListContentXmlCandidates()
    {
        var baseDir = LocalCacheDir();
        if (!Directory.Exists(baseDir))
        {
            return Array.Empty<ProfileFile>();
        }

        var results = new List<ProfileFile>();
        var root = Path.Combine(baseDir, "Content.xml");
        if (File.Exists(root))
        {
            results.Add(new ProfileFile(root, false, "LocalCache", File.GetLastWriteTimeUtc(root)));
        }

        foreach (var dir in Directory.EnumerateDirectories(baseDir))
        {
            var candidate = Path.Combine(dir, "Content.xml");
            if (File.Exists(candidate))
            {
                var name = Path.GetFileName(dir);
                results.Add(new ProfileFile(candidate, true, name, File.GetLastWriteTimeUtc(candidate)));
            }
        }

        return results
            .OrderByDescending(p => p.IsProfile)
            .ThenByDescending(p => p.MTime)
            .ToList();
    }

    public static string? BestContentXml()
    {
        return ListContentXmlCandidates().FirstOrDefault()?.Path;
    }

    public static List<PackageRow> LoadPackages(string xmlPath, Rules rules)
    {
        if (!File.Exists(xmlPath))
        {
            return new List<PackageRow>();
        }

        var doc = XDocument.Load(xmlPath);
        var packages = doc.Root?.Elements("Package") ?? Enumerable.Empty<XElement>();

        var rows = new List<PackageRow>();
        var idx = 0;
        foreach (var el in packages)
        {
            var name = (string?)el.Attribute("name") ?? string.Empty;
            var status = (string?)el.Attribute("active") ?? PackageStatus.Activated;
            var (source, sim) = Categorizer.DeriveSourceAndSim(name);
            var category = Categorizer.Categorize(name, rules);
            var vendor = Categorizer.DeriveVendor(name);
            var thumbPath = FindThumbnail(name, source, xmlPath);

            var row = new PackageRow(name, status, idx)
            {
                Source = source,
                Sim = sim,
                Category = category,
                Vendor = vendor,
                ThumbnailPath = thumbPath
            };
            rows.Add(row);
            idx++;
        }

        return rows;
    }

    public static string BackupContent(string xmlPath)
    {
        var dir = Path.GetDirectoryName(xmlPath) ?? string.Empty;
        var baseName = Path.GetFileNameWithoutExtension(xmlPath);
        var ext = Path.GetExtension(xmlPath);
        var dest = Path.Combine(dir, $"{baseName}_backup{ext}");
        File.Copy(xmlPath, dest, true);
        return dest;
    }

    public static int SavePackages(string xmlPath, IEnumerable<PackageRow> rows, bool cleanLegacyFs20)
    {
        var doc = XDocument.Load(xmlPath);
        var root = doc.Root;
        if (root == null)
        {
            return 0;
        }

        var removedCount = 0;
        if (cleanLegacyFs20)
        {
            var toRemove = root.Elements("Package")
                .Where(el => ((string?)el.Attribute("name"))?.StartsWith("communityfs20-", StringComparison.OrdinalIgnoreCase) == true)
                .ToList();

            foreach (var el in toRemove)
            {
                el.Remove();
            }
            removedCount = toRemove.Count;
        }

        var statusMap = rows.ToDictionary(r => r.Name, r => r.Status, StringComparer.OrdinalIgnoreCase);
        foreach (var el in root.Elements("Package"))
        {
            var name = (string?)el.Attribute("name") ?? string.Empty;
            if (statusMap.TryGetValue(name, out var status))
            {
                el.SetAttributeValue("active", status);
            }
        }

        var dirPath = Path.GetDirectoryName(xmlPath) ?? string.Empty;
        var tmpPath = Path.Combine(dirPath, $"Content_{Guid.NewGuid():N}.xml");

        var settings = new XmlWriterSettings
        {
            OmitXmlDeclaration = true,
            Indent = false,
            NewLineHandling = NewLineHandling.None
        };

        using (var writer = XmlWriter.Create(tmpPath, settings))
        {
            doc.Save(writer);
        }

        File.Move(tmpPath, xmlPath, true);
        return removedCount;
    }

    private static string? FindThumbnail(string packageName, string packageSource, string contentXmlPath)
    {
        try
        {
            var xmlDir = Path.GetDirectoryName(contentXmlPath);
            if (xmlDir == null)
            {
                return null;
            }
            var basePath = Directory.GetParent(xmlDir)?.FullName;
            if (string.IsNullOrWhiteSpace(basePath))
            {
                return null;
            }

            var folderName = CultureInfo.InvariantCulture.TextInfo.ToTitleCase(packageSource);
            var packageFolder = Path.Combine(basePath, folderName, packageName);
            if (!Directory.Exists(packageFolder))
            {
                return null;
            }

            foreach (var pattern in ThumbnailPatterns)
            {
                var found = Directory.EnumerateFiles(packageFolder, pattern, SearchOption.TopDirectoryOnly).ToList();
                if (found.Count == 0)
                {
                    continue;
                }
                found.Sort((a, b) =>
                {
                    var aName = Path.GetFileName(a).ToLowerInvariant();
                    var bName = Path.GetFileName(b).ToLowerInvariant();
                    var aPref = aName is "thumbnail.jpg" or "thumbnail.png" ? 0 : 1;
                    var bPref = bName is "thumbnail.jpg" or "thumbnail.png" ? 0 : 1;
                    var prefCompare = aPref.CompareTo(bPref);
                    if (prefCompare != 0) return prefCompare;
                    var aSize = new FileInfo(a).Length;
                    var bSize = new FileInfo(b).Length;
                    return aSize.CompareTo(bSize);
                });
                return found[0];
            }
        }
        catch
        {
            // ignore
        }
        return null;
    }
}
