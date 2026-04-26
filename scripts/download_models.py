import logging
import os
import zipfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

BASE_DIR = Path("outputs/model_runs/advanced_match_predictor")
TARGET_DIR = BASE_DIR / "stage2_classifier_runs"
LOCAL_ZIP_PATH = Path("model_artifacts/stage2_classifier_runs.zip")
ZIP_PATH = Path("models.zip")


def download_models_if_needed() -> None:
    if TARGET_DIR.exists() and any(TARGET_DIR.iterdir()):
        logger.info("Model bundles already available at %s", TARGET_DIR)
        return

    try:
        BASE_DIR.mkdir(parents=True, exist_ok=True)

        if LOCAL_ZIP_PATH.exists():
            logger.info("Extracting local model bundle from %s", LOCAL_ZIP_PATH)
            logger.info("Extracting ZIP...")
            with zipfile.ZipFile(LOCAL_ZIP_PATH, "r") as zip_ref:
                zip_ref.extractall(BASE_DIR)
            logger.info("Model bundles ready at %s", TARGET_DIR)
            return

        url = os.getenv("MODEL_BUNDLE_ZIP_URL")
        if not url:
            logger.warning(
                "Local model bundle missing and MODEL_BUNDLE_ZIP_URL is not set."
            )
            return

        logger.info("Downloading model bundles from %s", url)

        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type.lower():
            logger.error(
                "Model download returned HTML instead of ZIP. Check MODEL_BUNDLE_ZIP_URL."
            )
            return

        with ZIP_PATH.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)

        logger.info("Extracting ZIP...")
        with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
            zip_ref.extractall(BASE_DIR)

        ZIP_PATH.unlink(missing_ok=True)
        logger.info("Model bundles ready at %s", TARGET_DIR)

    except Exception as exc:
        logger.exception("Could not download or extract model bundles: %s", exc)
        try:
            ZIP_PATH.unlink(missing_ok=True)
        except Exception:
            pass
