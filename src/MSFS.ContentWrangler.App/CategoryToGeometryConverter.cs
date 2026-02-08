using System;
using System.Globalization;
using System.Windows.Data;
using System.Windows.Media;

namespace MSFS.ContentWrangler.App;

public sealed class CategoryToGeometryConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        var category = (value as string ?? string.Empty).ToLowerInvariant();

        if (category.Contains("airport") || category.Contains("airfield"))
        {
            return Geometry.Parse("M2,12 L12,2 L22,12 L12,22 Z");
        }

        if (category.Contains("livery") || category.Contains("aircraft") || category.Contains("plane"))
        {
            return Geometry.Parse("M2,12 L22,12 M12,2 L12,22 M5,6 L19,18 M5,18 L19,6");
        }

        if (category.Contains("scenery") || category.Contains("landmark"))
        {
            return Geometry.Parse("M3,20 L9,8 L15,16 L21,4 L21,20 Z");
        }

        if (category.Contains("utility") || category.Contains("tool"))
        {
            return Geometry.Parse("M6,6 L18,6 L18,18 L6,18 Z M9,9 L15,9 L15,15 L9,15 Z");
        }

        return Geometry.Parse("M4,6 L20,6 L20,18 L4,18 Z");
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
    {
        throw new NotSupportedException();
    }
}
