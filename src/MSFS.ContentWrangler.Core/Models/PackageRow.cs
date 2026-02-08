using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace MSFS.ContentWrangler.Core.Models;

public sealed class PackageRow : INotifyPropertyChanged
{
    private string _status;
    private string _category;
    private string _vendor;
    private string _sim;
    private string _source;
    private string? _thumbnailPath;

    public PackageRow(string name, string status, int rawIndex)
    {
        Name = name;
        _status = status;
        RawIndex = rawIndex;
        OriginalStatus = status;
        _category = "Other";
        _vendor = string.Empty;
        _sim = "fs24";
        _source = "official";
    }

    public string Name { get; }

    public string Status
    {
        get => _status;
        set => SetField(ref _status, value);
    }

    public string OriginalStatus { get; set; }

    public int RawIndex { get; }

    public string Category
    {
        get => _category;
        set => SetField(ref _category, value);
    }

    public string Vendor
    {
        get => _vendor;
        set => SetField(ref _vendor, value);
    }

    public string Sim
    {
        get => _sim;
        set => SetField(ref _sim, value);
    }

    public string Source
    {
        get => _source;
        set => SetField(ref _source, value);
    }

    public string? ThumbnailPath
    {
        get => _thumbnailPath;
        set => SetField(ref _thumbnailPath, value);
    }

    public bool IsReadOnly => Status == PackageStatus.SystemDisabled;

    public event PropertyChangedEventHandler? PropertyChanged;

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
