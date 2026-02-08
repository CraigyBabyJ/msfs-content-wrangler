using System;
using System.Globalization;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;
using MSFS.ContentWrangler.Core.Models;

namespace MSFS.ContentWrangler.App;

public sealed class StatusToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        var status = value as string ?? string.Empty;
        var resources = Application.Current.Resources;

        if (status == PackageStatus.Activated)
        {
            return resources["AccentBrush"] as Brush ?? Brushes.LimeGreen;
        }
        if (status == PackageStatus.UserDisabled)
        {
            return resources["DangerBrush"] as Brush ?? Brushes.IndianRed;
        }
        if (status == PackageStatus.SystemDisabled)
        {
            return resources["WarningBrush"] as Brush ?? Brushes.Goldenrod;
        }
        return resources["TextSecondaryBrush"] as Brush ?? Brushes.Gray;
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
    {
        throw new NotSupportedException();
    }
}
