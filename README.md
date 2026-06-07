# Pucho AI — Telegram Bot (AI Automation Internship Assessment)

This is my submission for the AI Automation Internship Assessment. The task was to build a Telegram bot that handles voice queries using AI and creates tasks in ClickUp from text messages.

---

## What the bot does

There are three things this bot can handle:

1. **Voice messages** — You send a voice note, it transcribes it using Gemini and replies with an answer.
2. **Task messages** — You send task details in text, it extracts the fields, validates them, and creates a task in ClickUp.
3. **Everything else** — Photos, videos, files, stickers — it just tells you it doesn't support those.

---

## Tech stack

- **Python** — main language
- **Pyrogram** — for connecting to Telegram (MTProto, not the Bot API wrapper)
- **google-genai** — Gemini API for both transcription and text generation
- **httpx** — async HTTP client for ClickUp API calls
- **python-dotenv** — loads the `.env` config


---

## Project structure

```
pucho-telegram-bot/
├── bot.py           # All Pyrogram handlers — start command, voice, text, unsupported
├── speech.py        # Sends OGG audio bytes to Gemini and returns transcription
├── clickup.py       # Builds payload and calls ClickUp v2 API to create the task
├── requirements.txt
├── Procfile         # For Heroku: worker: python bot.py
├── .env.example     # Template for environment variables
└── temp/            # Auto-created at runtime for downloaded voice files
```

---

## How each flow works

### Voice message

1. User sends a voice note
2. Bot downloads the `.ogg` file to `temp/`
3. `speech.py` reads the raw bytes and sends them inline to Gemini with a transcription prompt
4. The transcript goes back to Gemini as a Q&A query
5. Bot replies with the answer
6. Temp file is deleted in the `finally` block regardless of whether it succeeded or failed

### Text task creation

1. User sends task details as plain text
2. Bot sends the message to Gemini with a prompt asking for JSON output containing: `task_name`, `description`, `status`, `priority`, `assignee`
3. The JSON is parsed and validated — status must be one of `Open, In Progress, Done, Review` and priority must be one of `Low, Normal, High, Urgent`
4. If anything is missing or wrong → error message with the correct format shown
5. If valid → `clickup.py` maps the values (e.g., `"Urgent"` → `1`, `"Open"` → `"to do"`) and creates the task via `POST /api/v2/list/{list_id}/task`
6. Bot replies with task name, status, priority, assignee name, and a direct ClickUp link

### Unsupported media

Bot replies: `"Invalid Message type, Please send voice message or text!!"`

---

## Setup

### 1. Clone and set up environment

```bash
git clone https://github.com/BM-INFINITY/pucho-ai-task.git
cd pucho-ai-task

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Fill in these values:

```env
TELEGRAM_BOT_TOKEN=your_bot_token        # from @BotFather
TELEGRAM_API_ID=your_api_id              # from https://my.telegram.org
TELEGRAM_API_HASH=your_api_hash          # from https://my.telegram.org
GEMINI_API_KEY=your_gemini_key           # from https://aistudio.google.com/app/apikey
CLICKUP_API_TOKEN=your_clickup_token     # ClickUp → Settings → Apps → API Token
CLICKUP_LIST_ID=your_list_id             # visible in the ClickUp List URL
```

### 3. Run

```bash
python bot.py
```

---

## Example inputs and outputs

**Voice note:**
> User says: "Give me a summary of Tally software"
>
> Bot replies with a short text explanation of what Tally is.

**Valid task message:**
```
Task Name: Fix login bug
Description: Users are unable to login with Google OAuth on mobile
Status: In Progress
Priority: High
Assignee: Rahul Shah
```
Bot replies with task details and a ClickUp link.

The bot also accepts the same info without labels — just values on separate lines, in that order.

**Invalid task (missing fields):**
```
Fix the login bug
High
```
Bot replies:
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

## A few things worth noting

**Assignee handling** — ClickUp's API requires a numeric user ID to assign tasks. Since I don't have a user directory to look up IDs from, the assignee name is appended to the task description as `[Assignee: Name]`. It's a workaround but it works within the scope of this project.

**JSON cleanup** — Gemini sometimes wraps the JSON in markdown code fences (` ```json ``` `). There's a regex step that strips those out before parsing, to avoid `json.loads` failures.

**Blocking calls in async context** — Gemini's SDK calls and audio file reads are synchronous. I wrapped them with `asyncio.to_thread()` so they don't block Pyrogram's event loop.

**Startup check** — The bot validates `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` at startup and exits immediately with a clear message if they're missing or still set to placeholders.

---

## Limitations

- Assignee is a name in the description, not an actual ClickUp user assignment
- Only works in private chats — no group support
- Voice files sent as audio documents (not voice notes) are not handled
- No conversation history or stored task data — everything is stateless

---

## Requirements coverage

| Requirement | Implemented |
|---|---|
| Voice message handling | ✅ |
| Speech-to-text | ✅ |
| AI response generation | ✅ |
| Task field extraction | ✅ |
| ClickUp task creation | ✅ |
| Validation with error messages | ✅ |
| Unsupported media handling | ✅ |

---

**Submitted by:** Bhavy Modi — AI Automation Internship Assessment
