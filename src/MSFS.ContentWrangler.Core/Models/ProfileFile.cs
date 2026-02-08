namespace MSFS.ContentWrangler.Core.Models;

public sealed record ProfileFile(string Path, bool IsProfile, string Name, DateTimeOffset MTime);
