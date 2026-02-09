using System.IO;
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
                { "TikTok", "https://tiktok.com/@craigybabyj_new" },
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
                if (loaded.Links == null || loaded.Links.Count == 0)
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

    public void Save()
    {
        var json = JsonSerializer.Serialize(this, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(ConfigPath, json);
    }
}
