from pathlib import Path
import os

PROGRAM_DATA = Path(os.environ["PROGRAMDATA"])
BASE_DIR = PROGRAM_DATA / "CCTV_AI_SYSTEM"
LICENSE_DIR = BASE_DIR / "license"

LICENSE_DIR.mkdir(parents=True, exist_ok=True)

LICENSE_FILE = LICENSE_DIR / "license.dat"
CACHE_FILE = LICENSE_DIR / "cache.dat"
RUNTIME_FILE = LICENSE_DIR / "runtime.dat"
MACHINE_FILE = LICENSE_DIR / "machine_uuid.dat"