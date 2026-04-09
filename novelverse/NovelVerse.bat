@echo off
echo Starting NovelVerse...
start cmd /k "python app.py"
timeout /t 3
start cmd /k "ngrok http --url=allowably-unconfusable-angie.ngrok-free.dev 80"
echo Both started! Your site is live.