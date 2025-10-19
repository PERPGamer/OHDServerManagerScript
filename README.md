                       OHD Server Manager
                       =========================

OHD Server Manager is a headless, cross-platform utility for managing your OHD (Harsh Doorstop) server. 
It provides functionality for managing server updates, mod synchronization, crash recovery, and more.

---

### Features:
---------
- **Headless**: Works without a graphical interface, ideal for remote server management.
- **Cross-Platform**: Compatible with Windows and Linux.
- **Inline Configuration**: Configurable via a `config.py` file.
- **Automated Mod & Server Build Checks**: Periodic checks for mods and server build updates with auto-restarts.
- **Discord Webhook Integration**: Send server status updates to Discord.
- **Service Installation**: Install as a service on Linux (systemd) or Windows.

---

### Prerequisites:
--------------
- **Python 3.8** or higher
- **SteamCMD** installed and accessible

### Required Libraries:
-------------------
- **requests**: For Steam API calls
- **psutil**: For server process management

---

### Installation:
-------------
1. Download the files.
2. Install **SteamCMD** and configure it in `config.py`.
3. Ensure Python is installed, along with any required libraries (`requests`, `psutil`). You can use the `prerequisites_installer.bat` script for ease of installation.
4. Set up your server directory and mod list in `config.py`.
5. Run the script using the available command-line arguments.

*Note*: If you are using any mods, run `start.bat` first. Once the mods are downloaded, run `RunFirst.bat` to allow the script to check for mod updates.

---

### Configuration:
--------------
Configuration values are specified in the `config.py` file. The key values are:

- **DEFAULT_INSTALL_DIR**: Path to your OHD server directory.
- **DEFAULT_APP_ID**: Steam app ID for the OHD server.
- **DEFAULT_STEAMCMD_DIR**: Path to your SteamCMD installation.
- **DEFAULT_MODLIST_FILENAME**: Name of the mod list file (`Modlist.txt`).
- **MOD_LIST**: A list of Steam Workshop mod IDs and folder names (if applicable).
- **RUNTIME**: Defines runtime options like update intervals, wait times, etc.

---

### Command-Line Arguments:
------------------------
You can configure the server manager behavior using the following arguments:
usage: ohd_server_manager_combined.py [-h] [--install-dir INSTALL_DIR]
[--app-id APP_ID]
[--steamcmd-dir STEAMCMD_DIR]
[--mod-list MOD_LIST] [--dry-run]
[--once] [--no-webhook]
[--webhook-url WEBHOOK_URL]
[--log-file LOG_FILE] [--debug]
[--create-localupdates [CREATE_LOCALUPDATES]]
[--update-checker-dir UPDATE_CHECKER_DIR]
[--mod-update-checker-dir MOD_UPDATE_CHECKER_DIR]
[--install-systemd] [--remove-systemd]
[--install-windows-service]
[--remove-windows-service] [--service-name SERVICE_NAME]

---

### Arguments Explanation:
------------------------
- **`--install-dir`**: Path to the directory where your OHD server is installed.
- **`--app-id`**: The Steam App ID for your OHD server (default is set in `config.py`).
- **`--steamcmd-dir`**: Directory for SteamCMD installation.
- **`--mod-list`**: Path to a mod list file (optional if using `config.MOD_LIST`).
- **`--dry-run`**: Run in dry-run mode, which will not make any actual changes but will simulate the actions.
- **`--once`**: Run the server manager for one iteration then exit.
- **`--no-webhook`**: Disable Discord webhook posting.
- **`--webhook-url`**: Provide an override for the Discord webhook URL.
- **`--log-file`**: Specify a custom log file path.
- **`--debug`**: Enable debug logging.
- **`--create-localupdates`**: Create or update the `localupdates.json` file for mods (you can specify a custom path or leave it blank to auto-detect).
- **`--update-checker-dir`**: Directory for the base update checker scripts.
- **`--mod-update-checker-dir`**: Directory for mod update checker scripts.

---

### Example Usage:
------------------------
1. **Run server manager once**:
   python ohd_server_manager_combined.py --once
2. **Update mods**:
   python ohd_server_manager_combined.py --create-localupdates /path/to/steam/workshop
3. Run in dry-run mode (simulates the actions):
   python ohd_server_manager_combined.py --dry-run

