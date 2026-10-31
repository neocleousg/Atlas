@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set DJANGO_DEBUG=1
title ΑΤΛΑΣ - δοκιμή στον υπολογιστή

echo.
echo  ===============================================
echo   ΑΤΛΑΣ - εκκίνηση για δοκιμή στον υπολογιστή
echo  ===============================================
echo.

rem --- 1. Έλεγχος Python ---
where py >nul 2>nul
if not errorlevel 1 (
  set "PY=py -3"
  goto havepy
)
where python >nul 2>nul
if not errorlevel 1 (
  set "PY=python"
  goto havepy
)
echo  Δεν βρέθηκε η Python.
echo  Εγκαταστήστε την από https://www.python.org/downloads/
echo  και τσεκάρετε "Add python.exe to PATH" κατά την εγκατάσταση.
echo.
pause
exit /b 1

:havepy
rem --- 2. Πρώτη φορά: εγκατάσταση ---
if not exist ".venv\Scripts\python.exe" (
  echo  Πρώτη εκκίνηση: εγκατάσταση. Θα πάρει μερικά λεπτά...
  %PY% -m venv .venv
  if errorlevel 1 goto error
)
set VPY=.venv\Scripts\python.exe
"%VPY%" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto error

rem --- 3. Βάση δεδομένων ---
"%VPY%" manage.py migrate --noinput -v 0
if errorlevel 1 goto error

rem --- 4. Εικονικά δεδομένα μόνο την πρώτη φορά ---
if not exist "kodikoi_dokimis.txt" (
  "%VPY%" manage.py seed_demo --out kodikoi_dokimis.txt
  if errorlevel 1 goto error
)

echo.
echo  Οι κωδικοί δοκιμής είναι στο αρχείο kodikoi_dokimis.txt (ανοίγει τώρα).
echo  Ο ΑΤΛΑΣ ανοίγει στον browser: http://127.0.0.1:8000
echo  Για να σταματήσει, κλείστε αυτό το παράθυρο.
echo.
start "" notepad kodikoi_dokimis.txt
start "" http://127.0.0.1:8000
"%VPY%" manage.py runserver 127.0.0.1:8000 --noreload
goto end

:error
echo.
echo  Κάτι πήγε στραβά. Στείλτε στιγμιότυπο αυτού του παραθύρου.
pause
exit /b 1

:end
endlocal
