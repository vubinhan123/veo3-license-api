import requests
import json
import time
import subprocess
import os
import signal

# Chay server fastapi trong nen de lay log
cmd = 'cmd.exe /c "call .venv\\Scripts\\activate.bat && uvicorn app.main:app --host 127.0.0.1 --port 8080"'
print(f"[*] Starting server on 8080...")
proc = subprocess.Popen(cmd, shell=True, cwd="G:\\LVC_Veo3_Automation_v1.2.62\\quanlykeyveo3-backend")
time.sleep(5)

try:
    API_URL = "http://127.0.0.1:8080/api/v1"
    key_to_verify = "E3D3-518F-1AE9-61E6-B32F-C250-9E11-2DB2" # Test with dummy key to get 400 or logic trace
    hwid = "TEST_HWID_ABC_123"
    
    print(f"[*] Verifying key: {key_to_verify}")
    res = requests.post(f"{API_URL}/license/verify", json={"license_key": key_to_verify, "hwid": hwid})
    print(f"Status Code: {res.status_code}")
    print(f"Response: {res.text}")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    # Kill the server
    subprocess.call(['taskkill', '/F', '/T', '/PID', str(proc.pid)])
