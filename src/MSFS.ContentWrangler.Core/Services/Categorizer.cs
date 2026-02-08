using MSFS.ContentWrangler.Core.Models;

namespace MSFS.ContentWrangler.Core.Services;

public static class Categorizer
{
    public static Rules DefaultRules => new()
    {
        Categories =
        [
            new CategoryRule { Name = "Airport", Patterns = ["-airport-", "airport-"] },
            new CategoryRule { Name = "Aircraft", Patterns = ["-aircraft-"] },
            new CategoryRule { Name = "Livery", Patterns = ["-livery-"] },
            new CategoryRule { Name = "Scenery", Patterns = ["scenery", "cityscape", "landmarks"] },
            new CategoryRule
            {
                Name = "Library",
                Patterns = ["commonlibrary", "modellib", "material-lib", "-library-", "-lib", "lib-"]
            },
            new CategoryRule
            {
                Name = "Missions",
                Patterns = ["activities", "challenges", "mission", "training", "discovery", "travelbook"]
            },
            new CategoryRule { Name = "Utilities", Patterns = ["jetways", "toolbar", "gsx", "flow"] }
        ],
        DefaultCategory = "Other"
    };

    public static string Categorize(string name, Rules rules)
    {
        var n = (name ?? string.Empty).ToLowerInvariant();
        foreach (var cat in rules.Categories)
        {
            foreach (var pat in cat.Patterns)
            {
                if (n.Contains(pat, StringComparison.OrdinalIgnoreCase))
                {
                    return string.IsNullOrWhiteSpace(cat.Name) ? "Other" : cat.Name;
                }
            }
        }
        return string.IsNullOrWhiteSpace(rules.DefaultCategory) ? "Other" : rules.DefaultCategory;
    }

    public static (string Source, string Sim) DeriveSourceAndSim(string name)
    {
        var n = (name ?? string.Empty).ToLowerInvariant();

        if (n.StartsWith("communityfs24-")) return ("community", "fs24");
        if (n.StartsWith("communityfs20-")) return ("community", "fs20");
        if (n.StartsWith("fs24-")) return ("official", "fs24");
        if (n.StartsWith("fs20-")) return ("official", "fs20");

        var legacy2020Hints = new[]
        {
            "fs-base",
            "asobo-aircraft",
            "asobo-vcockpits",
            "microsoft-",
            "asobo-",
            "wombi",
        };

        if (legacy2020Hints.Any(h => n.Contains(h, StringComparison.OrdinalIgnoreCase)))
        {
            return ("official", "fs20");
        }

        return ("official", "fs24");
    }

    public static string DeriveVendor(string name)
    {
        var baseName = name ?? string.Empty;
        foreach (var prefix in new[] { "communityfs24-", "communityfs20-", "fs24-", "fs20-" })
        {
            if (baseName.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                baseName = baseName[prefix.Length..];
                break;
            }
        }

        var vendor = baseName.Split('-', StringSplitOptions.RemoveEmptyEntries).FirstOrDefault() ?? string.Empty;
        return vendor.ToLowerInvariant();
    }
}
