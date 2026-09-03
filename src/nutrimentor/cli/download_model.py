"""Download the BGE embedding model (ModelScope first, HuggingFace fallback)."""

from __future__ import annotations

import sys

from nutrimentor.config import EMBEDDING_MODEL_ID, MODEL_DIR


def main() -> int:
    if (MODEL_DIR / "config.json").exists():
        print(f"Model already present at {MODEL_DIR}")
        return 0
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    try:  # ModelScope — fast in mainland China
        from modelscope import snapshot_download

        print(f"Downloading {EMBEDDING_MODEL_ID} from ModelScope ...")
        snapshot_download(EMBEDDING_MODEL_ID, cache_dir=str(MODEL_DIR))
        print(f"\nDone. Model saved to {MODEL_DIR}")
        return 0
    except ImportError:
        print("modelscope not installed; trying HuggingFace Hub ...")
    except Exception as exc:
        print(f"ModelScope failed: {exc}; trying HuggingFace Hub ...")

    try:
        from huggingface_hub import snapshot_download

        print(f"Downloading {EMBEDDING_MODEL_ID} from HuggingFace Hub ...")
        snapshot_download(
            EMBEDDING_MODEL_ID, local_dir=str(MODEL_DIR), local_dir_use_symlinks=False
        )
        print(f"\nDone. Model saved to {MODEL_DIR}")
        return 0
    except Exception as exc:
        print(f"HuggingFace failed: {exc}")
        print(f"\nManual fallback: download from https://huggingface.co/{EMBEDDING_MODEL_ID} "
              f"and place files in {MODEL_DIR}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
