# Fang

Automatically organize music files by metadata into an `Artist/Album/Track` folder structure. Files with missing or incomplete metadata are sorted into a separate "Unorganized" folder.

Available as a **desktop app** (Mac/Windows), **Python CLI**, or **Docker**.

## Features

- 🎵 Supports: MP3, FLAC, M4A, AAC, WMA, OGG, Opus
- 📂 Organizes by artist → album → track name
- 🔍 Preview mode (dry-run) before applying changes
- ⚠️ Separates files with bad/missing metadata
- 🛡️ Won't overwrite existing files
- 🖥️ Beautiful desktop GUI for Mac & Windows
- 🐳 Docker support
- 💜 Lavender purple Minecraft music disk theme

## Quick Start - Desktop App

### Mac
1. Download `Fang.app` from [Releases](https://github.com/Antares-AlphaScorpii/Fang/releases)
2. Drag to Applications folder
3. Double-click to run

### Windows
1. Download `Fang.exe` from [Releases](https://github.com/Antares-AlphaScorpii/Fang/releases)
2. Double-click to run

## Desktop App Usage

1. **Select Source Folder** — Where your music files are
2. **Select Output Folder** — Where organized music will go
3. **Preview (Dry Run)** — See what would happen without moving files
4. **Organize** — Actually move your files

## Installation from Source

### Option 1: Desktop App (Build from source)

```bash
git clone https://github.com/Antares-AlphaScorpii/Fang.git
cd Fang
pip install -r requirements.txt
python music_organizer_gui.py
```

To package as a standalone app:

```bash
python build.py
# Check the 'dist' folder for Fang.app or Fang.exe
```

### Option 2: Python CLI

```bash
git clone https://github.com/Antares-AlphaScorpii/Fang.git
cd Fang
pip install -r requirements.txt
```

#### Dry Run
```bash
python music_organizer.py ~/Music ~/Music_Organized
```

#### Apply Changes
```bash
python music_organizer.py ~/Music ~/Music_Organized --apply
```

#### Custom Problematic Folder
```bash
python music_organizer.py ~/Music ~/Music_Organized --apply --problematic-folder "No_Metadata"
```

### Option 3: Docker

```bash
docker build -t fang .

# Dry run
docker run --rm \
  -v ~/Music:/music_source:ro \
  -v ~/Music_Organized:/music_output \
  fang /music_source /music_output

# Apply changes
docker run --rm \
  -v ~/Music:/music_source:ro \
  -v ~/Music_Organized:/music_output \
  fang /music_source /music_output --apply
```

## How It Works

1. Scans for all audio files (mp3, flac, m4a, aac, wma, ogg, opus)
2. Reads metadata: artist, album, track title
3. Creates folders: `Artist/Album/Track Name.ext`
4. Files with missing metadata → separate "Unorganized" folder
5. Preview mode shows everything before moving
6. Apply mode actually moves the files

## Example

**Before:**

## Command Line Options (CLI)

- `--apply` — Actually move files (default: dry-run)
- `--problematic-folder` — Custom name for files with bad metadata (default: "Unorganized")

## Building Standalone Apps

### Mac

```bash
python build.py
# Creates Fang.app in the dist/ folder
open dist/Fang.app
```

### Windows

```bash
python build.py
# Creates Fang.exe in the dist/ folder
dist\Fang.exe
```

## License

MIT

## Contributing

Contributions are welcome! Feel free to open issues and pull requests.
