import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Maximum number of messages in the history
MAX_HISTORY_LENGTH = 10

# Paths to the data and the chroma_db
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "knowledge_base")
CHROMA_PATH = os.path.join(BASE_DIR, "data", "chroma_db")

