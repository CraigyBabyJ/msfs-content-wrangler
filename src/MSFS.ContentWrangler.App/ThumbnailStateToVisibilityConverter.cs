using System.Globalization;
using System.Windows;
using System.Windows.Data;

namespace MSFS.ContentWrangler.App;

public sealed class ThumbnailStateToVisibilityConverter : IValueConverter
{
    public ThumbnailState TargetState { get; set; }

    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        if (value is ThumbnailState state && state == TargetState)
        {
            return Visibility.Visible;
        }
        return Visibility.Collapsed;
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
    {
        throw new NotSupportedException();
    }
}
