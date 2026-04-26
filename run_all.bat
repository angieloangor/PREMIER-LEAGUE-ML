start cmd /k "uvicorn api.main:app --reload --host 127.0.0.1 --port 8001"
timeout /t 2
start cmd /k "python -m http.server 8000"