@echo off
echo Creating Python virtual environment...
python -m venv venv

if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
    
    echo Installing requirements...
    pip install --upgrade pip
    pip install -r requirements.txt
    
    echo.
    echo Virtual environment setup complete!
    echo To activate in the future, run: .\venv\Scripts\activate
) else (
    echo Failed to create virtual environment.
    pause
)
