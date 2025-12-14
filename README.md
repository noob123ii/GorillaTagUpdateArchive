# Gorilla Tag Update Archive

## Features

- 📅 Organized by year (2021-2025)
- 📥 Automatic download handling
- 🔗 Direct links for Google Drive and Discord CDN downloads
- 🎮 SteamCMD script generation for Steam depot downloads

## Installation

### Quick Install (Windows)
Double-click `install.bat` to automatically install all dependencies.

### Manual Install
1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

**Troubleshooting cryptography installation:**
If you encounter issues installing `cryptography`:
1. Upgrade pip and build tools:
   ```bash
   pip install --upgrade pip setuptools wheel
   ```
2. Install cryptography separately:
   ```bash
   pip install cryptography
   ```
3. If still failing, try installing from a pre-built wheel:
   ```bash
   pip install --only-binary :all: cryptography
   ```
4. On some systems, you may need Visual C++ Build Tools (usually not required for pre-built wheels)

## Usage

1. Run the server:
```bash
python app.py
```

2. The website will automatically open in your browser at `http://127.0.0.1:5000`

## Download Types

### Google Drive Links
- Clicking will open the Google Drive link in a new tab
- You can download directly from Google Drive

### Direct Links (Discord CDN)
- Clicking will open the direct download link in a new tab
- Downloads start immediately

### Steam Depot Downloads
- Clicking will download a `.bat` script file
- You need SteamCMD installed to use these scripts
- Download SteamCMD from: https://developer.valvesoftware.com/wiki/SteamCMD
- Place `steamcmd.exe` in the same folder as the downloaded script, or add it to your PATH
- Run the `.bat` file to download the update
- Downloads will be in: `steamapps/content/app_1533390/depot_1533391/`

## Notes

- The server runs on port 5000 by default
- Press `Ctrl+C` to stop the server
- All updates are organized chronologically by year

