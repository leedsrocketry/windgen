import os
import requests
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("MET_API_KEY")
BASE     = "https://data.hub.api.metoffice.gov.uk/atmospheric-models/1.0.0"
ORDER_ID = "o001556024975"

HEADERS_JSON = {"apikey": API_KEY, "accept": "application/json"}
HEADERS_GRIB = {"apikey": API_KEY, "accept": "application/x-grib"}

os.makedirs("grib", exist_ok=True)

# ── File list ─────────────────────────────────────────────────────────────────

resp = requests.get(f"{BASE}/orders/{ORDER_ID}/latest", headers=HEADERS_JSON)
print(f"HTTP {resp.status_code} {resp.reason}  {resp.url}")
resp.raise_for_status()
files = resp.json()["orderDetails"]["files"]

latest_files = [f for f in files if f["fileId"].startswith("isbl_") and "_+15_" in f["fileId"]]
print(f"Found {len(latest_files)} files to download\n")

# ── Download ──────────────────────────────────────────────────────────────────

ok = skipped = failed = 0

for f in latest_files:
    file_id  = f["fileId"]
    encoded  = quote(file_id, safe="")
    filename = f"grib/{file_id}.grib2"

    # Skip files that already exist and look valid (>10 KB)
    if os.path.exists(filename) and os.path.getsize(filename) > 10_000:
        print(f"  SKIP  {file_id}  (already downloaded)")
        skipped += 1
        continue

    response = requests.get(
        f"{BASE}/orders/{ORDER_ID}/latest/{encoded}/data",
        headers=HEADERS_GRIB,
        allow_redirects=True,
    )

    # ── Validate before writing ───────────────────────────────────────────────
    if response.status_code != 200:
        print(f"  FAIL  {file_id}  HTTP {response.status_code}: {response.text[:120]}")
        failed += 1
        continue

    content_type = response.headers.get("Content-Type", "")
    if "grib" not in content_type and "octet-stream" not in content_type:
        print(f"  FAIL  {file_id}  unexpected Content-Type: {content_type!r}")
        print(f"        body preview: {response.content[:200]}")
        failed += 1
        continue

    # GRIB2 files start with the magic bytes "GRIB"
    if not response.content[:4] == b"GRIB":
        print(f"  FAIL  {file_id}  missing GRIB magic bytes — got: {response.content[:20]}")
        failed += 1
        continue

    with open(filename, "wb") as out:
        out.write(response.content)

    size_kb = len(response.content) / 1024
    print(f"  OK    {file_id}  ({size_kb:,.1f} KB)")
    ok += 1

# ── Summary ───────────────────────────────────────────────────────────────────

print(f"\n{'─'*52}")
print(f"  Downloaded : {ok}")
print(f"  Skipped    : {skipped}  (already on disk)")
print(f"  Failed     : {failed}")