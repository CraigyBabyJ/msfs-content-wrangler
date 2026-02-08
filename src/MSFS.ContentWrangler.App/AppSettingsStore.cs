using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MSFS.ContentWrangler.App;

public sealed class AppSettingsStore
{
    [JsonPropertyName("last_content_xml")]
    public string? LastContentXml { get; set; }

    [JsonPropertyName("window")]
    public WindowState? Window { get; set; }

    public static string SettingsPath => Path.Combine(AppContext.BaseDirectory, "settings.json");

    public static AppSettingsStore Load()
    {
        if (!File.Exists(SettingsPath))
        {
            return new AppSettingsStore();
        }

        try
        {
            var json = File.ReadAllText(SettingsPath);
            return JsonSerializer.Deserialize<AppSettingsStore>(json, new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
                   ?? new AppSettingsStore();
        }
        catch
        {
            return new AppSettingsStore();
        }
    }

    public void Save()
    {
        var json = JsonSerializer.Serialize(this, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(SettingsPath, json);
    }
}

public sealed class WindowState
{
    public int X { get; set; }
    public int Y { get; set; }
    public int Width { get; set; } = 1280;
    public int Height { get; set; } = 840;
    public bool Maximized { get; set; }
}
