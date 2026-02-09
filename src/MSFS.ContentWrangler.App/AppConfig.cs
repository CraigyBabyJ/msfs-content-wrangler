using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MSFS.ContentWrangler.App;

public sealed class AppConfig
{
    [JsonPropertyName("content_xml_path")]
    public string ContentXmlPath { get; set; } = string.Empty;

    [JsonPropertyName("theme")]
    public string Theme { get; set; } = "dark";

    [JsonPropertyName("show_thumbnails")]
    public bool ShowThumbnails { get; set; } = false;

    [JsonPropertyName("clean_legacy_fs20")]
    public bool CleanLegacyFs20 { get; set; } = true;

    [JsonPropertyName("links")]
    public Dictionary<string, string> Links { get; set; } = new();

    public static string ConfigPath => Path.Combine(AppContext.BaseDirectory, "config.json");

    public static AppConfig Load()
    {
        var defaults = new AppConfig
        {
            Links = new Dictionary<string, string>
            {
                { "Discord", "https://discord.gg/ErQduaBqAg" },
                { "GitHub", "https://github.com/CraigyBabyJ/msfs-content-wrangler" },
                { "Website", "https://www.craigybabyj.com" },
                { "Buy Me a Coffee", "https://www.buymeacoffee.com/craigybabyj" },
            }
        };

        if (!File.Exists(ConfigPath))
        {
            return defaults;
        }

        try
        {
            var json = File.ReadAllText(ConfigPath);
            var loaded = JsonSerializer.Deserialize<AppConfig>(json, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            if (loaded != null)
            {
                loaded.Links ??= new Dictionary<string, string>();

                // Migrate legacy keys/URLs so the footer stays consistent across upgrades.
                RemoveLinkKeyInsensitive(loaded.Links, "TikTok");
                if (RemoveLinkKeyInsensitive(loaded.Links, "Donate"))
                {
                    // Replaced with Buy Me a Coffee.
                    if (!ContainsLinkKeyInsensitive(loaded.Links, "Buy Me a Coffee"))
                    {
                        loaded.Links["Buy Me a Coffee"] = defaults.Links["Buy Me a Coffee"];
                    }
                }

                // Update legacy website URL.
                if (TryGetLinkValueInsensitive(loaded.Links, "Website", out var website) &&
                    string.Equals(website?.Trim(), "https://craigybabyj.itch.io/", StringComparison.OrdinalIgnoreCase))
                {
                    loaded.Links["Website"] = defaults.Links["Website"];
                }

                if (loaded.Links.Count == 0)
                {
                    loaded.Links = defaults.Links;
                }
                return loaded;
            }
        }
        catch
        {
            // ignore and fall back to defaults
        }

        return defaults;
    }

    private static bool RemoveLinkKeyInsensitive(Dictionary<string, string> links, string key)
    {
        var found = links.Keys.FirstOrDefault(k => string.Equals(k, key, StringComparison.OrdinalIgnoreCase));
        if (found is null)
        {
            return false;
        }
        return links.Remove(found);
    }

    private static bool ContainsLinkKeyInsensitive(Dictionary<string, string> links, string key) =>
        links.Keys.Any(k => string.Equals(k, key, StringComparison.OrdinalIgnoreCase));

    private static bool TryGetLinkValueInsensitive(Dictionary<string, string> links, string key, out string? value)
    {
        var found = links.Keys.FirstOrDefault(k => string.Equals(k, key, StringComparison.OrdinalIgnoreCase));
        if (found is null)
        {
            value = null;
            return false;
        }
        value = links[found];
        return true;
    }

    public void Save()
    {
        var json = JsonSerializer.Serialize(this, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(ConfigPath, json);
    }
}
