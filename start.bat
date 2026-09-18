@echo off
REM BrandShield AI - one-click start (Windows)
REM Builds the dashboard if needed and starts the API on http://127.0.0.1:8000

cd /d "%~dp0"

if not exist env\Scripts\python.exe (
    echo Creating Python virtual environment...
    python -m venv env || goto :error
)

echo Installing / checking Python packages...
env\Scripts\python.exe -m pip install -q -r backend\requirements.txt || goto :error
env\Scripts\python.exe -c "import nltk; [nltk.download(p, quiet=True) for p in ('stopwords','wordnet','omw-1.4')]"

if not exist frontend\dist\index.html (
    echo Building the dashboard...
    pushd frontend
    call npm install || goto :error
    call npm run build || goto :error
    popd
)

echo.
echo Starting BrandShield AI at http://127.0.0.1:8000
echo (first start downloads the DistilBERT model and generates demo history - give it a few minutes)
echo.
start "" http://127.0.0.1:8000
cd backend
..\env\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
goto :eof

:error
echo.
echo Setup failed - see the messages above.
pause
