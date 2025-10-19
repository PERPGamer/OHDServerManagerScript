r"""config.py

Static and runtime configuration for the OHD Server Manager.

Edit the values below as needed. This file is imported by ohd_server_manager.py.
"""
from pathlib import Path
import os

# -------------------------
# Static constants
# -------------------------
DEFAULT_INSTALL_DIR = Path(r"C:\OHDServers\OHDVanillaClassic")
DEFAULT_APP_ID = "950900"  # server app id
DEFAULT_STEAM_APPID_FOR_WORKSHOP = "736590"  # workshop folder id for OHD mods
DEFAULT_STEAMCMD_DIR = Path(r"C:\steamcmd")  # default steamcmd location
DEFAULT_GAME_BIN_REL = Path("HarshDoorstop/Binaries/Win64")
DEFAULT_SERVER_EXE = "HarshDoorstopServer-Win64-Shipping.exe"
DEFAULT_MODLIST_FILENAME = "Modlist.txt" # Not needed, just a backup
DEFAULT_LOG_FILENAME = "ohd_server_manager.log"
DEFAULT_STEAM_USER = "anonymous"
DEFAULT_STEAMCMD_DEL = 5  # seconds delay before syncing mods
DEFAULT_MAP_CYCLE = "MapCycle.cfg"
DEFAULT_PORT_NUM = 7777
DEFAULT_QUERYPORT= 27005
DEFAULT_RCONPORT= 7779
DEFAULT_STEAM_TITLE = "Harsh Doorstop Dedicated Server"
DEFAULT_DISCORD_TITLE = ""
DEFAULT_OHD_MAP = "AAS-TestMap"
DEFAULT_OHD_GAMEMODE = ""
DEFAULT_OHD_PARAM = "?MaxPlayers=16"
WEBHOOK_URL_DEFAULT = ""

# -------------------------
# Inline MOD_LIST
# - Put workshop item IDs (strings) here in desired loading order.
# - You may also use tuples like ("123456789", "FolderNameToUse")
# - If empty, the script falls back to reading <install_dir>/Modlist.txt (if present).
# -------------------------
MOD_LIST = [
    # "3581493334",
    # "3128391023",
]

# -------------------------
# Runtime options
# - update_interval: seconds between automatic periodic checks (mods + server)
# - init_wait_time: seconds to wait after launching server for initialization
# - restart_delay: seconds to wait after crash before restarting
# - enable_auto_update_checks: set False to disable periodic checks (still checks after crash)
# -------------------------
RUNTIME = {
    "update_interval": 600,      # default: 600s (10 minutes)
    "init_wait_time": 30,        # default: 30s after starting server
    "restart_delay": 30,         # default: 30s after crash before restart
    "enable_auto_update_checks": True,
    "dry_run": False,
    "once": False,
    "debug": True,
    "log_file": None,
}

# Environment overrides (optional)
if "OHD_INSTALL_DIR" in os.environ:
    DEFAULT_INSTALL_DIR = Path(os.environ["OHD_INSTALL_DIR"])
if "OHD_APP_ID" in os.environ:
    DEFAULT_APP_ID = os.environ["OHD_APP_ID"]
if "OHD_DISCORD_WEBHOOK" in os.environ:
    WEBHOOK_URL_DEFAULT = os.environ["OHD_DISCORD_WEBHOOK"]
