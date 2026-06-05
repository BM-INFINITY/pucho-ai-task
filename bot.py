import os
import asyncio
import re
import json
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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

# Initialize the Google Gemini API Client
api_key = os.getenv("GEMINI_API_KEY")
gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
genai_client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

# =====================================================================
# BOT COMMAND HANDLERS
# =====================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /start command trigger.
    Sends a comprehensive, single-message welcome guide explaining all bot features,
    voice note Q&A instructions, task creation layouts, and format requirements.
    """
    first_name = update.effective_user.first_name if update.effective_user else "there"
    welcome_text = (
        f"👋 Hello {first_name}!\n\n"
        "I am your task automation bot. Here is what I can do:\n\n"
        "🎙️ *Voice Note Query*\n"
        "Record and send a voice message asking a question. Example: 'Explain quantum physics simply.'\n\n"
        "📝 *ClickUp Task Creation*\n"
        "Send a text message containing task details. You must include all of the following:\n"
        "• *Task Name*\n"
        "• *Description*\n"
        "• *Status* (must be: Open, In Progress, Done, or Review)\n"
        "• *Priority* (must be: Low, Normal, High, or Urgent)\n"
        "• *Assignee*\n\n"
        "*Example text format:*\n"
        "Task Name: Implement Login API\n"
        "Description: Write integration test case for Auth routes\n"
        "Status: Open\n"
        "Priority: High\n"
        "Assignee: Bhavy Modi\n\n"
        "🚫 *Note:* Images, videos, files, and documents are not supported."
    )
    # Send the response using Markdown parsing for bold text and formatting
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


# =====================================================================
# MESSAGE EVENT HANDLERS
# =====================================================================

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Accepts, downloads, transcribes, and answers voice messages.
    """
    # Notify the user that the request is processing
    processing_msg = await update.message.reply_text("🎙️ Processing your voice message...")
    file_path = ""
    try:
        # 1. Retrieve file ID and define local save path
        voice = update.message.voice
        file_path = f"temp/voice_{voice.file_id}.ogg"
        os.makedirs("temp", exist_ok=True) # Ensure local temp directory exists
        
        # Download voice file from Telegram servers to local filesystem
        tg_file = await context.bot.get_file(voice.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        with open(file_path, "wb") as f:
            f.write(file_bytes)
            
        # 2. Transcribe OGG voice note to text (run in separate thread to avoid blocking loop)
        transcript = await asyncio.to_thread(speech.transcribe_audio, file_path)
        logger.info(f"Audio Transcript: {transcript}")
        
        # 3. Request conversational response from Gemini based on the transcription
        response = await asyncio.to_thread(
            genai_client.models.generate_content,
            model=gemini_model,
            contents=f"Answer the user's voice message query: {transcript}"
        )
        
        # Delete the processing indicator and send the final response
        await processing_msg.delete()
        await update.message.reply_text(response.text.strip())
        
    except Exception as e:
        logger.error(f"Error in voice handler: {e}", exc_info=True)
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass
        await update.message.reply_text("⚠️ Failed to process voice note. Please try again.")
    finally:
        # Guarantee that the local temp audio file is always deleted
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Extracts, validates, and creates a ClickUp task from unstructured user text.
    If the text has invalid or missing fields, returns a validation message
    and instructions showing the correct format.
    """
    processing_msg = await update.message.reply_text("⏳ Processing your task request...")
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
            f"User message: {update.message.text}"
        )
        # Call Gemini in a worker thread
        response = await asyncio.to_thread(
            genai_client.models.generate_content,
            model=gemini_model,
            contents=prompt
        )
        
        # Clean potential markdown formatting fences (e.g. ```json ... ```)
        raw_text = response.text.strip()
        raw_text = re.sub(r"^```(?:json)?\n|```$", "", raw_text, flags=re.MULTILINE).strip()
        
        # Parse the string response into a Python dictionary
        fields = json.loads(raw_text)
        logger.info(f"Parsed task fields: {fields}")
        
        # Configure allowed vocabularies for status and priority validation
        allowed_statuses = {"Open", "In Progress", "Done", "Review"}
        allowed_priorities = {"Low", "Normal", "High", "Urgent"}
        
        # Validate that all required properties are present and conform to rules
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
            await update.message.reply_text(error_msg)
            return
            
        # Call the ClickUp service to create the task
        task = await clickup.create_task(fields)
        
        # Delete processing status indicator and send confirmation with task link
        await processing_msg.delete()
        reply_text = (
            f"🚀 *Task Created Successfully!*\n\n"
            f"📝 *Task Name:* {task['name']}\n"
            f"📋 *Status:* {task['status']}\n"
            f"⚠️ *Priority:* {task['priority']}\n"
            f"👤 *Assignee:* {task['assignee']}\n\n"
            f"🔗 [View on ClickUp]({task['url']})"
        )
        await update.message.reply_text(reply_text, parse_mode="Markdown")
        
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
        await update.message.reply_text(error_msg)

async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Catches and rejects photos, videos, files, stickers, etc. with a warning.
    """
    await update.message.reply_text(
        "Unsupported media type. Please send a voice message or text task description."
    )

# =====================================================================
# MAIN ENTRYPOINT
# =====================================================================

def main() -> None:
    # Build the application with the Telegram Token
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()
    
    # Register command and message event handlers in priority order
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Catch-all filter for anything that is not command, plain text, or voice
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.TEXT & ~filters.VOICE, handle_unsupported))
    
    # Start polling updates from Telegram
    logger.info("Bot started and polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
