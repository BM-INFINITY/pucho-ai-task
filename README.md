# Pucho AI — Telegram Task Automation Bot

A Telegram bot built as part of an AI Automation Internship Assessment. It handles voice message queries using speech-to-text and Gemini AI, and creates tasks in ClickUp from structured text messages.

---

## Objective

The assessment required building a Telegram bot that can:

- Accept voice messages, transcribe them, and return an AI-generated answer.
- Accept text messages containing task details, validate them, and create a task in ClickUp via its REST API.
- Reject unsupported media types (images, videos, files, stickers) with a clear error message.

---

## Features

- **Voice message handling** — Accepts OGG voice notes sent via Telegram.
- **Speech-to-text conversion** — Transcribes voice audio using the Gemini API (inline audio, no separate upload step).
- **AI-powered response generation** — Sends the transcription to Gemini and returns an answer to the user.
- **Text-based task creation** — Parses free-form text messages to extract task fields using Gemini.
- **ClickUp integration** — Creates tasks in a configured ClickUp List via the ClickUp v2 REST API.
- **Validation handling** — Validates all five required task fields before attempting to create a task; returns a formatted error message if validation fails.
- **Unsupported media handling** — Catches photos, videos, files, stickers, and other non-supported types and replies with an error.

---

## Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.x | Primary language |
| Pyrogram `>=2.0.0` | Telegram MTProto client (bot mode) |
| TgCrypto `>=1.2.5` | Cryptography layer required by Pyrogram |
| Google GenAI SDK (`google-genai >= 1.0.0`) | Gemini API — transcription and text generation |
| HTTPX `>=0.27.0` | Async HTTP client for ClickUp API calls |
| python-dotenv `==1.0.1` | Loads environment variables from `.env` |

---

## Project Structure

```
pucho-telegram-bot/
├── bot.py              # Main entry point. Defines all Pyrogram event handlers.
├── speech.py           # Handles audio transcription using the Gemini API.
├── clickup.py          # Handles task creation via the ClickUp v2 REST API.
├── requirements.txt    # Python package dependencies.
├── Procfile            # Process definition for Heroku deployment (worker: python bot.py).
├── .env.example        # Template for required environment variables.
├── .env                # Actual environment config (not committed to version control).
├── logs/               # Log output directory.
└── temp/               # Temporary directory for downloaded voice files (auto-created at runtime).
```

### File Descriptions

- **`bot.py`** — Initializes the Pyrogram `Client`, configures the Gemini `genai.Client`, and registers four event handlers: `/start` command, voice messages, text messages, and unsupported media. All async I/O is handled here.
- **`speech.py`** — Reads a local `.ogg` file as raw bytes and sends it inline to the Gemini API along with a transcription prompt. Returns the plain text transcript.
- **`clickup.py`** — Maps extracted status and priority strings to ClickUp-compatible values, builds the JSON payload, and performs an async POST request to `api.clickup.com/api/v2/list/{list_id}/task`. Since ClickUp requires numeric user IDs for assignees, the assignee name is appended to the task description instead.
- **`requirements.txt`** — Lists all required packages with minimum version constraints.
- **`Procfile`** — Tells Heroku to run the bot as a background worker process.

---

## Workflow

### Voice Message Flow

```
User sends a voice message
  → Bot downloads the .ogg file to the temp/ directory
  → speech.py reads the file bytes and sends them to the Gemini API
  → Gemini returns a text transcript
  → bot.py sends the transcript back to Gemini as a Q&A query
  → Gemini returns an answer
  → Bot replies to the user with the answer
  → Temp file is deleted in the finally block
```

### Text Message Flow

```
User sends a text message (not a /start command)
  → bot.py sends the raw message to Gemini with a structured extraction prompt
  → Gemini returns a JSON object with: task_name, description, status, priority, assignee
  → bot.py validates all five fields against allowed values
  → If invalid → Bot replies with the required format and exits
  → If valid   → clickup.py creates the task via ClickUp API
  → Bot replies with task name, status, priority, assignee, and a ClickUp URL
```

### Unsupported Media Flow

```
User sends a photo, video, file, sticker, or any other media type
  → handle_unsupported handler catches it
  → Bot replies: "Invalid Message type, Please send voice message or text!!"
```

---

## Setup Instructions

### Clone Project

```bash
git clone https://github.com/your-username/pucho-telegram-bot.git
cd pucho-telegram-bot
```

### Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set the following variables:

```env
# Telegram — get from https://my.telegram.org and @BotFather
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE
TELEGRAM_API_ID=YOUR_TELEGRAM_API_ID_HERE
TELEGRAM_API_HASH=YOUR_TELEGRAM_API_HASH_HERE

# Google Gemini — get from https://aistudio.google.com/app/apikey
GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE

# ClickUp — get from ClickUp → Settings → Apps → API Token
CLICKUP_API_TOKEN=YOUR_CLICKUP_API_TOKEN_HERE

# ClickUp List ID — visible in the URL when viewing a List
CLICKUP_LIST_ID=YOUR_CLICKUP_LIST_ID_HERE
```

**Where to get each value:**

