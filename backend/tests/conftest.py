import sys
from pathlib import Path

# Make `import app...` work when pytest is run from the repo root or from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
