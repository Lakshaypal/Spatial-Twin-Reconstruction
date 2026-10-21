@echo off
echo Creating lingbot_map environment...
call conda create -n lingbot_map python=3.10 -y
if errorlevel 1 exit /b 1

echo Activating environment...
call conda activate lingbot_map

echo Installing PyTorch 2.8.0 with cu128...
pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 exit /b 1

cd lingbot-map
echo Installing lingbot-map package...
pip install -e .
if errorlevel 1 exit /b 1

echo Installing FlashInfer...
pip install --index-url https://pypi.org/simple flashinfer-python
if errorlevel 1 exit /b 1

echo Setup complete!
