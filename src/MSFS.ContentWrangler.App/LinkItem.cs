namespace MSFS.ContentWrangler.App;

public sealed class LinkItem
{
    public LinkItem(string label, Uri uri)
    {
        Label = label;
        Uri = uri;
    }

    public string Label { get; }
    public Uri Uri { get; }
}
