import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from appcore import add
if __name__ == "__main__":
    if "--self-test" in sys.argv:
        if add(2, 3) != 5:
            raise SystemExit(1)
    print(f"razer-battery: 2 + 3 = {add(2, 3)}")
