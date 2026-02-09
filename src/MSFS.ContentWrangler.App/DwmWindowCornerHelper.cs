using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;

namespace MSFS.ContentWrangler.App;

internal static class DwmWindowCornerHelper
{
    // Windows 11 rounded corners are controlled via DwmSetWindowAttribute(DWMWA_WINDOW_CORNER_PREFERENCE).
    private const int DWMWA_WINDOW_CORNER_PREFERENCE = 33;

    internal enum CornerPreference
    {
        Default = 0,
        DoNotRound = 1,
        Round = 2,
        RoundSmall = 3,
    }

    [DllImport("dwmapi.dll", ExactSpelling = true)]
    private static extern int DwmSetWindowAttribute(nint hwnd, int dwAttribute, ref int pvAttribute, int cbAttribute);

    public static void TryApply(Window window, bool isMaximized)
    {
        // Build 22000 = Windows 11 initial release. Older OSes just won't have the same behavior.
        if (!OperatingSystem.IsWindowsVersionAtLeast(10, 0, 22000))
        {
            return;
        }

        try
        {
            var hwnd = new WindowInteropHelper(window).Handle;
            if (hwnd == nint.Zero)
            {
                return;
            }

            var pref = isMaximized ? CornerPreference.DoNotRound : CornerPreference.Round;
            var v = (int)pref;
            _ = DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ref v, sizeof(int));
        }
        catch
        {
            // Best-effort only; never crash the app for cosmetic options.
        }
    }
}

