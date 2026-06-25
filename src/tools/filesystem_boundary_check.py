from pathlib import Path
import os


def main() -> int:
    root = Path("/data/3.8T-1/yue").resolve()
    names = [
        "HOME",
        "TMPDIR",
        "XDG_CACHE_HOME",
        "HF_HOME",
        "HUGGINGFACE_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "TORCH_HOME",
        "PIP_CACHE_DIR",
        "UV_CACHE_DIR",
        "CONDA_PKGS_DIRS",
    ]
    failed = False
    for name in names:
        value = os.environ.get(name)
        if not value:
            print(name, "MISSING")
            failed = True
            continue
        path = Path(value).expanduser().resolve()
        ok = root == path or root in path.parents
        print(name, path, "OK" if ok else "OUTSIDE_ROOT")
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
