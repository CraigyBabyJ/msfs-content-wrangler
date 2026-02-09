namespace MSFS.ContentWrangler.App;

public sealed class LinkItem
{
    public LinkItem(string label, Uri uri, string iconFileName)
    {
        Label = label;
        Uri = uri;
        IconFileName = iconFileName;
    }

    public string Label { get; }
    public Uri Uri { get; }
    public string IconFileName { get; }
}
