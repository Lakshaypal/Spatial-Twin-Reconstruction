@echo off
REM ==========================================================================
REM  SETUP_recon.bat — build the 'recon' conda environment (Windows)
REM
REM  RUN THE MANUAL PREREQUISITES FIRST (see SETUP_GUIDE.md):
REM    1. Miniconda
REM    2. Visual Studio Build Tools 2022 (with "Desktop development with C++")
REM    3. CUDA Toolkit 11.8
REM    4. FFmpeg on PATH
REM    5. COLMAP on PATH
REM
REM  Then: right-click this file -> Run, or run it from an "Anaconda Prompt".
REM ==========================================================================

echo ==========================================================
echo   Building conda env: recon
echo ==========================================================
echo.

REM --- check conda exists ---
where conda >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] conda not found.
    echo Install Miniconda first, then run this from an "Anaconda Prompt".
    pause
    exit /b 1
)

REM --- show what GPU/driver we have ---
echo --- Your GPU / driver ---
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
echo.

REM --- create env ---
echo [1/6] Creating conda env 'recon' (python 3.10)...
call conda create -n recon python=3.10 -y
if %errorlevel% neq 0 goto :fail

echo [2/6] Activating...
call conda activate recon
if %errorlevel% neq 0 goto :fail

REM --- pytorch with CUDA 11.8 (most compatible choice) ---
echo [3/6] Installing PyTorch (CUDA 11.8)...
pip install torch==2.1.2+cu118 torchvision==0.16.2+cu118 --index-url https://download.pytorch.org/whl/cu118
if %errorlevel% neq 0 goto :fail

REM --- build helper ---
echo [4/6] Installing build tools...
pip install ninja
if %errorlevel% neq 0 goto :fail

REM --- nerfstudio (pulls gsplat, which COMPILES — this is the slow part) ---
echo [5/6] Installing Nerfstudio + gsplat (this compiles CUDA — be patient)...
pip install nerfstudio
if %errorlevel% neq 0 goto :fail

REM --- our reframe script deps ---
echo [6/6] Installing reframe deps...
pip install py360convert opencv-python numpy
if %errorlevel% neq 0 goto :fail

echo.
echo ==========================================================
echo   DONE. Now verify with:
echo       conda activate recon
echo       python verify_setup.py
echo ==========================================================
pause
exit /b 0

:fail
echo.
echo ==========================================================
echo   [FAILED] A step above errored. Read the last error text.
echo   See SETUP_GUIDE.md -> Troubleshooting.
echo ==========================================================
pause
exit /b 1
