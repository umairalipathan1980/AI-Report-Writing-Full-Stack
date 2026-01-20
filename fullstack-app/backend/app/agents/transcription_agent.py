import os
import subprocess
from typing import Any, Dict

from pydantic import BaseModel

from app.transcription.transcriber import process_audio_transcription


class TranscriptionResult(BaseModel):
    """Output model for transcription results"""
    transcript: str
    transcript_path: str
    status: str = "completed"


def transcribe_audio_file(file_path: str, output_dir: str, api_config: Dict[str, Any], compress_audio: bool = True) -> TranscriptionResult:
    """
    Tool function to transcribe audio/video files.
    
    Args:
        file_path: Path to the audio/video file
        output_dir: Directory to save the transcript
        api_config: API configuration dictionary
        
    Returns:
        TranscriptionResult: Results with transcript text and file path
    """
    if not file_path or not output_dir:
        raise ValueError("Missing required inputs: file_path and output_dir")
    
    print(f"Transcribing file: {os.path.basename(file_path)}")
    
    # File type detection will be handled by the transcriber function
    # Process the transcription using the existing function
    transcript, transcript_path = process_audio_transcription(
        file_path, 
        output_dir, 
        api_config,
        compress_audio
    )
    
    print(f"Transcription completed, saved to: {os.path.basename(transcript_path)}")
    
    return TranscriptionResult(
        transcript=transcript,
        transcript_path=transcript_path
    )
