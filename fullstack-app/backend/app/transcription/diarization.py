#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import os
import json
from typing import Any, Dict, List
import torch
import whisperx
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
from openai import OpenAI, AzureOpenAI
import openai


torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
# Load environment variables from a .env file if it exists
load_dotenv(".env")

# =================================================================
# CONFIGURATION - Tweak parameters here
# =================================================================

# --- Input/Output Files ---
if 1:
    AUDIO_PATH = "Soleus.wav"
    OUT_WORDS_JSONL = "Soleus_words_with_speakers.jsonl"
    OUT_SRT = "Soleus_segments_with_speakers.srt"
    INITIAL_PROMPT = '''Participants: Janne Kauttonen, Ali Umair Khan, Timo Rima and another Timo. Organizations: Haaga-Helia University and Soleus. Speakers are engaged in an AI and data consultation discussion.'''
else:
    AUDIO_PATH = "Soleus.wav"
    OUT_WORDS_JSONL = "Solable_words_with_speakers.jsonl"
    OUT_SRT = "Solable_segments_with_speakers.srt"
    INITIAL_PROMPT = None

# --- Diarization Settings ---
# Diarization requires a Hugging Face token with access to pyannote/speaker-diarization-3.1
DO_DIARIZATION = True
DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
MIN_SPEAKERS = 3  # e.g., 2
MAX_SPEAKERS = 6  # e.g., 4
SPEAKER_COUNT = None  # Use if you know the exact number of speakers

# --- Whisper ASR Model & Task ---
# Common choices: "large-v3" (best EN), "large-v2", "distil-large-v3", "medium", "small", "base", "tiny"
ASR_MODEL = "large-v3"
LANGUAGE = "en"  # Set to None to auto-detect language
TASK = "transcribe"  # "transcribe" or "translate"

# --- Decoding Knobs (for faster-whisper) ---
BEAM_SIZE = 15  # >1 enables beam search (better WER, slower)
#BEST_OF = 5  # For sampling-based decoding; ignored if BEAM_SIZE > 1
PATIENCE = 2.0
CONDITION_ON_PREV = True  # Default in WhisperX to reduce hallucinations
INITIAL_PROMPT = INITIAL_PROMPT or '''Speakers are engaged in an AI and data consultation discussion.'''

# --- Technical & Execution Parameters ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
if 0:
    COMPUTE_TYPE = "float32" # "float16"
    BATCH_SIZE = 8  # VRAM vs throughput trade-off
else:
    COMPUTE_TYPE = "float16" # "float16"
    BATCH_SIZE = 32  # VRAM vs throughput trade-off

CHUNK_SIZE = 30  # In seconds; how VAD-chunked segments are processed, DO NOTE REDUCE!

# --- VAD (Voice Activity Detection) ---
VAD_METHOD = "silero"
VAD_OPTIONS = {
    "vad_onset": 0.5,  # Lower if speech is being missed
    "vad_offset": 0.5,  # Lower if segment cuts are too tight
}

# --- Alignment Settings (Word Timestamps) ---
ALIGN_LANGUAGE = LANGUAGE or "en"  # Fallback to English if language is not specified
ALIGN_MODEL_NAME = None  # Let WhisperX pick the best model per language
RETURN_CHAR_ALIGNMENTS = False
ALIGN_INTERPOLATE_METHOD = "nearest"  # "nearest", "linear", or "ignore"

# --- ASR Options Dictionary (passed to faster-whisper) ---
ASR_OPTIONS = {
    "beam_size": BEAM_SIZE,
    "patience": PATIENCE,
    "condition_on_previous_text": CONDITION_ON_PREV,
    "initial_prompt": INITIAL_PROMPT,
    "suppress_tokens": None, # Keep default
}

