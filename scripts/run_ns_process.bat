@echo off
set PATH=C:\colmap38\COLMAP-3.8-windows-cuda;%PATH%
call C:\Users\krris\anaconda3\Scripts\activate.bat recon
ns-process-data images --data views --output-dir processed
