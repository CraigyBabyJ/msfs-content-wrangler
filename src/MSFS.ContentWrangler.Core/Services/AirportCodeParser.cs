using System.Text.RegularExpressions;

namespace MSFS.ContentWrangler.Core.Services;

public static class AirportCodeParser
{
    private static readonly Regex RxAfterAirport = new(
        "(?i)\\b(?:airport|airfield|aerodrome|heliport|seaplane[-_ ]base)[-_ ]+([a-z0-9]{3,5})\\b",
        RegexOptions.Compiled);

    private static readonly Regex RxStrict4 = new("^[A-Z][A-Z0-9]{3}$", RegexOptions.Compiled);
    private static readonly Regex RxLen3To5 = new("^[A-Z0-9]{3,5}$", RegexOptions.Compiled);

    public static string? ParseAirportCodeFromName(string? packageName)
    {
        if (string.IsNullOrWhiteSpace(packageName))
        {
            return null;
        }

        var match = RxAfterAirport.Match(packageName);
        if (match.Success)
        {
            var cand = match.Groups[1].Value.ToUpperInvariant();
            if (RxStrict4.IsMatch(cand) || RxLen3To5.IsMatch(cand))
            {
                return cand;
            }
        }

        var parts = Regex.Split(packageName.ToLowerInvariant(), "[-_. ]+");
        var keywords = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "airport",
            "airfield",
            "aerodrome",
            "heliport",
            "seaplane",
            "seaplane-base",
        };

        var idx = Array.FindIndex(parts, p => keywords.Contains(p));
        if (idx < 0)
        {
            return null;
        }

        var window = parts.Skip(idx + 1).Take(4).Select(p => p.ToUpperInvariant()).ToList();

        foreach (var tok in window)
        {
            if (RxStrict4.IsMatch(tok))
            {
                return tok;
            }
        }
        foreach (var tok in window)
        {
            if (RxLen3To5.IsMatch(tok))
            {
                return tok;
            }
        }

        return null;
    }
}
