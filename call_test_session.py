import urllib.request
import json

# Call test-session for account 2
url = 'http://127.0.0.1:8000/api/accounts/2/test-session'
req = urllib.request.Request(url, method='POST', headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
        print(f"Test session response: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"Test session failed: {e}")
    import traceback
    traceback.print_exc()