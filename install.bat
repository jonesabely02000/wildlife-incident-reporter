@echo off
echo Installing Website...
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
echo Installation complete!
pause