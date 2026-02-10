# Changelog

All notable changes to this project will be documented in this file.

## [0.2.5] - 2026-02-10
- **CI Fix**: Fixed PowerShell syntax error in release workflow script.

## [0.2.4] - 2026-02-10
- **Build Fix**: Removed dependency on local `config.json` for release builds.

## [0.2.3] - 2026-02-09

### Added
- **Complete Rewrite in C# (WPF)**: Rebuilt the application from scratch using .NET 8 and WPF for native performance and better OS integration.
- **Modern UI**:
  - Custom window chrome with integrated title bar.
  - Fully dynamic Dark and Light themes.
  - Glassy/Acrylic design elements.
- **Package Management**:
  - Separate tabs for Official (FS2024), Official (FS2020), and Community content.
  - Real-time filtering by Category and Status.
  - Search functionality for finding specific packages.
- **Visual Enhancements**:
  - **Tooltips**: Added hover tooltips to package names showing the full file path.
  - **Thumbnails**: Automatic loading of package thumbnails (`layout.json` / `manifest.json` integration).
  - **Icons**: New application icon and footer social links.
- **Settings & Customization**:
  - Configurable categorization rules (Regex-based pattern matching).
  - Ability to manually select `Content.xml` location.
  - Thumbnail cache management.

### Fixed
- **Theme Issues**:
  - Resolved low contrast text in Light Theme (Save button, DataGrid selection).
  - Fixed "black artifact" corners on dialogs by enabling transparency.
  - Adjusted Dark Theme accent color brightness.
- **Settings Dialog**:
  - Restored missing Save/Cancel buttons in the footer.
  - Fixed title bar styling to match the main window.
- **General**:
  - Fixed application icon not updating on the executable (resource embedding).
  - Improved layout consistency across all dialogs.

## [0.1.0] - Pre-Release
- Initial prototype (Python/Tkinter version - Deprecated).
