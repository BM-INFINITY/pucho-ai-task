import os
import asyncio
import re
import json
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from google import genai

# Import local simplified helper modules
import speech
import clickup

# Initialize logging to show execution status and debug details in the console
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment configuration variables from the .env file
load_dotenv()

# Retrieve Telegram API configuration parameters required by Pyrogram
api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

# Validate that the necessary environment variables are set before starting the Client
if not api_id or not api_hash or "YOUR_TELEGRAM_API_" in str(api_id) or "YOUR_TELEGRAM_API_" in str(api_hash):
    logger.error("Pyrogram requires valid TELEGRAM_API_ID and TELEGRAM_API_HASH values in the .env file.")
    print("\n⚠️ CONFIGURATION ERROR: Please set your TELEGRAM_API_ID and TELEGRAM_API_HASH in the .env file first!")
    import sys
    sys.exit(1)

# Initialize the Pyrogram Client using bot token authentication
app = Client(
    "pucho_bot",
    api_id=int(api_id),
    api_hash=api_hash,
    bot_token=bot_token
)

# Initialize the Google Gemini API Client
gemini_api_key = os.getenv("GEMINI_API_KEY")
gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
genai_client = genai.Client(api_key=gemini_api_key, http_options={"api_version": "v1beta"})

# =====================================================================
# PYROGRAM EVENT HANDLERS
# =====================================================================

@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, message: Message) -> None:
    """
    Handles the /start command.
    Sends a comprehensive welcome guide explaining voice note Q&A and task creation layouts.
    """
    first_name = message.from_user.first_name if message.from_user else "there"
    welcome_text = (
        f"👋 Hello {first_name}!\n\n"
        "I am your task automation bot. Here is what I can do:\n\n"
        "🎙️ **Voice Note Query**\n"
        "Record and send a voice message asking a question. Example: 'Explain quantum physics simply.'\n\n"
        "📝 **ClickUp Task Creation**\n"
        "Send a text message containing task details. You must include all of the following:\n"
        "• **Task Name**\n"
        "• **Description**\n"
        "• **Status** (must be: Open, In Progress, Done, or Review)\n"
        "• **Priority** (must be: Low, Normal, High, or Urgent)\n"
        "• **Assignee**\n\n"
        "🚫 **Note:** Images, videos, files, and documents are not supported."
    )
    await message.reply_text(welcome_text)

@app.on_message(filters.voice & filters.private)
async def handle_voice(client: Client, message: Message) -> None:
    """
    Accepts, downloads, transcribes, and answers voice messages.
    """
    processing_msg = await message.reply_text("🎙️ Processing your voice message...")
    file_path = ""
    try:
        # Define local save path in the temp folder
        file_path = f"temp/voice_{message.voice.file_unique_id}.ogg"
        os.makedirs("temp", exist_ok=True)
        
        # Download the voice note media using Pyrogram's built-in downloader
        await message.download(file_name=file_path)
            
        # Transcribe audio to text (runs in a separate thread to avoid blocking Pyrogram's loop)
        transcript = await asyncio.to_thread(speech.transcribe_audio, file_path)
        logger.info(f"Audio Transcript: {transcript}")
        
        # Request conversational response from Gemini based on the transcription
        response = await asyncio.to_thread(
            genai_client.models.generate_content,
            model=gemini_model,
            contents=f"Answer the user's voice message query: {transcript}"
        )
        
        await processing_msg.delete()
        await message.reply_text(response.text.strip())
        
    except Exception as e:
        logger.error(f"Error in voice handler: {e}", exc_info=True)
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass
        await message.reply_text("⚠️ Failed to process voice note. Please try again.")
    finally:
        # Guarantee cleanup of local temp file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

@app.on_message(filters.text & ~filters.command("start") & filters.private)
async def handle_text(client: Client, message: Message) -> None:
    """
    Extracts, validates, and creates a ClickUp task from unstructured user text.
    If the text has invalid or missing fields, returns a validation message
    and instructions showing the correct format.
    """
    processing_msg = await message.reply_text("⏳ Processing your task request...")
    try:
        # Define instruction prompt asking Gemini to extract fields in JSON format
        prompt = (
            "Extract task fields from the user message. Your response must be a valid JSON object only. "
            "Do not include markdown format or backticks. Valid fields are:\n"
            "- task_name (string)\n"
            "- description (string)\n"
            "- status (must be one of: Open, In Progress, Done, Review)\n"
            "- priority (must be one of: Low, Normal, High, Urgent)\n"
            "- assignee (string)\n\n"
            "If any field cannot be found, set its value to null.\n"
            f"User message: {message.text}"
        )
        response = await asyncio.to_thread(
            genai_client.models.generate_content,
            model=gemini_model,
            contents=prompt
        )
        
        # Clean potential markdown formatting fences (e.g. ```json ... ```)
        raw_text = response.text.strip()
        raw_text = re.sub(r"^```(?:json)?\n|```$", "", raw_text, flags=re.MULTILINE).strip()
        
        # Parse the response string into a Python dictionary
        fields = json.loads(raw_text)
        logger.info(f"Parsed task fields: {fields}")
        
        # Allowed vocabularies for status and priority validation
        allowed_statuses = {"Open", "In Progress", "Done", "Review"}
        allowed_priorities = {"Low", "Normal", "High", "Urgent"}
        
        # Check validity
        is_valid = (
            fields.get("task_name") and
            fields.get("description") and
            fields.get("status") in allowed_statuses and
            fields.get("priority") in allowed_priorities and
            fields.get("assignee")
        )
        
        if not is_valid:
            await processing_msg.delete()
            error_msg = (
                "Invalid Task Message!!\n\n"
                "Please provide the details in the following format:\n"
                "Task Name: <Name of the task>\n"
                "Description: <Detailed description>\n"
                "Status: <Open, In Progress, Done, or Review>\n"
                "Priority: <Low, Normal, High, or Urgent>\n"
                "Assignee: <Name of the person>"
            )
            await message.reply_text(error_msg)
            return
            
        # Call the ClickUp service to create the task
        task = await clickup.create_task(fields)
        
        await processing_msg.delete()
        reply_text = (
            f"🚀 **Task Created Successfully!**\n\n"
            f"📝 **Task Name:** {task['name']}\n"
            f"📋 **Status:** {task['status']}\n"
            f"⚠️ **Priority:** {task['priority']}\n"
            f"👤 **Assignee:** {task['assignee']}\n\n"
            f"🔗 [View on ClickUp]({task['url']})"
        )
        await message.reply_text(reply_text)
        
    except Exception as e:
        logger.error(f"Error in text handler: {e}", exc_info=True)
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass
        error_msg = (
            "Invalid Task Message!!\n\n"
            "Please provide the details in the following format:\n"
            "Task Name: <Name of the task>\n"
            "Description: <Detailed description>\n"
            "Status: <Open, In Progress, Done, or Review>\n"
            "Priority: <Low, Normal, High, or Urgent>\n"
            "Assignee: <Name of the person>"
        )
        await message.reply_text(error_msg)

@app.on_message(filters.private & ~filters.voice & ~filters.text)
async def handle_unsupported(client: Client, message: Message) -> None:
    """
    Catches and rejects photos, videos, files, stickers, etc. with a warning.
    """
    await message.reply_text("Invalid Message type, Please send voice message or text!!")

# =====================================================================
# MAIN RUNNER
# =====================================================================

def main() -> None:
    logger.info("Bot started and running under Pyrogram Client...")
    app.run()

if __name__ == "__main__":
    main()
