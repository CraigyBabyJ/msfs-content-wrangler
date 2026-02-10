using System.Text.Json;
using MSFS.ContentWrangler.Core.Models;

namespace MSFS.ContentWrangler.Core.Services;

public static class RulesStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
    };

    public static Rules Load(string path)
    {
        try
        {
            if (!string.IsNullOrWhiteSpace(path) && File.Exists(path))
            {
                var json = File.ReadAllText(path);
                var rules = JsonSerializer.Deserialize<Rules>(json, Options);
                if (rules != null)
                {
                    return rules;
                }
            }
        }
        catch
        {
            // ignore and fall back to defaults
        }
        return Categorizer.DefaultRules;
    }

    public static Rules Load(Stream stream)
    {
        try
        {
            var rules = JsonSerializer.Deserialize<Rules>(stream, Options);
            if (rules != null)
            {
                return rules;
            }
        }
        catch
        {
            // ignore
        }
        return Categorizer.DefaultRules;
    }

    public static void Save(string path, Rules rules)
    {
        try
        {
            var dir = Path.GetDirectoryName(path);
            if (!string.IsNullOrWhiteSpace(dir))
            {
                Directory.CreateDirectory(dir);
            }
            var json = JsonSerializer.Serialize(rules, Options);
            File.WriteAllText(path, json);
        }
        catch
        {
            // swallow errors; caller can surface as needed
        }
    }
}
