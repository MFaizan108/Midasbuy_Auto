import urllib.request
import json

# Call login for account 2
url = 'http://127.0.0.1:8000/api/accounts/2/login'
req = urllib.request.Request(url, method='POST', headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
        print(f"Login response: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"Login failed: {e}")
    import traceback
    traceback.print_exc()