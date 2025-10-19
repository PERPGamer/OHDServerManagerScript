@echo off
echo Installing OHD Server Manager Prerequisites...

:: Check if Python is installed
echo Checking for Python...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python is not installed. Please install Python from https://www.python.org/downloads/
    pause
    exit /b
)

:: Check if pip is installed
echo Checking for pip...
python -m ensurepip --upgrade
if %errorlevel% neq 0 (
    echo pip is not installed. Please ensure pip is installed.
    pause
    exit /b
)

:: Install required Python packages
echo Installing required Python packages...
pip install --upgrade pip
pip install requests psutil

:: Check if SteamCMD is installed
echo Checking for SteamCMD...
if not exist "C:\steamcmd\steamcmd.exe" (
    echo SteamCMD not found. Downloading SteamCMD...
    :: Create SteamCMD directory if not exists
    mkdir "C:\steamcmd"
    :: Download SteamCMD (Windows version)
    powershell -Command "Invoke-WebRequest -Uri 'https://steamcdn-a.akamaihd.net/client/steamcmd/steamcmd.zip' -OutFile 'C:\steamcmd\steamcmd.zip'"
    echo Extracting SteamCMD...
    powershell -Command "Expand-Archive -Path 'C:\steamcmd\steamcmd.zip' -DestinationPath 'C:\steamcmd'"
    del "C:\steamcmd\steamcmd.zip"
    echo SteamCMD installed at C:\steamcmd
)

echo All prerequisites are installed successfully!
pause
