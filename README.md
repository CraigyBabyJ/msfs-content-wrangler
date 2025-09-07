# msfs-content-wrangler
Content file editor for MFS2024
MSFS Content Wrangler

A fast, friendly desktop tool to review and toggle enable/disable Microsoft Flight Simulator content entries in Content.xml — with smart thumbnail discovery and safe backups. Built for MSFS 2024.


✨ What it does

Loads Content.xml and shows your installed entries in a clean table with:

Name, Status, Category, Vendor, Sim (FS24/FS20), and an optional Thumbnail.
Tabs for Official (FS2024), Community (FS2024), and Official (FS2020).
Filter & find fast: Search by name/vendor (regex supported), filter by Category & Status, and sort any column.

Toggle status with a click:
Activated ↔ UserDisabled via the Status column or Activate/Disable Selected buttons.
SystemDisabled entries are read-only and visually muted.
Shift-click and Ctrl/Cmd-click for multi-select (SystemDisabled rows won’t be included).

Safe save with automatic backup:
Creates a timestamped backup of Content.xml before writing.
Optionally removes legacy FS2020 Community entries on save (configurable).

Thumbnails without copying files:
Discovers thumbnail images in place (no duplication) and caches the paths in cache/thumbnails.json.
Discovery order: layout.json → ContentInfo/thumbnail* → ContentInfo/screenshot* → any image under ContentInfo/ → (for aircraft) SimObjects/Airplanes/**/thumbnail*.
Refresh per row (click the thumbnail cell or right-click “Refresh thumbnail(s)”) or Clear cache in Settings.
Shows a polished “Not Found” tile if scanned and no image exists.

Quality of life:
Stable column widths (no jitter), clean row-selection visuals, and non-blocking background work.

🧩 How it works (overview)
Content discovery

On first launch, the app searches typical MSFS LocalCache locations and profiles for Content.xml. You can switch files any time (File → Open… or Switch Content.xml…).

The table is a model/view backed by PackageRow objects, one per entry in Content.xml.

Tabs are enforced by a filter layer:
Official FS2024 Store → entries marked as official for FS24
Community Folder FS2024 → FS24 community
Official FS2020 Store  → official FS20 content that are enabled if compatable


Thumbnails (map-only cache)
The app never copies or resizes images; it stores paths in cache/thumbnails.json:
Keyed by package name; values include the resolved image path and mtime for quick validation.
When the thumbnail column is visible, discovery runs asynchronously (thread-pool) to keep the UI responsive.

You can:

Click the thumb cell to re-scan that one row.
Right-click → Refresh thumbnail(s) to re-scan all selected rows.
Settings → Clear thumbnail cache to wipe the DB and refresh organically as you scroll.
Status toggling
Click the Status column (green/red tick) to toggle Activated ↔ UserDisabled.
Use Activate Selected / Disable Selected for batch operations.
SystemDisabled entries are always greyed and excluded from bulk changes.

Save & backup
Before writing, the app creates a timestamped backup of the current Content.xml next to the file.
If Clean legacy FS20 mods is enabled (recommended), FS2020 Community references are removed during save.


🧭 Usage

Start the app – it will try to auto-detect Content.xml; otherwise use Open… or Switch Content.xml….
Pick a tab (Official FS2024, Community FS2024, Official FS2020).
Filter/search (Category/Status dropdowns, search box for name or vendor).
Toggle status by clicking the Status column or using the bulk buttons.
(Optional) Show thumbnails – enable in Settings → Appearance.
Click a thumbnail cell to force a refresh.
Right-click the table → Refresh thumbnail(s) to batch refresh.
Settings → Clear thumbnail cache to rebuild from scratch.
Save – creates a backup automatically; optionally cleans FS2020 community refs.

🧪 Power user notes

Regex search covers name and vendor fields.
Selection behavior: Shift-click to select ranges; Ctrl/Cmd-click to add/remove; SystemDisabled rows won’t remain selected in mixed groups.
Performance: thumbnail discovery is threaded and throttled; the cache prevents re-scanning on each launch.

Safety: only Content.xml is modified; no package folders are touched. Backups are always created.
Right-click menu: quick access to Refresh thumbnail(s) on selected rows.

🐞 Troubleshooting

No thumbnails appear
Ensure Settings → Appearance → Show thumbnails is enabled.
Use Clear thumbnail cache and scroll — rows will be re-scanned.
Check that packages contain a ContentInfo/thumbnail*.{png|jpg|jpeg|webp} or layout.json references.
“Permission denied” when saving thumbnail cache
Antivirus or another process may lock cache/thumbnails.json. Add an exclusion for the app folder.
Content.xml not found
Open manually (File → Open…) and select the correct profile’s Content.xml.
FS2020 Community items are missing
That’s by design. This tool hides FS2020 Community entries to avoid cross-sim confusion.
If Clean legacy FS20 mods is enabled, those refs are removed on save.


🤝 Contributing

PRs and issues are welcome! If you’re filing a bug, please include:
Whether MSFS 2024/2020 are installed and from which store (MS Store/Steam)
Content.xml location 
Steps to reproduce

📄 License

MIT. See LICENSE

🙏 Credits

Built with ❤️ by @CraigyBabyJ and contributors.
If you need this tweaked (tone, badges, logo, screenshots), tell me the vibe and I’ll tailor it.

Not affiliated with Microsoft, Asobo Studio, or any add-on vendor. All product names, logos, and brands are property of their respective owners.
