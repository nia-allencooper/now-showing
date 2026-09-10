@echo off
REM  Now Showing - weekly update, run by Windows Task Scheduler on Tuesday evening.
REM  Scrapes Odeon, rebuilds the page, and pushes. GitHub Pages publishes on the push.

cd /d "%~dp0"

call ".venv\Scripts\activate.bat"

echo [%date% %time%] pulling latest
git pull --quiet --rebase --autostash

echo [%date% %time%] scraping
python scrape.py
if errorlevel 1 (
  echo scrape failed - leaving last week's snapshot in place, not pushing
  exit /b 1
)

echo [%date% %time%] building
python build.py
if errorlevel 1 exit /b 1

echo [%date% %time%] committing and pushing
git add snapshots site
git commit -m "Weekly update %date%" || echo (nothing changed this week)
git push

echo [%date% %time%] done
