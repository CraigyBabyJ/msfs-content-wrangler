using System.Globalization;
using System.IO;
using System.Net;
using System.Windows.Data;
using System.Windows.Media;
using System.Xml.Linq;

namespace MSFS.ContentWrangler.App;

// Minimal SVG support for footer icons (path/circle/ellipse/line). We ignore styling.
public sealed class SvgFileToGeometryConverter : IValueConverter
{
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

            var svgText = File.ReadAllText(path);
            var group = new GeometryGroup();
            XDocument doc;
            try
            {
                doc = XDocument.Parse(svgText);
            }
            catch
            {
                // Some SVGs might include leading/trailing junk; try a looser parse.
                doc = XDocument.Parse(svgText.Trim());
            }

            foreach (var el in doc.Descendants())
            {
                switch (el.Name.LocalName.ToLowerInvariant())
                {
                    case "path":
                    {
                        var d = el.Attribute("d")?.Value;
                        if (string.IsNullOrWhiteSpace(d))
                        {
                            break;
                        }

                        d = WebUtility.HtmlDecode(d);
                        try
                        {
                            group.Children.Add(Geometry.Parse(d));
                        }
                        catch
                        {
                            // Skip invalid path segments.
                        }

                        break;
                    }
                    case "circle":
                    {
                        if (!TryGetDouble(el, "cx", out var cx) ||
                            !TryGetDouble(el, "cy", out var cy) ||
                            !TryGetDouble(el, "r", out var r))
                        {
                            break;
                        }

                        group.Children.Add(new EllipseGeometry(new System.Windows.Point(cx, cy), r, r));
                        break;
                    }
                    case "ellipse":
                    {
                        if (!TryGetDouble(el, "cx", out var cx) ||
                            !TryGetDouble(el, "cy", out var cy) ||
                            !TryGetDouble(el, "rx", out var rx) ||
                            !TryGetDouble(el, "ry", out var ry))
                        {
                            break;
                        }

                        group.Children.Add(new EllipseGeometry(new System.Windows.Point(cx, cy), rx, ry));
                        break;
                    }
                    case "line":
                    {
                        if (!TryGetDouble(el, "x1", out var x1) ||
                            !TryGetDouble(el, "y1", out var y1) ||
                            !TryGetDouble(el, "x2", out var x2) ||
                            !TryGetDouble(el, "y2", out var y2))
                        {
                            break;
                        }

                        group.Children.Add(new LineGeometry(new System.Windows.Point(x1, y1), new System.Windows.Point(x2, y2)));
                        break;
                    }
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

    private static bool TryGetDouble(XElement el, string attrName, out double value)
    {
        value = 0;
        var s = el.Attribute(attrName)?.Value;
        if (string.IsNullOrWhiteSpace(s))
        {
            return false;
        }

        // Strip a trailing "px" if present.
        s = s.Trim();
        if (s.EndsWith("px", StringComparison.OrdinalIgnoreCase))
        {
            s = s[..^2];
        }

        return double.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out value);
    }
}
