#!/usr/bin/env python3
# ohd_server_manager_ubuntu.py
# Ubuntu-compatible OHD Server Manager with auto SteamCMD download
# Drop this next to your config or edit defaults below.

from __future__ import annotations
import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import tarfile
import urllib.request
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional, Tuple
import datetime

# Optional third-party
try:
    import requests
except Exception:
    requests = None

try:
    import psutil
except Exception:
    psutil = None

# -------------------------
# Default config (Ubuntu-friendly)
# Edit these or create a local config.py to override by importing it
# -------------------------
HOME = Path.home()
DEFAULT_INSTALL_DIR = HOME / "OHDServers" / "OHDVanillaClassic"
DEFAULT_APP_ID = "950900"
DEFAULT_STEAM_APPID_FOR_WORKSHOP = "736590"
DEFAULT_STEAMCMD_DIR = HOME / ".steamcmd"           # will auto-download here if missing
DEFAULT_GAME_BIN_REL = Path("HarshDoorstop/Binaries/Linux")
DEFAULT_SERVER_EXE = "HarshDoorstopServer-Linux-Shipping"  # change if different on your build
DEFAULT_MODLIST_FILENAME = "Modlist.txt"
DEFAULT_LOG_FILENAME = "ohd_server_manager.log"
DEFAULT_STEAM_USER = "anonymous"
DEFAULT_STEAMCMD_DEL = 5
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

# Inline MOD_LIST (put workshop item IDs here)
MOD_LIST = [
    # "3581493334",
]

# Runtime tuning
RUNTIME = {
    "update_interval": 600,
    "init_wait_time": 30,
    "restart_delay": 30,
    "auto_delete_mods_after_moved": True,
    "enable_auto_update_checks": True,
    "dry_run": False,
    "once": False,
    "debug": False,
    "log_file": None,
}

# Allow a local config.py to override defaults if present
try:
    import config as user_config  # type: ignore
    # override if attributes exist
    for k, v in vars(user_config).items():
        if k.isupper():
            globals()[k] = v
except Exception:
    pass

# Globals (set later)
DRY_RUN = False
WEBHOOK_URL = ""
STEAMCMD_LOCATION = DEFAULT_STEAMCMD_DIR
APP_ID = DEFAULT_APP_ID
MOD_LIST_FILE = None
MOD_UPDATE_CHECKER_DIR = None
UPDATE_CHECKER_DIR = None
STEAM_USER = DEFAULT_STEAM_USER
STEAMCMD_DEL = DEFAULT_STEAMCMD_DEL

# -------------------------
# Utilities
# -------------------------
def prettyPrintModInfo(mod_id, mod_name, latest_update, needs_updated=True):
    idlength = len(str(mod_id))
    namelength = len(str(mod_name))
    lastupdatetime = len(str(latest_update))
    needsupdatelength = len(str(needs_updated))
    maxlength = max(idlength, namelength, lastupdatetime, needsupdatelength)
    box = "╔" + "═" * (maxlength + 13) + "╗\n"
    box += f"║Title:       {mod_name}{' ' * (maxlength - namelength)}║\n"
    box += "╠" + "═" * (maxlength + 13) + "╣\n"
    box += f"║ID:          {mod_id}{' ' * (maxlength - idlength)}║\n"
    box += "╠" + "═" * (maxlength + 13) + "╣\n"
    box += f"║Last Update: {latest_update}{' ' * (maxlength - lastupdatetime)}║\n"
    box += "╠" + "═" * (maxlength + 13) + "╣\n"
    box += f"║Needs Update:{needs_updated}{' ' * (maxlength - needsupdatelength)}║\n"
    box += "╚" + "═" * (maxlength + 13) + "╝"
    print(box)

# -------------------------
# SteamCMD auto-download
# -------------------------
STEAMCMD_TAR_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz"
def ensure_steamcmd(steamcmd_dir: Path) -> Path:
    """
    Ensure SteamCMD exists in steamcmd_dir. If not, attempt to download and extract it.
    Returns path to steamcmd executable (steamcmd.sh).
    """
    steamcmd_dir = Path(steamcmd_dir).expanduser().resolve()
    steamcmd_sh = steamcmd_dir / "steamcmd.sh"
    # If present and executable, return
    if steamcmd_sh.exists():
        try:
            steamcmd_sh.chmod(steamcmd_sh.stat().st_mode | 0o111)
        except Exception:
            pass
        return steamcmd_sh

    # Try to create and download
    try:
        steamcmd_dir.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] SteamCMD not found at {steamcmd_dir}. Downloading SteamCMD...")
        archive = steamcmd_dir / "steamcmd_linux.tar.gz"
        # Attempt curl or wget via subprocess first for progress; fallback to urllib
        got = False
        try:
            # prefer curl
            subprocess.run(["curl", "-L", "-o", str(archive), STEAMCMD_TAR_URL], check=True)
            got = True
        except Exception:
            try:
                subprocess.run(["wget", "-O", str(archive), STEAMCMD_TAR_URL], check=True)
                got = True
            except Exception:
                got = False
        if not got:
            # fallback to urllib
            print("[INFO] Falling back to urllib to download steamcmd tarball...")
            with urllib.request.urlopen(STEAMCMD_TAR_URL, timeout=30) as r:
                data = r.read()
                archive.write_bytes(data)
        # extract
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(path=str(steamcmd_dir))
        archive.unlink(missing_ok=True)
        # Make the shell wrapper executable
        if (steamcmd_dir / "steamcmd.sh").exists():
            (steamcmd_dir / "steamcmd.sh").chmod(0o755)
            print(f"[INFO] SteamCMD downloaded and extracted to {steamcmd_dir}")
            return steamcmd_dir / "steamcmd.sh"
        else:
            raise RuntimeError("steamcmd.sh not found after extraction.")
    except Exception as e:
        raise RuntimeError(f"Failed to ensure SteamCMD: {e}")

