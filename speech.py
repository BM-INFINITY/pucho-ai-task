import os
from google import genai
from google.genai import types

def transcribe_audio(file_path: str) -> str:
    """
    Transcribes a local OGG/Opus voice note using the Google Gemini API.
    
    Parameters:
      file_path (str): The local path to the downloaded Telegram voice note file.
      
    Returns:
      str: The verbatim text transcription returned by Gemini.
    """
    # Load API token and model directly from environment variables
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    
    # Initialize the Google GenAI SDK Client using the v1beta API version
    # (v1beta supports sending raw audio bytes directly inside the request)
    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1beta"},
    )
    
    # Read the raw binary content of the voice file
    with open(file_path, "rb") as f:
        audio_bytes = f.read()
        
    # Transcription prompt instruction for the model
    prompt = (
        "Listen to the audio carefully and transcribe everything that is spoken "
        "verbatim. Return ONLY the transcription text — no labels, no timestamps, "
        "no commentary. If the audio is silent or unintelligible, return exactly: "
        "[Unintelligible audio]"
    )
    
    # Send the transcription request containing both the instruction text and audio data
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(text=prompt),
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="audio/ogg",
                            data=audio_bytes,
                        )
                    ),
                ],
            )
        ]
    )
    
    # Check if the model returned content
    if not response or not response.text:
        raise RuntimeError("Empty response from Gemini transcription API.")
        
    # Return the clean transcription text
    return response.text.strip()
