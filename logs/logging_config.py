# logs/logging_config.py

import logging
import os


LOGGING_DIR = r"logs"
os.makedirs(LOGGING_DIR, exist_ok=True)

# ---- THE LOGGER CONFIGURATION BLOCK ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=os.path.join(LOGGING_DIR, "logs.log"), # The path to the log file
    filemode="a", # 'a' - add to the end, 'w' - overwrite,
    encoding="utf-8"
)