# =================================================================
# Helper Functions
# =================================================================
def merge_srt_exact_tag(srt_text: str) -> str:
    """
    Merge consecutive SRT cues when the FIRST token in the cue text is a single tag
    of the form "[xxx]" (exact match). Tags must be identical character-for-character
    to merge. Tags like "[xxx]" != "[xxx ]" != "[ xxx ]". Cues without a leading tag
    never merge. Returns a new SRT string with renumbered indices starting at 1.
    """

    time_re = re.compile(
        r"^(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})\s*(?:.*)?$"
    )
    tag_at_start = re.compile(r"^\s*(\[[^\[\]]*\])\s*(.*)$", re.DOTALL)

    def normalize_spaces(text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        return text

    def split_blocks(s: str):
        return [p for p in re.split(r"\r?\n\r?\n+", s.strip(), flags=re.MULTILINE) if p.strip()]

    def parse_block(block: str):
        lines = [ln.rstrip("\r") for ln in block.splitlines()]
        if not lines:
            return None
        pos = 0
        if re.fullmatch(r"\d+", lines[0].strip()):
            pos = 1
        if pos >= len(lines):
            return None
        m = time_re.match(lines[pos].strip())
        if not m:
            return None
        start, end = m.group("start"), m.group("end")
        text_lines = lines[pos + 1 :] if pos + 1 < len(lines) else [""]
        text = " ".join(ln.strip() for ln in text_lines if ln.strip())
        text = normalize_spaces(text)
        tm = tag_at_start.match(text)
        if tm:
            tag = tm.group(1)            # exact as seen
            text_wo = tm.group(2).lstrip()
        else:
            tag = None
            text_wo = text
        return {"start": start, "end": end, "speaker": tag, "text": text_wo}

    # Parse cues
    cues = []
    for blk in split_blocks(srt_text):
        parsed = parse_block(blk)
        if parsed:
            cues.append(parsed)

    # Merge consecutive cues with identical (exact) speaker tag
    merged = []
    for cue in cues:
        if merged and cue["speaker"] is not None and cue["speaker"] == merged[-1]["speaker"]:
            merged[-1]["end"] = cue["end"]
            if cue["text"]:
                merged[-1]["text"] = normalize_spaces((merged[-1]["text"] + " " + cue["text"]).strip())
        else:
            merged.append(cue.copy())

    # Rebuild SRT with renumbered indices
    out_lines = []
    for i, cue in enumerate(merged, start=1):
        out_lines.append(str(i))
        out_lines.append(f"{cue['start']} --> {cue['end']}")
        txt = (cue["speaker"] + " " if cue["speaker"] else "") + (cue["text"] or "")
        out_lines.append(normalize_spaces(txt))
        out_lines.append("")
    return "\n".join(out_lines).rstrip() + "\n"

def _srt_ts(t: float) -> str:
    """Formats a timestamp for SRT files."""
    t = max(0.0, float(t))
    h = int(t // 3600)
    t -= 3600 * h
    m = int(t // 60)
    t -= 60 * m
    s = int(t)
    ms = int(round((t - s) * 1000.0))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _write_words_jsonl(words: List[Dict[str, Any]], path: str):
    """Writes word-level segments to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for w in words:
            f.write(json.dumps(w, ensure_ascii=False) + "\n")

def _write_srt_from_segments(segments: List[Dict[str, Any]], path: str):
    """Writes speaker-attributed segments to an SRT file."""
    out = ''
    with open(path, "w", encoding="utf-8") as f:
        idx = 1
        for seg in segments:
            start = _srt_ts(seg["start"])
            end = _srt_ts(seg["end"])
            spk = seg.get("speaker", "UNKNOWN")
            text = seg.get("text", "").strip()

            if not text and seg.get("words"):
                text = " ".join(w.get("text", "") for w in seg["words"]).strip()

            if text:
                f.write(f"{idx}\n{start} --> {end}\n[{spk}] {text}\n\n")
                idx += 1
                out += f"{idx}\n{start} --> {end}\n[{spk}] {text}\n\n"

    return out

def now():
    """Returns current timestamp string"""
    return datetime.now().strftime("%H:%M:%S")

use_azure = True  

# API Configuration  
def get_api_config():
    """Get API configuration for Azure or OpenAI"""
    
    if use_azure:
        return {
            'use_azure': True,
            'api_key': os.getenv("AZURE_API_KEY"),
            'azure_endpoint': "https://haagahelia-poc-gaik.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?",
            'azure_audio_endpoint': "https://haagahelia-poc-gaik.openai.azure.com/openai/deployments/whisper/audio/translations?api-version=2024-06-01",
            'api_version': "2024-12-01-preview",
            'model': 'gpt-4.1',  # Chat completion model
        }
    else:
        return {
            'use_azure': False,
            'api_key': os.getenv("OPENAI_API_KEY"),
            'model': 'gpt-4.1-2025-04-14',  # Chat completion model
        }

# =================================================================
# Transcript Enhancement and Role Classification  
# =================================================================

def post_process_transcript(transcript_text):
    """
    Post-process the transcript using Azure OpenAI or OpenAI to improve quality and assign roles
    """
    print(f"[{now()}] 🔧 Starting transcript post-processing with role classification...")
    
    # Get API configuration
    api_config = get_api_config()
    print(f"[{now()}] 📋 API configuration loaded for {'Azure OpenAI' if api_config.get('use_azure') else 'OpenAI Direct'}")
    
    # Create the prompt for transcript enhancement
    prompt = f"""
    You are an expert transcript editor specializing in AI consultation meeting transcription. Please improve the following raw transcript of an AI needs analysis and advisory meeting between AI experts and company representatives.

    Your task is to:
    1. The transcript needs to be in English. Even if some or all parts of the transcript are in any other language, translate them in English.
    2. Fix any transcription errors, inconsistencies, and unclear speech
    3. Create proper dialogue structure with clear speaker identification and role classification
    4. Format the text with appropriate paragraphs and line breaks for readability
    5. Maintain consistent naming of speakers throughout the entire transcript
    6. Ensure the conversation flows naturally between segments and timestamp blocks
    7. Preserve all timestamp markers [Timestamp: XX:XX - XX:XX] if present
    8. Retain all factual information without altering meaning or context
    9. Do not add any content that wasn't in the original transcript

    **CRITICAL: SPEAKER DIARIZATION & ROLE CLASSIFICATION**
    Perform intelligent speaker diarization that:
    - **Separates different speakers** based on voice patterns, speaking style, and context clues
    - **Classifies speakers by role** using conversation context and content analysis:

    **AI EXPERTS** are identified by content that:
    - **Offers services, recommendations, opinions, deliverables, or solutions** 
    - **Proposes implementation strategies** or technical approaches
    - **Discusses AI technologies, methodologies, or technical frameworks**
    - **Asks technical assessment questions** about company needs or capabilities
    - **Provides expert guidance** on AI implementation or best practices
    - **Uses specialized AI/ML terminology** and technical language
    - **Suggests next steps for consultation** or technical development
    - **Explains technical concepts** or methodologies to the client

    **COMPANY REPRESENTATIVES** are identified by content that:
    - **Describes their company, business operations, or organizational structure**
    - **Explains current challenges, problems, or business objectives**
    - **Provides company-specific context**, processes, or domain knowledge
    - **Shares their background or role within the company**
    - **Asks questions about services, costs, timelines, or implementation**
    - **Responds to technical questions** about their business needs
    - **Discusses company resources, constraints, or requirements**

    **CUSTOMER MANAGER** are identified by content that is **purely administrative/facilitative**:
    - **Works as a liason** between AI experts and company representatives
    - **Manages meeting flow** and transitions between speakers, although his/her involvement might be minimal
    - **Handles scheduling or administrative matters**
    - **Acts as neutral moderator** without providing technical expertise or business context
    - **IMPORTANT**: Does NOT offer services, make recommendations, or provide technical guidance

    **KEY DISTINCTION**: If someone is **offering services, providing recommendations, or giving technical advice**, they are an **AI EXPERT**, NOT a Customer Manager, regardless of how the statement is phrased.

    **SPEAKER LABELING FORMAT:**
    - Use the label "[AI Expert:]" for the dialogues uttered by AI consultation specialists
    - Use the label "[Company rep.:]" for the dialogues uttered by company representatives  
    - Use the label "[Customer Manager:]" for the dialogues uttered by customer managers
    - **IMPORTANT:** Analyze each dialogue's **content and intent** carefully. Focus on WHAT is being said rather than HOW it's said.
    - **CRITICAL RULE**: Anyone discussing deliverables, recommendations, opinions, technical solutions, or service offerings is an AI EXPERT.
    - Do not add any names with the labels. Do not use any other labels except those mentioned.
    - Maintain consistent numbering throughout the transcript

    **QUALITY ENHANCEMENT:**
    - Remove filler words (um, uh, you know) for clarity while preserving natural speech patterns
    - Fix grammatical errors and incomplete sentences
    - Ensure proper capitalization and punctuation
    - Group related statements by the same speaker into coherent paragraphs
    - Add line breaks between different speakers for visual clarity

    Return ONLY the enhanced transcript with proper speaker identification and role classification. Do not include any explanatory text or commentary.

    RAW TRANSCRIPT:
    {transcript_text}
    """
    
    # Debug: Print transcript length and first 200 characters
    print(f"[{now()}] 🔍 Raw transcript length: {len(transcript_text)} characters")
    print(f"[{now()}] 🔍 Raw transcript preview: {transcript_text[:200]}...")
    
    # Use OpenAI or Azure OpenAI based on config
    try:
        use_azure = api_config.get('use_azure', False)
        
        print(f"[{now()}] 🔧 API Config Debug:")
        print(f"  - Use Azure: {use_azure}")
        print(f"  - API Key present: {'Yes' if api_config.get('api_key') else 'No'}")
        print(f"  - Azure Endpoint: {api_config.get('azure_endpoint', 'Not set')}")
        
        if use_azure:
            # Use Azure OpenAI
            print(f"[{now()}] 🌐 Connecting to Azure OpenAI endpoint...")
            if not api_config.get('api_key') or not api_config.get('azure_endpoint'):
                print(f"[{now()}] ❌ Missing Azure OpenAI credentials!")
                return transcript_text
                
            client = AzureOpenAI(
                api_key=api_config.get('api_key'),
                azure_endpoint=api_config.get('azure_endpoint', ''),
                api_version=api_config.get('api_version', '2024-12-01-preview')
            )
            
            chat_model = api_config.get('model', 'gpt-4.1')
            print(f"[{now()}] 🤖 Sending transcript to {chat_model} for role classification...")
            print(f"[{now()}] 📏 Prompt length: {len(prompt)} characters")
            
            response = client.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role": "system", "content": "You are an expert transcript editor who improves the quality, readability, and structure of transcribed conversations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  
                # max_tokens=16000
            )
        else:
            # Use OpenAI directly
            print(f"[{now()}] 🌐 Connecting to OpenAI direct endpoint...")
            if not api_config.get('api_key'):
                print(f"[{now()}] ❌ Missing OpenAI API key!")
                return transcript_text
                
            import openai
            openai.api_key = api_config.get('api_key')
            chat_model = api_config.get('model', 'gpt-4.1-2025-04-14')
            print(f"[{now()}] 🤖 Sending transcript to {chat_model} for role classification...")
            print(f"[{now()}] 📏 Prompt length: {len(prompt)} characters")
            
            response = openai.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role": "system", "content": "You are an expert transcript editor who improves the quality, readability, and structure of transcribed conversations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  
                # max_tokens=16000
            )
        
        # Extract the enhanced transcript
        enhanced_transcript = response.choices[0].message.content
        print(f"[{now()}] 🔍 Enhanced transcript length: {len(enhanced_transcript)} characters")
        print(f"[{now()}] 🔍 Enhanced transcript preview: {enhanced_transcript[:200]}...")
        print(f"[{now()}] ✅ Transcript post-processing completed")
        return enhanced_transcript
        
    except Exception as e:
        print(f"[{now()}] ❌ Error during post-processing: {e}")
        print(f"[{now()}] ⚠️ Falling back to original transcript...")
        return transcript_text

# =================================================================
# Main Pipeline
# =================================================================

def run_diarization_transcription():
    """Executes the full transcription, alignment, and diarization pipeline."""
    print(f"CUDA available: {torch.cuda.is_available()} | Device: {DEVICE} | Compute Type: {COMPUTE_TYPE}")

    # 1) Load ASR model
    # Decoding and VAD options are passed at model load time
    model = whisperx.load_model(
        ASR_MODEL,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        language=LANGUAGE,
        task=TASK,
        asr_options=ASR_OPTIONS,
        vad_options=VAD_OPTIONS,
    )
    print("WhisperX model loaded.")

    # 2) Load audio and transcribe
    audio = whisperx.load_audio(AUDIO_PATH)
    result = model.transcribe(
        audio,
        batch_size=BATCH_SIZE,
        chunk_size=CHUNK_SIZE,
        print_progress=True,
    )
    # result: {"segments":[{start,end,text,...}], "text":"...", "language":"xx"}
    print("Transcription complete.")

    # 3) Align for word-level timestamps
    align_model, align_meta = whisperx.load_align_model(
        language_code=result["language"],
        device=DEVICE,
        model_name=ALIGN_MODEL_NAME,
    )
    aligned = whisperx.align(
        result["segments"],
        align_model,
        align_meta,
        audio,
        DEVICE,
        return_char_alignments=RETURN_CHAR_ALIGNMENTS,
        interpolate_method=ALIGN_INTERPOLATE_METHOD,
    )
    print("Alignment complete.")

    # 4) Diarize to assign speakers (optional)
    if DO_DIARIZATION:
        if not HF_TOKEN:
            raise ValueError(
                "Diarization requires a Hugging Face token. "
                "Please set HF_TOKEN in your environment."
            )
        print("Starting diarization...")
        diar_pipeline = whisperx.diarize.DiarizationPipeline(model_name=DIARIZATION_MODEL,use_auth_token=HF_TOKEN, device=DEVICE)

        diar_kwargs = {}
        if SPEAKER_COUNT is not None:
            diar_kwargs["num_speakers"] = SPEAKER_COUNT
        elif MIN_SPEAKERS is not None or MAX_SPEAKERS is not None:
            diar_kwargs["min_speakers"] = MIN_SPEAKERS if MIN_SPEAKERS is not None else 1
            diar_kwargs["max_speakers"] = MAX_SPEAKERS if MAX_SPEAKERS is not None else 10  # A reasonable default max

        diar_segments = diar_pipeline(audio, **diar_kwargs)
        fused = whisperx.assign_word_speakers(diar_segments, aligned)
        print("Diarization complete.")

        full_segments_df = pd.DataFrame(fused['segments'])
        word_segments_df = pd.DataFrame(fused['word_segments'])
    else:
        fused = aligned

    # 5) Save word-level JSONL output
    words = []
    for segment in fused.get("word_segments", []):
        for word in segment.get("words", []):
            words.append({
                "start": round(float(word.get("start", 0)), 3),
                "end": round(float(word.get("end", 0)), 3),
                "text": word.get("word", ""),
                "speaker": word.get("speaker", "UNKNOWN"),
            })
    if words:
        _write_words_jsonl(words, OUT_WORDS_JSONL)

    # 6) Save segment-level SRT with majority speaker
    # First, ensure each segment has a speaker assigned based on its words
    for seg in fused["segments"]:
        if "speaker" not in seg and seg.get("words"):
            word_speakers = [w.get("speaker", "UNKNOWN") for w in seg["words"]]
            if word_speakers:
                # Assign the most frequent speaker in the segment
                seg["speaker"] = max(set(word_speakers), key=word_speakers.count)
            else:
                seg["speaker"] = "UNKNOWN"

    srt_text = _write_srt_from_segments(fused["segments"], OUT_SRT)

    srt_text_formatted = merge_srt_exact_tag(srt_text)

    with open(OUT_SRT.replace('.srt','_JOINED.srt'), "w", encoding="utf-8") as f:
        f.write(srt_text_formatted)

    print(f"[{now()}] ✅ Diarization and transcription completed")
    print(f" - Word-level JSONL saved to: {OUT_WORDS_JSONL}")
    print(f" - Speaker SRT saved to: {OUT_SRT}")
    
    # Return the formatted transcript for post-processing
    return srt_text_formatted

# =================================================================
# Main Function
# =================================================================

def main():
    """Main function that orchestrates the entire pipeline"""
    print(f"[{now()}] 🚀 Starting enhanced diarization pipeline")
    
    # 1) Run WhisperX diarization+transcription
    raw_transcript = run_diarization_transcription()
    
    # 2) Post-process for role classification
    print(f"[{now()}] 🔄 Starting transcript enhancement phase...")
    enhanced_transcript = post_process_transcript(raw_transcript)
    
    # 3) Save final outputs
    print(f"[{now()}] 💾 Preparing to save final output files...")
    base_out = os.path.splitext(os.path.abspath(AUDIO_PATH))[0] + "_dialogue"
    
    # Save raw diarization output as text
    print(f"[{now()}] 📄 Saving raw diarization transcript...")
    with open(base_out + "_raw.txt", "w", encoding="utf-8") as f:
        f.write(raw_transcript)
    print(f"[{now()}] ✅ Saved raw diarization to {base_out}_raw.txt")
    
    # Save enhanced transcript as text  
    print(f"[{now()}] 📄 Saving enhanced transcript with role classification...")
    with open(base_out + "_enhanced.txt", "w", encoding="utf-8") as f:
        f.write(enhanced_transcript)
    print(f"[{now()}] ✅ Saved enhanced transcript to {base_out}_enhanced.txt")
    
    print(f"[{now()}] 🏁 Pipeline completed successfully! Generated enhanced transcript with role classification.")

if __name__ == "__main__":
    main()