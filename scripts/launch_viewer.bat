@echo off
title RECON VIEWER - Professional 3D Inspector
echo.
echo  ========================================
echo   RECONSTRUCTION VIEWER LAUNCHER
echo   READ-ONLY - no files will be modified
echo  ========================================
echo.

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [!] Python not found in PATH.
    pause
    exit /b 1
)

:: Try Open3D first
echo  [1/2] Checking for Open3D...
python -c "import open3d" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  [OK] Open3D found! Launching Python viewer...
    echo.
    python "%~dp0viewer.py" %*
    goto :END
)

echo  [ ] Open3D not installed - using browser viewer.
echo.
echo  [2/2] Starting local file server + Three.js viewer...
echo.

python -c "import http.server,socketserver,os,sys,webbrowser,threading,urllib.parse;RECON=r'C:\recon';VD=r'%~dp0'.rstrip('\\');PORT=9876;exec(\"\"\"class H(http.server.SimpleHTTPRequestHandler):\n def translate_path(self,p):\n  p=urllib.parse.unquote(p).lstrip('/')\n  if p=='' or p=='viewer.html':return os.path.join(VD,'viewer.html')\n  rp=os.path.join(RECON,p)\n  if os.path.exists(rp):return rp\n  vp=os.path.join(VD,p)\n  return vp if os.path.exists(vp) else rp\n def end_headers(self):\n  self.send_header('Access-Control-Allow-Origin','*')\n  self.send_header('Cache-Control','no-cache')\n  super().end_headers()\n def log_message(self,f,*a):\n  if '.ply' in str(a) or '.html' in str(a):sys.stderr.write('  [SERVE] %%s\\n'%%(a[0],))\n\"\"\")\nprint(f'  Serving: {RECON}')\nprint(f'  Viewer:  {VD}')\nprint(f'  URL:     http://localhost:{PORT}/viewer.html')\nprint()\nprint('  Press Ctrl+C to stop.')\nprint()\nthreading.Thread(target=lambda:((__import__('time').sleep(1.5)),webbrowser.open(f'http://localhost:{PORT}/viewer.html')),daemon=True).start()\nwith socketserver.TCPServer(('',PORT),H) as s:\n try:s.serve_forever()\n except KeyboardInterrupt:print('\\n  Stopped.')"

:END
echo.
pause
