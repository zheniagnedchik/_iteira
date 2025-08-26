import tempfile
import os
from aiogram import Bot
from aiogram.types import Voice
import openai
from config import OPENAI_API_KEY

client = openai.OpenAI(api_key=OPENAI_API_KEY)


async def transcribe_with_whisper(bot: Bot, voice: Voice) -> str:
    """
    1. Get the file_info and file_path from the Telegram (from bot and Voice objects).
    2. Download the file to BytesIO object and read bytes.
    3. Save to a temporary .ogg file to send to Whisper.
    4. Call Whisper (Openal) and get the decryption.
    5. Delete the temporary file and returns the transcribed text.
    """
    # 1. Receive information about the file (the path on the Telegram servers)
    try:
        file_info = await bot.get_file(voice.file_id)
        file_path = file_info.file_path
    except Exception as e:
        print(f"[transcribe_with_whisper]: Error while getting file_info: {e}")
        return ""

    # 2. Download the file to the BytesIO object and read bytes from it
    try:
        downloaded_file = await bot.download_file(file_path)
        audio_data = downloaded_file.read()
    except Exception as e:
        print(f"[transcribe_with_whisper]: Error while downloading the file from Telegram: {e}")
        return ""

    # 3. Create a temporary .ogg audio recording file
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
    except Exception as e:
        print(f"[transcribe_with_whisper]: Error while creating a temporary file: {e}")
        return ""
    
    # 4. Open a temporary file and send it to the OpenAI Whisper API
    try:
        with open(temp_file_path, 'rb') as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru"
            )
            # Extract the text from the transcription result
            transcribed_text = transcription.text.strip()
    except Exception as e:
        print(f"[transcribe_with_whisper]: Error while sending the file to Whisper: {e}")
        transcribed_text = ""
    
    finally:
        # 5. Delete the temporary file after use
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    return transcribed_text