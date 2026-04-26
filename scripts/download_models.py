import os
import requests
import zipfile
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_models_if_needed():
    """
    Descarga y descomprime los modelos desde Google Drive en el directorio de outputs
    si no se detecta la carpeta de stage2 (necesario para Render).
    """
    base_dir = "outputs/model_runs/advanced_match_predictor/"
    check_dir = os.path.join(base_dir, "stage2_classifier_runs")
    url = "https://drive.google.com/uc?export=download&id=18FZqa6kKu-HSn_pXmTuYezWfMgnzpJt7"
    zip_path = "models.zip"

    if os.path.exists(check_dir):
        logger.info(f"✓ Modelos detectados en {check_dir}. Omitiendo descarga.")
        return

    logger.info("! Carpeta de modelos no encontrada en 'outputs/'. Iniciando descarga desde Google Drive...")
    
    try:
        # Crear la estructura de carpetas si no existe
        os.makedirs(base_dir, exist_ok=True)
        
        # Descarga del archivo ZIP usando stream
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info("Descarga completa. Descomprimiendo archivos...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(base_dir)
        
        # Limpieza del archivo temporal
        os.remove(zip_path)
        logger.info("✓ Modelos instalados correctamente en el entorno.")
        
    except Exception as e:
        logger.warning(f"⚠ No se pudieron descargar los modelos automáticamente: {e}")
        logger.warning("La API intentará iniciar, pero fallará si no se cargan modelos de forma manual.")

if __name__ == "__main__":
    download_models_if_needed()