import subprocess
import time
import sys
import urllib.request
import json

# Start backend
be = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'],
                      cwd=r'C:\Users\pakcomp\Downloads\midasbuy-automation\backend')
print(f"Backend started with PID: {be.pid}")

# Wait for startup with retries
for i in range(10):
    time.sleep(1)
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2) as resp:
            data = json.load(resp)
            print(f"Health check: {data}")
            print("Backend is ready!")
            break
    except Exception as e:
        print(f"Attempt {i+1}: {e}")
else:
    print("Backend failed to start")
    be.terminate()
    sys.exit(1)

# Keep backend running
try:
    be.wait()
except KeyboardInterrupt:
    be.terminate()