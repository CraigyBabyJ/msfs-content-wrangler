using System.Text.Json.Serialization;

namespace MSFS.ContentWrangler.Core.Models;

public sealed class Rules
{
    [JsonPropertyName("categories")]
    public List<CategoryRule> Categories { get; set; } = new();

    [JsonPropertyName("defaultCategory")]
    public string DefaultCategory { get; set; } = "Other";
}

public sealed class CategoryRule
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("patterns")]
    public List<string> Patterns { get; set; } = new();
}