# -------------------------
# Steam API Manager (same as original)
# -------------------------
class SteamAPIManager:
    __instance = None

    @staticmethod
    def getInstance():
        if SteamAPIManager.__instance is None:
            SteamAPIManager()
        return SteamAPIManager.__instance

    @staticmethod
    def getWorkshopMod(itemID: str) -> dict:
        url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1"
        data = {"itemcount": 1, "publishedfileids[0]": itemID}
        if requests is None:
            raise RuntimeError("requests library is required for Steam API calls.")
        r = requests.post(url, data=data, timeout=15)
        r.raise_for_status()
        return r.json()

    def __init__(self):
        if SteamAPIManager.__instance is not None:
            raise Exception("This class is a singleton")
        SteamAPIManager.__instance = self

# -------------------------
# FileManager (headless)
# -------------------------
class FileManager:
    __instance = None

    @staticmethod
    def getInstance():
        if FileManager.__instance is None:
            FileManager()
        return FileManager.__instance

    @staticmethod
    def readJsonFile() -> dict:
        try:
            with open("localupdates.json", "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            raise FileNotFoundError("localupdates.json not found. Use --create-localupdates to create it.")

    @staticmethod
    def _build_localupdates_from_path(root: Path) -> dict:
        root = Path(root).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Workshop path not found: {root}")
        try:
            entries = [e for e in os.listdir(root) if os.path.isdir(os.path.join(root, e))]
        except Exception as e:
            entries = []
            print(f"[WARNING] Could not list {root}: {e}")
        modlist = []
        for folder in entries:
            try:
                dt = FileManager.getUpdate(folder)
            except Exception as e:
                print(f"[WARNING] Error when getting update for {folder}: {e}")
                dt = "NA"
            modlist.append({"id": folder, "dt": dt})
        base = {"dirpath": str(root), "mods": modlist}
        try:
            with open("localupdates.json", "w", encoding="utf-8") as out:
                json.dump(base, out, indent=2)
            print(f"[INFO] localupdates.json written successfully ({len(modlist)} mods).")
        except Exception as e:
            print(f"[ERROR] Failed to write localupdates.json: {e}")
        return base

    @staticmethod
    def updateJsonFile(direct: str) -> dict:
        try:
            base = FileManager._build_localupdates_from_path(Path(direct))
            if not base:
                raise ValueError("No mods found to update.")
            return base
        except Exception as e:
            log(f"Failed to update localupdates.json: {e}", logging.ERROR)
            raise

    @staticmethod
    def getUpdate(itemid: str) -> str:
        try:
            if requests is None:
                print(f"[WARNING] requests not installed; unable to query Steam for mod {itemid}")
                return "NA"
            api = SteamAPIManager.getInstance()
            resp = api.getWorkshopMod(itemid)
            if not isinstance(resp, dict):
                print(f"[WARNING] Unexpected Steam API response for {itemid}: {resp!r}")
                return "NA"
            details = resp.get("response", {}).get("publishedfiledetails", [])
            if not details:
                print(f"[INFO] No publishedfiledetails for mod {itemid}")
                return "NA"
            lastupdate = details[0].get("time_updated")
            if not lastupdate:
                return "NA"
            dt = datetime.datetime.fromtimestamp(int(lastupdate))
            print(f"[DEBUG] Mod {itemid} last updated {dt}")
            return str(dt)
        except Exception as e:
            print(f"[WARNING] Exception while fetching mod {itemid}: {e}")
            traceback.print_exc(limit=2)
            return "NA"

    def __init__(self):
        if FileManager.__instance is not None:
            raise Exception("This class is a singleton")
        FileManager.__instance = self

# -------------------------
# OHD Update Checker
# -------------------------
class OHDUpdateChecker:
    def __init__(self):
        SteamAPIManager.getInstance()
        FileManager.getInstance()

    @staticmethod
    def checkForUpdate(itemid: str, localupdate: str) -> bool:
        try:
            if requests is None:
                return False
            resp = SteamAPIManager.getInstance().getWorkshopMod(itemid)
            details = resp.get("response", {}).get("publishedfiledetails", [])
            if not details:
                return False
            lastupdate = details[0].get("time_updated")
            if not lastupdate:
                return False
            dt = datetime.datetime.fromtimestamp(int(lastupdate))
            return str(dt) != localupdate
        except Exception:
            return False

    @staticmethod
    def checkUpdates() -> bool:
        try:
            moddata = FileManager.readJsonFile()
        except FileNotFoundError:
            return False
        found = False
        for item in moddata.get("mods", []):
            if OHDUpdateChecker.checkForUpdate(item["id"], item["dt"]):
                found = True
        return found

    @staticmethod
    def UpdateMods():
        try:
            derc = FileManager.readJsonFile()
        except FileNotFoundError:
            raise
        FileManager.updateJsonFile(derc["dirpath"])

# -------------------------
# Steam update checker (steamcmd)
# -------------------------
def call_steam_update_checker(app_id: str, install_dir: Path) -> int:
    """
    Uses SteamCMD to check whether the server build is up-to-date by comparing buildid.
    Returns:
      0 = up to date
      1 = update found and applied
      2 = error
    """
    log(f"Checking Steam app {app_id} for updates via SteamCMD...", logging.INFO)
    appinfo_path = install_dir / f"appinfo_{app_id}.json"
    steamcmd_sh = ensure_steamcmd(STEAMCMD_LOCATION)

    cmd = [str(steamcmd_sh),
           "+login", "anonymous",
           "+app_info_update", "1",
           "+app_info_print", str(app_id),
           "+quit"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout

        # Extract remote buildid from SteamCMD output
        match = re.search(r'"buildid"\s+"(\d+)"', output)
        if not match:
            log("Could not find buildid in SteamCMD output.", logging.WARNING)
            log(output[:500], logging.DEBUG)
            return 2

        remote_buildid = match.group(1)
        log(f"Remote Steam buildid: {remote_buildid}", logging.DEBUG)

        # Load stored buildid if available
        local_buildid = None
        if appinfo_path.exists():
            try:
                with open(appinfo_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    local_buildid = str(data.get("build_id"))
            except Exception as e:
                log(f"Failed to read local buildid: {e}", logging.WARNING)

        # Compare
        if local_buildid == remote_buildid:
            log("Server buildid matches local buildid — no update needed.", logging.INFO)
            return 0

        # New build detected — save new appinfo
        appinfo_data = {
            "app_id": app_id,
            "build_id": remote_buildid,
            "checked": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        with open(appinfo_path, "w", encoding="utf-8") as f:
            json.dump(appinfo_data, f, indent=2)
        log(f"Updated {appinfo_path} with new buildid {remote_buildid}", logging.INFO)

        # Perform actual update
        update_cmd = [
            str(steamcmd_sh),
            "+login", "anonymous",
            "+force_install_dir", str(install_dir),
            "+app_update", str(app_id), "validate",
            "+quit"
        ]
        update_result = subprocess.run(update_cmd, capture_output=True, text=True)

        stdout = update_result.stdout or ""
        if "Success! App" in stdout or "fully installed" in stdout:
            log(f"Server files updated to buildid {remote_buildid}.", logging.INFO)
            return 1
        else:
            log("SteamCMD did not report success — assuming up-to-date.", logging.WARNING)
            return 0

    except subprocess.CalledProcessError as e:
        log(f"SteamCMD failed: {e}", logging.ERROR)
        return 2
    except Exception as e:
        log(f"Unexpected error during SteamCMD check: {e}", logging.ERROR)
        return 2

# -------------------------
# Logging helpers
# -------------------------
def normalize_level(level_param):
    if isinstance(level_param, int):
        return level_param
    if isinstance(level_param, str):
        lv = logging.getLevelName(level_param.upper())
        return lv if isinstance(lv, int) else logging.INFO
    return logging.INFO

def log(msg: str, level=logging.INFO):
    logging.log(normalize_level(level), msg)

def setup_logging(log_file: Path, debug: bool = False):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    if logger.handlers:
        logger.handlers.clear()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    fh = RotatingFileHandler(str(log_file), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if debug else logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    logging.debug(f"Logging initialized; file: {log_file}")

# -------------------------
# Webhook (unchanged)
# -------------------------
def post_discord_embed(title: str, description: str, color: int):
    global WEBHOOK_URL
    if not WEBHOOK_URL:
        logging.getLogger().debug("Webhook not configured; skipping Discord post.")
        return
    payload = {"content": None, "embeds": [{"title": title, "description": description, "color": color}]}
    if DRY_RUN:
        log(f"[dry-run] Webhook payload: {title} - {description}", logging.DEBUG)
        return
    try:
        import requests as _requests
        r = _requests.post(WEBHOOK_URL, json=payload, timeout=10)
        r.raise_for_status()
        log("Discord webhook posted.", logging.INFO)
    except Exception as e:
        log(f"Failed to post Discord webhook: {e}", logging.WARNING)
        try:
            subprocess.run(["curl", "-X", "POST", "-H", "Content-Type: application/json", "--data", json.dumps(payload), WEBHOOK_URL], check=True)
            log("Discord webhook posted via curl fallback.", logging.INFO)
        except Exception:
            log("Failed to post webhook via curl fallback.", logging.WARNING)

# -------------------------
# Steamcmd helpers & update wrappers
# -------------------------
def run_steamcmd(args: List[str], cwd: Path = None) -> subprocess.CompletedProcess:
    global DRY_RUN, STEAMCMD_LOCATION
    if DRY_RUN:
        log(f"[dry-run] steamcmd args: {' '.join(args)}", logging.DEBUG)
        return subprocess.CompletedProcess(args=args, returncode=0)
    steamcmd_sh = ensure_steamcmd(STEAMCMD_LOCATION)
    cmd = [str(steamcmd_sh)] + args
    try:
        res = subprocess.run(cmd, cwd=str(STEAMCMD_LOCATION))
        return res
    except Exception as e:
        log(f"Error running steamcmd: {e}", logging.ERROR)
        return subprocess.CompletedProcess(args=cmd, returncode=1)

def call_python_update_checker_for_mods() -> bool:
    global DRY_RUN
    if DRY_RUN:
        log("[dry-run] Skipping mod update checker", logging.DEBUG)
        return False
    if not getattr(sys.modules.get('config', None), "MOD_LIST", None) and not MOD_LIST:
        try:
            _ = FileManager.readJsonFile()
        except FileNotFoundError:
            log("No MOD_LIST and no localupdates.json -> skipping mod update checks.", logging.DEBUG)
            return False
    try:
        checker = OHDUpdateChecker()
        return checker.checkUpdates()
    except Exception as e:
        log(f"Mod update checker failed: {e}", logging.WARNING)
        return False

def call_updatemods_python():
    global DRY_RUN
    if DRY_RUN:
        log("[dry-run] Skipping UpdateMods", logging.DEBUG)
        return
    try:
        OHDUpdateChecker.UpdateMods()
    except FileNotFoundError:
        create_or_update_localupdates()
        log("localupdates.json not found; cannot update mods list automatically.", logging.WARNING)
    except Exception as e:
        log(f"UpdateMods failed: {e}", logging.WARNING)

# -------------------------
# Mod list & sync (keeps config.MOD_LIST support)
# -------------------------
def read_mod_list(mod_list_path: Path) -> List[Tuple[str, str]]:
    mods: List[Tuple[str, str]] = []
    # First check for user config module
    conf_mod_list = None
    try:
        import config as cfg  # type: ignore
        conf_mod_list = getattr(cfg, "MOD_LIST", None)
    except Exception:
        conf_mod_list = MOD_LIST

    if conf_mod_list:
        for entry in conf_mod_list:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                mods.append((str(entry[0]), str(entry[1])))
            else:
                mods.append((str(entry), str(entry)))
        if mods:
            log(f"Loaded {len(mods)} mods from config.MOD_LIST", logging.DEBUG)
        else:
            log("MOD_LIST in config is empty — running server without mods.", logging.INFO)
        return mods

    log("No MOD_LIST found — skipping mods entirely.", logging.WARNING)
    return mods

def delete_folders_in_workshop(directory_path: Path):
    try:
        if not directory_path.exists():
            print(f"[ERROR] The specified directory does not exist: {directory_path}")
            return
        for item in directory_path.iterdir():
            if item.is_dir():
                print(f"[INFO] Deleting folder: {item}")
                shutil.rmtree(item)
                print(f"[INFO] Deleted {item}")
            else:
                print(f"[INFO] Skipping non-folder: {item}")
        print("[INFO] Completed deletion of workshop subfolders.")
    except Exception as e:
        print(f"[ERROR] Error deleting folders: {e}")

def sync_workshop_mods(mod_list_path: Path, install_dir: Path, workshop_dir: Path, app_workshop_id: str) -> Optional[str]:
    global DRY_RUN, STEAMCMD_DEL, STEAM_USER
    mods = read_mod_list(mod_list_path)
    if not mods:
        log("No mods configured; skipping workshop sync.", logging.INFO)
        return None
    for s in range(STEAMCMD_DEL, 0, -1):
        log(f"Waiting {s}s before syncing mods...", logging.DEBUG)
        time.sleep(1)
    steamcmd_sh = ensure_steamcmd(STEAMCMD_LOCATION)
    for wid, _ in mods:
        args = ["+force_install_dir", str(install_dir), "+login", STEAM_USER, "+workshop_download_item", app_workshop_id, wid, "+quit"]
        run_steamcmd(args, cwd=STEAMCMD_LOCATION)
    call_updatemods_python()
    server_mods_dir = install_dir / "HarshDoorstop" / "Mods"
    if not DRY_RUN:
        server_mods_dir.mkdir(parents=True, exist_ok=True)
    for wid, _ in mods:
        workshop_id_folder = workshop_dir / str(wid)
        if DRY_RUN:
            log(f"[dry-run] Would copy from {workshop_id_folder} to destination", logging.INFO)
            continue
        try:
            if workshop_id_folder.exists() and workshop_id_folder.is_dir():
                contents = [c for c in workshop_id_folder.iterdir() if c.is_dir() or c.is_file()]
                if not contents:
                    log(f"No contents in {workshop_id_folder}; skipping {wid}", logging.WARNING)
                    continue
                # choose first folder or file entry as mod root
                mod_root = contents[0]
                # If it's a directory, copy recursively to server_mods_dir/<mod_root.name>
                dst = server_mods_dir / mod_root.name
                # remove existing dst if auto_delete_mods_after_moved enabled (we'll replace)
                if dst.exists():
                    try:
                        if dst.is_dir():
                            shutil.rmtree(dst)
                        else:
                            dst.unlink()
                    except Exception:
                        pass
                if mod_root.is_dir():
                    shutil.copytree(mod_root, dst)
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(mod_root, dst)
                log(f"Successfully updated mod {mod_root.name} to {dst}")
            else:
                log(f"Workshop ID folder {workshop_id_folder} does not exist, skipping mod {wid}.", logging.WARNING)
        except Exception as e:
            log(f"Failed copying files for mod {wid}: {e}", logging.WARNING)

    mods_to_load_list = [folder for (_, folder) in mods]
    mods_to_load = ";".join(mods_to_load_list)
    if RUNTIME.get("auto_delete_mods_after_moved", True):
        try:
            delete_folders_in_workshop(workshop_dir)
        except Exception:
            pass
    log(f"Mods to load string: {mods_to_load}", logging.DEBUG)
    return mods_to_load

# -------------------------
# Server lifecycle (ServerProcess)
# -------------------------
class ServerProcess:
    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None

    def start(self, install_dir: Path, game_bin_rel: Path, server_exe: str, mods_to_load: Optional[str]) -> bool:
        global DRY_RUN, APP_ID, STEAMCMD_LOCATION
        log("Performing steamcmd app_update (may be skipped in dry-run)...", logging.INFO)
        if not DRY_RUN:
            run_steamcmd(["+login", STEAM_USER, "+force_install_dir", str(install_dir), "+app_update", APP_ID, "validate", "+quit"], cwd=STEAMCMD_LOCATION)
        else:
            log("[dry-run] Skipped steam app_update", logging.DEBUG)
        exe = install_dir / game_bin_rel / server_exe
        if not DRY_RUN and not exe.exists():
            log(f"Server executable not found: {exe}", logging.ERROR)
            return False

        args = [str(exe),
                f"{DEFAULT_OHD_MAP}?game={DEFAULT_OHD_GAMEMODE}{DEFAULT_OHD_PARAM}",
                "-log",
                f"-port={DEFAULT_PORT_NUM}",
                f"-QueryPort={DEFAULT_QUERYPORT}",
                f"-RCONPort={DEFAULT_RCONPORT}",
                f"-MapCycle={DEFAULT_MAP_CYCLE}",
                f"-SteamServerName={DEFAULT_STEAM_TITLE}"]
        log(f"Launching server: {' '.join(args)}", logging.DEBUG)
        if DRY_RUN:
            log("[dry-run] Would launch server", logging.INFO)
            self.proc = None
            self.pid = None
            return True
        try:
            # Ensure binary is executable
            try:
                exe.chmod(exe.stat().st_mode | 0o111)
            except Exception:
                pass
            self.proc = subprocess.Popen(args, cwd=str(install_dir / game_bin_rel))
            self.pid = self.proc.pid
            log(f"Server started with PID {self.pid}", logging.INFO)
        except Exception as e:
            log(f"Failed to start server process: {e}", logging.ERROR)
            return False
        return True

    def is_running(self) -> bool:
        if DRY_RUN:
            return False
        if self.proc:
            try:
                return self.proc.poll() is None
            except Exception:
                return False
        if self.pid and psutil:
            try:
                p = psutil.Process(self.pid)
                return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
            except Exception:
                return False
        return False

    def kill(self):
        if DRY_RUN:
            log("[dry-run] Would kill server", logging.DEBUG)
            self.proc = None
            self.pid = None
            return
        if not self.proc and not self.pid:
            return
        log(f"Killing server process (pid={self.pid})", logging.INFO)
        try:
            if self.proc:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=10)
                except Exception:
                    self.proc.kill()
            elif self.pid:
                if psutil:
                    try:
                        p = psutil.Process(self.pid)
                        p.terminate()
                        p.wait(timeout=10)
                    except Exception:
                        try:
                            p.kill()
                        except Exception:
                            pass
                else:
                    subprocess.run(["kill", "-TERM", str(self.pid)], check=False)
        except Exception as e:
            log(f"Error killing server process: {e}", logging.WARNING)
        finally:
            self.proc = None
            self.pid = None

# -------------------------
# Monitoring & main flow
# -------------------------
def check_server_on_launch(install_dir: Path) -> bool:
    rc = call_steam_update_checker(APP_ID, install_dir)
    if rc == 1:
        log("Server build update required on launch", logging.INFO)
        return False
    return True

def after_crash_checks_and_prepare(srv: ServerProcess, install_dir: Path, mod_list_path: Path, workshop_dir: Path, app_workshop_id: str) -> Tuple[bool, Optional[str]]:
    log("Running after-crash checks", logging.INFO)
    mods_need = call_python_update_checker_for_mods()
    if mods_need:
        post_discord_embed(DEFAULT_DISCORD_TITLE, "Restarting due to mod update (post-crash)", 10038562)
        log("Detected mod updates after crash; syncing", logging.INFO)
        m = sync_workshop_mods(mod_list_path, install_dir, workshop_dir, app_workshop_id)
        return True, m
    rc = call_steam_update_checker(APP_ID, install_dir)
    if rc == 1:
        post_discord_embed(DEFAULT_DISCORD_TITLE, "Restarting due to server build update (post-crash)", 2067276)
        log("Detected server build update after crash", logging.INFO)
        return True, None
    post_discord_embed(DEFAULT_DISCORD_TITLE, "Server crashed — restarting.", 11027200)
    log("Restarting server (no updates detected)", logging.INFO)
    return True, None

def main_loop(install_dir: Path, app_id: str, steamcmd_dir: Path, mod_list_path: Path,
              mod_update_checker_dir: Path, update_checker_dir: Path, dry_run: bool, once: bool):
    global DRY_RUN, WEBHOOK_URL, STEAMCMD_LOCATION, APP_ID
    DRY_RUN = dry_run
    STEAMCMD_LOCATION = steamcmd_dir
    APP_ID = app_id

    workshop_dir = install_dir / "steamapps" / "workshop" / "content" / DEFAULT_STEAM_APPID_FOR_WORKSHOP

    # ensure steamcmd available (will download if necessary)
    try:
        ensure_steamcmd(STEAMCMD_LOCATION)
    except Exception as e:
        log(f"Failed to prepare SteamCMD: {e}", logging.WARNING)

    # instantiate server process manager
    srv = ServerProcess()

    # initial checks
    ok = check_server_on_launch(install_dir)
    if not ok:
        log("Initial build update detected on launch; will handle in sync flow.", logging.INFO)

    # initial mod sync
    mods_to_load = sync_workshop_mods(mod_list_path, install_dir, workshop_dir, DEFAULT_STEAM_APPID_FOR_WORKSHOP)

    loop_count = 0
    update_interval = int(RUNTIME.get("update_interval", 600))
    init_wait_time = int(RUNTIME.get("init_wait_time", 30))
    restart_delay = int(RUNTIME.get("restart_delay", 30))
    enable_checks = bool(RUNTIME.get("enable_auto_update_checks", True))

    while True:
        loop_count += 1
        log(f"=== Launch iteration {loop_count} ===", logging.INFO)

        started = srv.start(install_dir, DEFAULT_GAME_BIN_REL, DEFAULT_SERVER_EXE, mods_to_load)
        if not started:
            log("Server failed to start; retrying after delay", logging.WARNING)
            time.sleep(restart_delay)
            if once:
                log("Exiting after single attempt (--once).", logging.INFO)
                return
            continue

        # --- Initialization wait ---
        log(f"Server init wait: allowing {init_wait_time}s for OHD to start...", logging.INFO)
        for sec in range(init_wait_time):
            if not srv.is_running():
                log("Server process ended unexpectedly during initialization.", logging.WARNING)
                srv.kill()
                break
            time.sleep(1)
        else:
            log("Server initialization wait complete — entering monitoring loop.", logging.INFO)

        # Monitoring
        check_timer = 0
        while True:
            time.sleep(5)
            check_timer += 5

            # Crash detection
            if not srv.is_running():
                log("Server process not running (crash or exit).", logging.WARNING)
                srv.kill()
                should_restart, new_mods = after_crash_checks_and_prepare(srv, install_dir, mod_list_path, workshop_dir, DEFAULT_STEAM_APPID_FOR_WORKSHOP)
                if new_mods is not None:
                    mods_to_load = new_mods
                break

            # Periodic checks
            if enable_checks and check_timer >= update_interval:
                check_timer = 0
                log(f"Performing periodic update check (interval={update_interval}s)", logging.INFO)

                # Mod check (skip if no mods)
                if getattr(sys.modules.get('config', None), "MOD_LIST", None) or MOD_LIST:
                    try:
                        if call_python_update_checker_for_mods():
                            log("Detected mod update during runtime.", logging.INFO)
                            post_discord_embed(DEFAULT_DISCORD_TITLE, "Restarting — mod update detected.", 10038562)
                            srv.kill()
                            mods_to_load = sync_workshop_mods(mod_list_path, install_dir, workshop_dir, DEFAULT_STEAM_APPID_FOR_WORKSHOP)
                            break
                    except Exception as e:
                        log(f"Runtime mod check failed: {e}", logging.WARNING)
                else:
                    log("Skipping mod check — MOD_LIST empty.", logging.DEBUG)

                # Server build check
                try:
                    rc = call_steam_update_checker(APP_ID, install_dir)
                    if rc == 1:
                        log("Detected server build update during runtime.", logging.INFO)
                        post_discord_embed(DEFAULT_DISCORD_TITLE, "Restarting — new server build detected.", 2067276)
                        srv.kill()
                        break
                except Exception as e:
                    log(f"Runtime build check failed: {e}", logging.WARNING)

        if once:
            log("Finished single run (--once). Exiting.", logging.INFO)
            return

# -------------------------
# Service helpers
# -------------------------
def is_root():
    try:
        return os.geteuid() == 0
    except Exception:
        return False

def install_systemd_service(script_path: Path, service_name: str, extra_args: str = "") -> bool:
    unit_path = Path("/etc/systemd/system") / f"{service_name}.service"
    python_bin = sys.executable
    exec_start = f"{python_bin} {script_path} {extra_args}".strip()
    unit_content = f"""[Unit]
Description=OHD Server Manager
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartSec=10
StandardOutput=append:/var/log/{service_name}.log
StandardError=append:/var/log/{service_name}.err
User={os.getenv('SUDO_USER') or os.getenv('USER') or 'root'}
WorkingDirectory={script_path.parent}

[Install]
WantedBy=multi-user.target
"""
    if not is_root():
        log("systemd install requires root", logging.ERROR)
        return False
    try:
        unit_path.write_text(unit_content, encoding="utf-8")
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", service_name], check=True)
        subprocess.run(["systemctl", "start", service_name], check=True)
        log("Installed systemd service", logging.INFO)
        return True
    except Exception as e:
        log(f"Failed to install systemd service: {e}", logging.ERROR)
        return False

def remove_systemd_service(service_name: str) -> bool:
    unit_path = Path("/etc/systemd/system") / f"{service_name}.service"
    if not is_root():
        log("systemd removal requires root", logging.ERROR)
        return False
    try:
        subprocess.run(["systemctl", "stop", service_name], check=False)
        subprocess.run(["systemctl", "disable", service_name], check=False)
        if unit_path.exists():
            unit_path.unlink()
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        log("Removed systemd service", logging.INFO)
        return True
    except Exception as e:
        log(f"Failed to remove systemd service: {e}", logging.ERROR)
        return False

# -------------------------
# CLI / Entrypoint
# -------------------------
def build_arg_parser():
    p = argparse.ArgumentParser(description="OHD Server Manager (Ubuntu-adapted)")
    p.add_argument("--install-dir", "-i", type=Path, default=DEFAULT_INSTALL_DIR, help="Server install directory")
    p.add_argument("--app-id", "-a", default=DEFAULT_APP_ID, help="Steam App ID for server")
    p.add_argument("--steamcmd-dir", type=Path, default=DEFAULT_STEAMCMD_DIR, help="SteamCMD directory")
    p.add_argument("--mod-list", type=Path, default=None, help="Modlist file (ignored if config.MOD_LIST set)")
    p.add_argument("--dry-run", action="store_true", help="Don't execute commands that modify system")
    p.add_argument("--once", action="store_true", help="Run one iteration then exit")
    p.add_argument("--no-webhook", action="store_true", help="Disable Discord webhook posting")
    p.add_argument("--webhook-url", default=None, help="Override webhook URL")
    p.add_argument("--log-file", default=None, help="Path to log file")
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    p.add_argument("--create-localupdates", nargs="?", const="", default=None, help="Create localupdates.json. Optional path; auto-detect if omitted.")
    p.add_argument("--update-checker-dir", type=Path, default=None, help="Directory for base update checker scripts (default: <install-dir>/UpdateChecker)")
    p.add_argument("--mod-update-checker-dir", type=Path, default=None, help="Directory for mod update checker scripts (default: <install-dir>/UpdateChecker)")
    p.add_argument("--install-systemd", action="store_true", help="Install systemd service (Linux, root)")
    p.add_argument("--remove-systemd", action="store_true", help="Remove systemd service (Linux, root)")
    p.add_argument("--service-name", default="ohd_server_manager", help="Service name for systemd")
    return p

def find_steam_workshop_dir() -> Optional[Path]:
    home = Path.home()
    appid = DEFAULT_STEAM_APPID_FOR_WORKSHOP
    # Common linux locations
    candidates = [
        home / ".steam" / "steam" / "steamapps" / "workshop" / "content" / appid,
        home / ".local" / "share" / "Steam" / "steamapps" / "workshop" / "content" / appid,
        DEFAULT_INSTALL_DIR / "steamapps" / "workshop" / "content" / appid
    ]
    for p in candidates:
        if p and p.exists():
            print(f"[AUTO-DETECT] Found workshop folder: {p.resolve()}")
            return p.resolve()
    return None

def create_or_update_localupdates(path_to_use: Optional[Path] = None):
    try:
        if path_to_use is None:
            path_to_use = find_steam_workshop_dir()
        if path_to_use is None:
            print("[ERROR] Could not auto-detect OHD workshop folder (736590). Provide path if needed.")
            return
        print(f"[INFO] Creating/updating localupdates.json for: {path_to_use}")
        FileManager.getInstance()
        local_updates = FileManager.updateJsonFile(str(path_to_use))
        if local_updates:
            print("✅ localupdates.json created/updated successfully.")
        else:
            print("[ERROR] Failed to create/update localupdates.json.")
            return
    except Exception as e:
        print("[ERROR] Failed creating localupdates.json:")
        traceback.print_exc()
        return

def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.create_localupdates is not None:
        provided = args.create_localupdates.strip() if isinstance(args.create_localupdates, str) else ""
        path_to_use: Optional[Path] = None
        if provided:
            path_to_use = Path(provided).expanduser().resolve()
            if not path_to_use.exists():
                print(f"[ERROR] Provided path not found: {path_to_use}")
                return
        else:
            path_to_use = find_steam_workshop_dir()
        if path_to_use is None:
            print("[ERROR] Could not auto-detect OHD workshop folder (736590). Provide path with --create-localupdates <path>")
            return
        create_or_update_localupdates(path_to_use)
        return

    install_dir = args.install_dir
    app_id = args.app_id
    steamcmd_dir = args.steamcmd_dir
    mod_list_path = args.mod_list or (install_dir / DEFAULT_MODLIST_FILENAME)
    dry_run = args.dry_run or RUNTIME.get("dry_run", False)
    once = args.once or RUNTIME.get("once", False)
    no_webhook = args.no_webhook
    webhook_url = args.webhook_url
    log_file_arg = args.log_file
    debug = args.debug or RUNTIME.get("debug", False)
    update_checker_dir = args.update_checker_dir or (install_dir / "UpdateChecker")
    mod_update_checker_dir = args.mod_update_checker_dir or (install_dir / "UpdateChecker")
    install_systemd = args.install_systemd
    remove_systemd = args.remove_systemd
    service_name = args.service_name

    global WEBHOOK_URL, MOD_LIST_FILE, UPDATE_CHECKER_DIR, MOD_UPDATE_CHECKER_DIR, STEAMCMD_DEL, STEAM_USER, APP_ID, DRY_RUN, STEAMCMD_LOCATION
    APP_ID = app_id
    STEAMCMD_LOCATION = steamcmd_dir
    DRY_RUN = dry_run

    if no_webhook:
        WEBHOOK_URL = ""
    else:
        WEBHOOK_URL = webhook_url or os.getenv("OHD_DISCORD_WEBHOOK") or WEBHOOK_URL_DEFAULT

    MOD_LIST_FILE = mod_list_path
    UPDATE_CHECKER_DIR = update_checker_dir
    MOD_UPDATE_CHECKER_DIR = mod_update_checker_dir

    log_file = Path(log_file_arg) if log_file_arg else (install_dir / DEFAULT_LOG_FILENAME)
    setup_logging(log_file, debug=debug)

    STEAMCMD_DEL = DEFAULT_STEAMCMD_DEL
    STEAM_USER = DEFAULT_STEAM_USER

    log("Starting OHD server manager (Ubuntu)", logging.INFO)
    log(f"install_dir={install_dir}, app_id={app_id}, steamcmd_dir={steamcmd_dir}", logging.DEBUG)

    script_path = Path(__file__).resolve()
    extra_args = f'--install-dir="{install_dir}" --app-id="{app_id}"'
    if install_systemd:
        install_systemd_service(script_path, service_name, extra_args)
        return
    if remove_systemd:
        remove_systemd_service(service_name)
        return

    try:
        main_loop(install_dir, app_id, steamcmd_dir, mod_list_path, mod_update_checker_dir, update_checker_dir, dry_run, once)
    except KeyboardInterrupt:
        log("Interrupted by user", logging.INFO)
    except Exception:
        log("Unhandled exception in main loop", logging.ERROR)
        traceback.print_exc()
        try:
            post_discord_embed(DEFAULT_DISCORD_TITLE, f"Server manager crashed: {traceback.format_exc()}", 16711680)
        except Exception:
            pass
        raise

if __name__ == "__main__":
    main()
