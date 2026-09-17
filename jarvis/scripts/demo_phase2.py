import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
from scripts.demo_phase2 import run_demonstrations

if __name__ == "__main__":
    asyncio.run(run_demonstrations())
