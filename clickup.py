import os
import httpx

# =====================================================================
# CLICKUP STATIC CONFIGURATION MAPS
# =====================================================================

# 1. Priority Map
# ClickUp API requires integer values for priority levels:
# 1 = Urgent (Red), 2 = High (Yellow), 3 = Normal (Blue), 4 = Low (Grey)
# This maps the text extracted by the Gemini AI to the correct integer.
PRIORITY_MAP = {
    "urgent": 1,
    "high": 2,
    "normal": 3,
    "low": 4
}

# 2. Status Map
# Translates the AI-extracted status string (e.g., "Done" or "Open")
# into the exact lowercase status name supported by the target ClickUp List.
STATUS_MAP = {
    "open": "to do",
    "in progress": "in progress",
    "done": "complete",
    "review": "to do"  # Default to 'to do' as a safe fallback for review status
}

async def create_task(task_fields: dict) -> dict:
    """
    Creates a new ClickUp task under the configured List ID.
    
    Parameters:
      task_fields (dict): Extracted task fields containing:
        - task_name
        - description
        - status
        - priority
        - assignee
        
    Returns:
      dict: Summary of the created task including the ClickUp web URL.
    """
    # Load credentials directly from environment variables (populated from .env)
    api_token = os.getenv("CLICKUP_API_TOKEN")
    list_id = os.getenv("CLICKUP_LIST_ID")
    
    # Configure the standard ClickUp API v2 request headers
    headers = {
        "Authorization": api_token,
        "Content-Type": "application/json"
    }
    
    # 1. Map status string to valid ClickUp List status name
    extracted_status = task_fields.get("status", "Open").lower().strip()
    status = STATUS_MAP.get(extracted_status, "to do")
    
    # 2. Map priority name to ClickUp priority integer code
    extracted_priority = task_fields.get("priority", "Normal").lower().strip()
    priority = PRIORITY_MAP.get(extracted_priority, 3)
    
    # Append the requested assignee to the task description instead of assigning a ClickUp user profile ID
    description = task_fields.get("description", "")
    extracted_assignee = task_fields.get("assignee", "").strip()
    if extracted_assignee:
        description += f"\n\n[Assignee: {extracted_assignee}]"
        
    # Build the HTTP request body payload
    payload = {
        "name": task_fields.get("task_name"),
        "description": description,
        "status": status,
        "priority": priority
    }
    
    # ClickUp v2 Create Task API URL
    url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
    
    # Perform the asynchronous HTTP POST request
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload, timeout=15.0)
        response.raise_for_status() # Raise an exception if HTTP code is not 200/OK
        data = response.json()
        
    # Return details used by the Telegram bot to reply to the user
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "status": status,
        "priority": task_fields.get("priority"),
        "assignee": extracted_assignee if extracted_assignee else "None",
        "url": data.get("url")
    }
