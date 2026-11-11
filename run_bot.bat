@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
	".venv\Scripts\python.exe" bot.py
) else (
	py -3 bot.py
)
if errorlevel 1 echo Бот завершился с ошибкой. Проверьте сообщение выше.
pause
