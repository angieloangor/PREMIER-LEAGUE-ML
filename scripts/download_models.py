import logging
import os
import zipfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

MODELS_URL = "https://www.dropbox.com/scl/fi/xolz2cyr8bipmgcxumiqq/stage2_classifier_runs.zip?rlkey=cizjov7hvffeg0g931jcaognb&st=s47dvvp0&dl=1"
BASE_DIR = Path("outputs/model_runs/advanced_match_predictor")
TARGET_DIR = BASE_DIR / "stage2_classifier_runs"
ZIP_PATH = Path("models.zip")


def download_models_if_needed() -> None:
    if TARGET_DIR.exists() and any(TARGET_DIR.iterdir()):
        logger.info("Model bundles already available at %s", TARGET_DIR)
        return

    url = "https://www.dropbox.com/scl/fi/xolz2cyr8bipmgcxumiqq/stage2_classifier_runs.zip?rlkey=cizjov7hvffeg0g931jcaognb&st=s47dvvp0&dl=1"

    try:
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading model bundles from %s", url)

        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type.lower():
            logger.error(
                "Model download returned HTML instead of ZIP. Google Drive requires public access."
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
