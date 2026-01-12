
import requests
import json

urls = [
    "https://www.slumbot.com/api/new_hand",
    "http://www.slumbot.com/api/new_hand",
    "https://slumbot.com/api/new_hand",
    "http://slumbot.com/api/new_hand"
]

bodies = [
    {},
    {"token": None},
    {"token": ""},
]

for url in urls:
    for body in bodies:
        try:
            print(f"Testing {url} with {body}...")
            resp = requests.post(url, json=body, timeout=5)
            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"  Success! Response: {resp.text[:100]}")
                break
            else:
                print(f"  Fail: {resp.text[:100]}")
        except Exception as e:
            print(f"  Error: {e}")
    print("-" * 20)
