# CONTINUE.md

---

## 1. Project Overview

**Purpose:**
This project appears to be a Python-based toolset for managing and displaying categorized content, possibly for a UI dashboard or file sorting app. While project specifics need verification, it processes XML data (e.g., `content.xml`), organizes images or resources, and generates/uses thumbnails and configuration settings.

**Key Technologies:**
- Python 3
- Likely uses PyQt or a similar GUI framework (needs verification)
- Custom categorization and file management logic

**High-Level Architecture:**
- Core logic: .py files (main, models, categorizer, content I/O)
- Data/config: .json, .xml
- Static resources: icons, thumbnails, themes, QSS

---

## 2. Getting Started

**Prerequisites:**
- Python 3.11+
- Recommended: virtualenv
- Dependencies in `requirements.txt`

**Installation:**
```sh
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

**Basic Usage:**
- Run main application:
```sh
python main.py
```
  
**Running Tests:**
- No dedicated test suite detected (add or update as needed)

---

## 3. Project Structure

- **main.py**: Entry point; likely initializes GUI/app.
- **models.py**: Data models (entities, types, categories).
- **categorizer.py**: Logic for sorting/categorizing content.
- **content_io.py**: Handles reading/writing/parsing of content files (possibly XML/JSON).
- **footer.py**: Possible UI or metadata/footer logic.
- **settings.py**: Config, user prefs, or UI settings logic.
- **rules.json/config.json**: App configuration or rules for categorization/presentation.
- **resources.qss/light_theme.qss**: Qt stylesheet (theme/UI appearance files).
- **icons/**: Static icons for UI use.
- **cache/**: Thumbnails and/or cached content for fast access.

*Important configuration*: `config.json`, `rules.json`, `requirements.txt`

---

## 4. Development Workflow

- **Coding Standards**: Use Python 3, PEP8 preferred unless otherwise configured.
- **Testing**: (No automated tests detected—consider introducing pytest or unittest.)
- **Build/Deployment**: Use `build_exe.bat` for executable packaging (likely PyInstaller or similar).
- **Contribution**: No guidelines—add `CONTRIBUTING.md` for detailed instructions. Use clear PRs, code reviews.

---

## 5. Key Concepts

- **Categories/Tabs**: Data is sorted (via `categorizer.py`, logic may involve rules in `rules.json` and settings in `config.json`).
- **Thumbnails**: Images in `cache/thumbs` correspond to content entries.
- **Themes/QSS**: Qt stylesheets for controlling interface look/feel.
- **Content Parsing**: XML/JSON used to structure/load content; logic likely in `content_io.py`.

*Needs verification*: GUI library (assumed Qt or PyQt), confirmation of `content.xml` logic.

---

## 6. Common Tasks

- **Add content**: Place new data/resources and update `content.xml`.
- **Re-categorize content**: Edit `rules.json` and re-run the app.
- **Update settings**: Edit `config.json` or via UI if supported.
- **Build EXE**: Run `build_exe.bat`.
- **Theme editing**: Modify `.qss` files.

---

## 7. Troubleshooting

- **Content not sorted into correct tabs**: Check `categorizer.py` logic and `content_io.py` parsing. Validate `rules.json` or `config.json`. Debug XML parsing and ensure XML structure matches what parsers expect. Content sorting not working is often an easy fix in the categorizer or config/rules files—see logic in those modules.
- **Missing thumbnails**: Ensure new images are placed in `cache/thumbs` and are correctly named.
- **UI/theme broken**: Check changes to QSS or icons.
- **Build issues**: Make sure dependencies in `requirements.txt` match your Python version.

---

## 8. References

- [Python documentation](https://docs.python.org/3/)
- (Add links to external APIs, frameworks, or team docs as needed)

---

*Note: Sections marked "needs verification" should be reviewed and updated with more project knowledge.*
