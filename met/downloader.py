import os
import requests
from urllib.parse import quote
from dotenv import load_dotenv

# Load the environment variables from the .env file
load_dotenv()

API_KEY = os.getenv("MET_API_KEY")

BASE = "https://data.hub.api.metoffice.gov.uk/atmospheric-models/1.0.0"
ORDER_ID = "o192605536227"

HEADERS_JSON = {"apikey": API_KEY, "accept": "application/json"}
HEADERS_GRIB = {"apikey": API_KEY, "accept": "application/x-grib"}

os.makedirs("grib", exist_ok=True)

# Get file list
data = requests.get(f"{BASE}/orders/{ORDER_ID}/latest", headers=HEADERS_JSON).json()
files = data["orderDetails"]["files"]

# Filter to +15 files only
latest_files = [f for f in files if f["fileId"].startswith("isbl_") and "_+15_" in f["fileId"]]

print(f"Found {len(latest_files)} files to download")

for f in latest_files:
    file_id = f["fileId"]
    encoded = quote(file_id, safe="")
    response = requests.get(
        f"{BASE}/orders/{ORDER_ID}/latest/{encoded}/data",
        headers=HEADERS_GRIB,
        allow_redirects=True,
    )
    # Save with the raw fileId as the name — renamer.py will clean these up
    filename = f"grib/{file_id}.grib2"
    with open(filename, "wb") as out:
        out.write(response.content)
    print(f"Saved {filename} ({len(response.content):,} bytes)")