using System.Globalization;
using System.IO;
using System.Net;
using System.Text.RegularExpressions;
using System.Windows.Data;
using System.Windows.Media;

namespace MSFS.ContentWrangler.App;

// Minimal SVG support for simple icon files that contain one or more <path d="..."> elements.
// We only use the path "d" data and ignore strokes/fills/etc.
public sealed class SvgFileToGeometryConverter : IValueConverter
{
    private static readonly Regex PathDRegex = new("d\\s*=\\s*\"([^\"]+)\"", RegexOptions.IgnoreCase | RegexOptions.Compiled);
    private static readonly Dictionary<string, Geometry> Cache = new(StringComparer.OrdinalIgnoreCase);
    private static readonly object CacheLock = new();

    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        if (value is not string fileName || string.IsNullOrWhiteSpace(fileName))
        {
            return Geometry.Empty;
        }

        lock (CacheLock)
        {
            if (Cache.TryGetValue(fileName, out var cached))
            {
                return cached;
            }
        }

        var geom = LoadGeometry(fileName);
        lock (CacheLock)
        {
            Cache[fileName] = geom;
        }
        return geom;
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
        Binding.DoNothing;

    private static Geometry LoadGeometry(string fileName)
    {
        try
        {
            var path = Path.Combine(AppContext.BaseDirectory, "icons", fileName);
            if (!File.Exists(path))
            {
                return Geometry.Empty;
            }

            var svg = File.ReadAllText(path);
            var matches = PathDRegex.Matches(svg);
            if (matches.Count == 0)
            {
                return Geometry.Empty;
            }

            var group = new GeometryGroup();
            foreach (Match m in matches)
            {
                var d = WebUtility.HtmlDecode(m.Groups[1].Value);
                if (string.IsNullOrWhiteSpace(d))
                {
                    continue;
                }

                try
                {
                    group.Children.Add(Geometry.Parse(d));
                }
                catch
                {
                    // If a specific path can't be parsed, skip it rather than failing the whole icon.
                }
            }

            if (group.Children.Count == 0)
            {
                return Geometry.Empty;
            }

            group.Freeze();
            return group;
        }
        catch
        {
            return Geometry.Empty;
        }
    }
}

