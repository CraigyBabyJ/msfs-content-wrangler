using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Media;
using MSFS.ContentWrangler.Core.Models;

namespace MSFS.ContentWrangler.App;

public sealed class PackageRowViewModel : INotifyPropertyChanged
{
    public PackageRowViewModel(PackageRow model)
    {
        Model = model;
        Model.PropertyChanged += OnModelPropertyChanged;
    }

    public PackageRow Model { get; }

    public string Name => Model.Name;

    public string Status
    {
        get => Model.Status;
        set
        {
            if (Model.Status == value)
            {
                return;
            }
            Model.Status = value;
            OnPropertyChanged();
            OnPropertyChanged(nameof(IsSystemDisabled));
            OnPropertyChanged(nameof(IsToggleable));
        }
    }

    public string Category => Model.Category;
    public string Vendor => Model.Vendor;
    public string Sim => Model.Sim;
    public string Source => Model.Source;

    public bool IsSystemDisabled => Status == PackageStatus.SystemDisabled;
    public bool IsToggleable => !IsSystemDisabled;

    private ImageSource? _thumbnailImage;
    public ImageSource? ThumbnailImage
    {
        get => _thumbnailImage;
        set => SetField(ref _thumbnailImage, value);
    }

    private ThumbnailState _thumbnailState = ThumbnailState.Unknown;
    public ThumbnailState ThumbnailState
    {
        get => _thumbnailState;
        set => SetField(ref _thumbnailState, value);
    }

    private string _thumbnailToolTip = string.Empty;
    public string ThumbnailToolTip
    {
        get => _thumbnailToolTip;
        set => SetField(ref _thumbnailToolTip, value);
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    private void OnModelPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(PackageRow.Status))
        {
            OnPropertyChanged(nameof(Status));
            OnPropertyChanged(nameof(IsSystemDisabled));
            OnPropertyChanged(nameof(IsToggleable));
        }
        else if (e.PropertyName == nameof(PackageRow.Category))
        {
            OnPropertyChanged(nameof(Category));
        }
        else if (e.PropertyName == nameof(PackageRow.Vendor))
        {
            OnPropertyChanged(nameof(Vendor));
        }
    }

    private void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }

    private void SetField<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (Equals(field, value))
        {
            return;
        }
        field = value;
        OnPropertyChanged(propertyName);
    }
}
