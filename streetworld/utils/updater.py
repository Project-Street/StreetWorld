import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path


UPDATE_URL = "http://101.201.109.161:8001/streetworld/update"


def update_streetworld_if_needed():
    project_root = Path(__file__).resolve().parents[2]
    local_version = (project_root / ".version").read_text(encoding="utf-8").strip()
    request_body = json.dumps({"version": local_version}).encode("utf-8")
    request = urllib.request.Request(
        UPDATE_URL,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        if response.status == 204:
            return False

        tmp_dir = Path("/tmp") / "StreetWorld_update"
        zip_path = tmp_dir / "StreetWorld.zip"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir()

        print("StreetWorld version mismatch. Updating...", file=sys.stderr)
        try:
            with zip_path.open("wb") as file:
                shutil.copyfileobj(response, file)
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(project_root)
        finally:
            shutil.rmtree(tmp_dir)

    print("StreetWorld update applied. Exiting launcher.", file=sys.stderr)
    return True
