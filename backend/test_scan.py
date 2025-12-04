import requests
import time

BASE_URL = "http://127.0.0.1:8000"
EMAIL = "scan_test@example.com"
PASSWORD = "password123"

def register_and_login():
    # Register
    try:
        requests.post(f"{BASE_URL}/auth/register", json={"email": EMAIL, "password": PASSWORD})
    except:
        pass # User might exist

    # Login
    response = requests.post(f"{BASE_URL}/auth/login", data={"username": EMAIL, "password": PASSWORD})
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return None
    return response.json()["access_token"]

def test_scan_flow(token):
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create Scan
    print("Creating scan...")
    scan_data = {
        "target": "127.0.0.1",
        "phases": ["Passive Recon", "Active Recon"]
    }
    response = requests.post(f"{BASE_URL}/scans/", json=scan_data, headers=headers)
    if response.status_code != 200:
        print(f"Create scan failed: {response.text}")
        return
    
    scan_id = response.json()["id"]
    print(f"Scan created with ID: {scan_id}")

    # Poll Status
    while True:
        response = requests.get(f"{BASE_URL}/scans/{scan_id}", headers=headers)
        scan = response.json()
        status = scan["status"]
        print(f"Scan Status: {status}")
        
        if status in ["Completed", "Failed"]:
            break
        
        # Check for AI results
        results = scan.get("results", [])
        ai_results = [r for r in results if r["tool"] == "AI_PHASE_SUMMARY"]
        if ai_results:
            print(f"Found {len(ai_results)} AI Analysis results.")
            for r in ai_results:
                print(f"  - Phase: {r['phase']}, Status: {r['status']}, Summary Len: {len(r['gemini_summary'] or '')}")
        
        time.sleep(2)

if __name__ == "__main__":
    token = register_and_login()
    if token:
        test_scan_flow(token)