| Variable | Source |
|---|---|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `TELEGRAM_API_ID` | [https://my.telegram.org](https://my.telegram.org) → API Development Tools |
| `TELEGRAM_API_HASH` | Same as above |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `CLICKUP_API_TOKEN` | ClickUp → Settings → Apps → API Token |
| `CLICKUP_LIST_ID` | Found in the ClickUp List URL: `.../v/l/6-{LIST_ID}-1` |

### Run Project

```bash
python bot.py
```

---

## Example Usage

### Voice Message Example

**User sends a voice note saying:**
> "Give me a summary about Tally software"

**Bot replies:**
> Tally is an accounting and business management software widely used by small and medium-sized businesses in India. It handles tasks like bookkeeping, GST filing, payroll, inventory, and invoicing. It is known for being relatively easy to use without requiring advanced accounting knowledge.

---

### Valid Task Example

**User sends:**
```
Task Name: Update API documentation
Description: Review and update all endpoint docs for the v2 release
Status: In Progress
Priority: High
Assignee: Rahul Shah
```

**Bot replies:**
```
🚀 Task Created Successfully!

📝 Task Name: Update API documentation
📋 Status: in progress
⚠️ Priority: High
👤 Assignee: Rahul Shah

🔗 View on ClickUp → https://app.clickup.com/t/...
```

The bot also supports a label-free line-by-line format:
```
Update API documentation
Review and update all endpoint docs for the v2 release
In Progress
High
Rahul Shah
```

---

### Invalid Task Example

**User sends:**
```
Fix the login bug
High
```

**Bot replies:**
```
Invalid Task Message!!

Please provide the details in the following format:
Task Name: <Name of the task>
Description: <Detailed description>
Status: <Open, In Progress, Done, or Review>
Priority: <Low, Normal, High, or Urgent>
Assignee: <Name of the person>
```

---

### Unsupported Media Example

**User sends an image or video.**

**Bot replies:**
```
Invalid Message type, Please send voice message or text!!
```

---

## Error Handling

- **Missing or invalid task fields** — If any of the five required fields (task name, description, status, priority, assignee) is missing or has an unrecognized value, the bot rejects the request and shows the correct format.
- **Invalid status/priority values** — Only `Open`, `In Progress`, `Done`, `Review` are accepted for status, and only `Low`, `Normal`, `High`, `Urgent` for priority. The check is case-insensitive (values are normalized to title case before validation).
- **Voice transcription failure** — If the Gemini API returns an empty response or the file cannot be processed, the bot replies with a generic failure message and logs the error.
- **ClickUp API errors** — If the HTTP request to ClickUp fails (e.g., invalid token, wrong list ID), `response.raise_for_status()` raises an exception which is caught by the outer try/except and returns an error message to the user.
- **Unsupported media types** — A dedicated handler catches all non-voice, non-text private messages and replies with an appropriate message.
- **Startup validation** — The bot checks that `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` are set before starting. If they are missing or still contain placeholder values, it logs an error and exits immediately.
- **Temp file cleanup** — The voice file downloaded to the `temp/` directory is always deleted in the `finally` block of the voice handler, even if an error occurs during processing.

---

## Design Decisions

**Why Pyrogram?**
Pyrogram uses the Telegram MTProto protocol directly, which gives more control over how the bot connects compared to the Bot API wrapper approach used by `python-telegram-bot`. It also has clean async support and straightforward media download methods.

**Why Gemini?**
Gemini was chosen because its API supports sending raw audio bytes inline within the request payload (using `inline_data`), which means no separate file upload step is needed for transcription. It also handles both transcription and text generation, so only one external AI service is needed for the entire bot.

**Why ClickUp API?**
The assessment specifically required ClickUp integration. The ClickUp v2 REST API is straightforward to use with a simple API token and a list ID, without needing OAuth. Since the API requires numeric user IDs to assign tasks, the assignee name is written into the task description as a note instead, which is a practical workaround given the scope of this project.

---

## Limitations

- Requires an active internet connection. The bot relies entirely on external APIs (Telegram, Gemini, ClickUp).
- The assignee field in a ClickUp task is set via a description note (`[Assignee: Name]`) rather than an actual ClickUp user assignment, because the API requires a numeric ClickUp user ID and there is no user lookup implemented.
- The bot only works in private (one-on-one) chats. Group chat messages are not handled.
- The Gemini model used for extraction (`gemini-3.1-flash-lite` by default) occasionally returns malformed JSON; the bot handles this with a regex cleanup step, but edge cases may still cause it to fall back to the error response.
- No persistent storage or task history — the bot does not store any message history or previously created tasks locally.
- Voice notes must be sent as Telegram voice messages (`.ogg` format). Audio files sent as documents are not handled.

---

## Assessment Requirements Coverage

| Requirement | Status |
|---|---|
| Voice Message Handling | ✅ |
| Speech-to-Text Conversion | ✅ |
| AI-Powered Response Generation | ✅ |
| Task Field Extraction from Text | ✅ |
| ClickUp Task Creation | ✅ |
| Input Validation with Error Messages | ✅ |
| Unsupported Media Type Handling | ✅ |

---

## Author

**Name:** Bhavy Modi

**Role:** AI Automation Internship Assessment Submission
