import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api import create_app  # noqa: E402


def main() -> None:
    output_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/openapi")
    output_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(SimpleNamespace(api_token=""), None, None)
    app.version = os.getenv("APP_VERSION", "dev").removeprefix("v")

    output_file = output_dir / "openapi.json"
    output_file.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {output_file}")


if __name__ == "__main__":
    main()
