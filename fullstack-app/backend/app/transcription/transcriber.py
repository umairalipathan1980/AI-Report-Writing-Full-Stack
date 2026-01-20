import os
import openai
from openai import AzureOpenAI
from pathlib import Path
import subprocess
import sys
import shutil
import math
import hashlib
from pydub import AudioSegment
import tempfile
from datetime import datetime
import time

def process_audio_transcription(file_path, output_dir, api_config, compress_audio=True):
    """
    Transcribe an audio or video file using OpenAI API or Azure OpenAI API
    
    Args:
        file_path: Path to the audio or video file
        output_dir: Directory to save the transcript
        api_config: Dictionary containing API configuration including API keys and model names
        
    Returns:
        tuple: (transcript text, transcript path)
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate a unique ID for this file based on name and timestamp
    file_name = os.path.basename(file_path)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = hashlib.md5(f"{file_name}_{timestamp}".encode()).hexdigest()[:10]
    
    # Use ffprobe to detect if file contains video streams
    audio_path = file_path
    extracted_audio = False
    is_video = False
    
    try:
        # Use ffprobe to check if file has video streams
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-select_streams', 'v:0', 
            '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', file_path
        ], capture_output=True, text=True)
        
        # If video stream found, it's a video file
        is_video = result.stdout.strip() != ""
        
    except (subprocess.SubprocessError, FileNotFoundError):
        # If ffprobe fails, fall back to extension check
        file_extension = os.path.splitext(file_path)[1].lower()
        is_video = file_extension in ['.mp4', '.avi', '.mov', '.mkv', '.flv']
    
    # Calculate file size in MB
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    compressed = False
    
    # Compress audio file if it's not a video AND size > 25MB AND compression is enabled
    if not is_video and file_size_mb > 25 and compress_audio:
        print(f"Audio file detected ({file_size_mb:.1f}MB). Compression option selected - compressing to 32k bitrate...")
        compressed_audio_path = os.path.join(output_dir, f"{unique_id}_compressed_audio.ogg")
        try:
            # Try to find ffmpeg - it might be in the path or need to be specified
            try:
                # Try running ffmpeg with a simple command to check if it's available
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                ffmpeg_available = True
                ffmpeg_path = 'ffmpeg'
            except (subprocess.SubprocessError, FileNotFoundError):
                # Check for common ffmpeg locations
                possible_paths = [
                    'ffmpeg',
                    '/usr/bin/ffmpeg',
                    '/usr/local/bin/ffmpeg',
                    'C:\\ffmpeg\\bin\\ffmpeg.exe',
                    'ffmpeg-2025-03-10-git-87e5da9067-essentials_build\\ffmpeg-2025-03-10-git-87e5da9067-essentials_build\\bin\\ffmpeg.exe'
                ]
                
                ffmpeg_available = False
                ffmpeg_path = None
                
                for path in possible_paths:
                    try:
                        subprocess.run([path, '-version'], capture_output=True, check=True)
                        ffmpeg_available = True
                        ffmpeg_path = path
                        break
                    except (subprocess.SubprocessError, FileNotFoundError):
                        continue
            
            if ffmpeg_available:
                print("ffmpeg found. Compressing audio...")
                # Compress audio using ffmpeg with specified parameters
                subprocess.run([
                    ffmpeg_path, '-i', file_path, '-vn', '-map_metadata', '-1', '-ac', '1',
                    '-c:a', 'libopus', '-b:a', '32k', '-application', 'voip',
                    compressed_audio_path, '-y'
                ], check=True, capture_output=True)
                
                audio_path = compressed_audio_path
                extracted_audio = True
                print(f"Audio compression completed. Using compressed file: {audio_path}")
                compressed = True
            else:
                print("FFmpeg not found. Audio compression disabled - processing original audio file.")
        except Exception as e:
            print(f"Error compressing audio: {e}")
            print("Audio compression failed - processing original audio file.")
    elif not is_video and file_size_mb > 25 and not compress_audio:
        print(f"Audio file detected ({file_size_mb:.1f}MB). Compression option disabled - processing original file.")
    
    if not is_video and file_size_mb < 25 and compress_audio:
        print("File size is less than 25MB. Proceeding without compression...")

    if is_video:
        print("Video file detected. Audio will be extracted for transcription.")
        # Extract audio from video file
        extracted_audio_path = os.path.join(output_dir, f"{unique_id}_audio.mp3")
        try:
            # Try to find ffmpeg - it might be in the path or need to be specified
            try:
                # Try running ffmpeg with a simple command to check if it's available
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                ffmpeg_available = True
                ffmpeg_path = 'ffmpeg'
            except (subprocess.SubprocessError, FileNotFoundError):
                # Check for common ffmpeg locations
                possible_paths = [
                    'ffmpeg',
                    '/usr/bin/ffmpeg',
                    '/usr/local/bin/ffmpeg',
                    'C:\\ffmpeg\\bin\\ffmpeg.exe',
                    'ffmpeg-2025-03-10-git-87e5da9067-essentials_build\\ffmpeg-2025-03-10-git-87e5da9067-essentials_build\\bin\\ffmpeg.exe'
                ]
                
                ffmpeg_available = False
                ffmpeg_path = None
                
                for path in possible_paths:
                    try:
                        subprocess.run([path, '-version'], capture_output=True, check=True)
                        ffmpeg_available = True
                        ffmpeg_path = path
                        break
                    except (subprocess.SubprocessError, FileNotFoundError):
                        continue
            
            if ffmpeg_available:
                # Extract audio using ffmpeg
                subprocess.run([
                    ffmpeg_path, '-i', file_path, '-q:a', '0', '-map', 'a', 
                    extracted_audio_path, '-y'
                ], check=True, capture_output=True)
                
                audio_path = extracted_audio_path
                extracted_audio = True
                print(f"Extracted audio to {audio_path}")
            else:
                print("FFmpeg not found. Will try to process the video directly.")
        except Exception as e:
            print(f"Error extracting audio from video: {e}")
            # Continue with original file and let OpenAI handle it
            print("Will try to process the video directly.")

    # Set output file path for transcript
    transcript_path = os.path.join(output_dir, f"{unique_id}_transcript.txt")
    raw_transcript_path = os.path.join(output_dir, f"{unique_id}_raw_transcript.txt")
    
    # Get API configuration parameters
    use_azure = api_config.get('use_azure', False)
    transcription_model = api_config.get('transcription_model', 'whisper-1')
    api_key = api_config.get('api_key')
    
    # Get file size and determine if chunking is needed
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)

    audio = AudioSegment.from_file(audio_path)
    duration_seconds = len(audio) / 1000  # pydub uses milliseconds
    duration_hours = duration_seconds / 3600  # Convert to hours
    # Determine if chunking is needed based on file size and duration
    max_size_mb = 25  # 25MB chunk size
    max_duration_seconds = 1500  # 25 minutes (1500 seconds)
    
    needs_chunking = (file_size_mb > max_size_mb) # chunking is needed if the file size is greater than 25MB
    
    try:
        # Handle transcript generation with or without chunking
        if needs_chunking and audio is not None:
            # Split and transcribe in chunks with context preservation
            raw_transcript = split_and_transcribe_with_context(audio_path, api_config, max_size_mb, max_duration_seconds, audio)
        else:
            print("Transcribing the whole audio file in one shot (file size <25MB)...")
            
            # Transcribe directly based on API selection
            if use_azure:
                print("Using MS Azure endpoint for transcription")
            else:
                print("Using OpenAI direct endpoint for transcription")
                
            with open(audio_path, "rb") as audio_file:
                if use_azure:
                    # Use Azure OpenAI for transcription
                    client = AzureOpenAI(
                        api_key=api_key,
                        # azure_endpoint=api_config.get('azure_endpoint', '').replace("chat/completions?", ""),
                        azure_endpoint=api_config.get('azure_endpoint', ''),
                        # api_version=api_config.get('api_version', '2024-12-01-preview')
                        api_version=api_config.get('api_version', '2025-03-01-preview'),
                    )
                    
                    # Use the specific audio endpoint if provided, otherwise construct from the main endpoint
                    audio_endpoint_url = api_config.get('azure_audio_endpoint', 
                                        api_config.get('azure_endpoint', '').replace("chat/completions?", "audio/transcriptions?"))
                    
                    print(f"Using Azure endpoint for transcription: {audio_endpoint_url}")
                    
                    # Create a customized client for audio transcription with the correct endpoint
                    from openai import AzureOpenAI as AzureAudioClient
                    audio_client = AzureAudioClient(
                        api_key=api_key,
                        azure_endpoint=audio_endpoint_url.split('/openai/')[0],  # Base URL part
                        api_version=api_config.get('api_version', '2024-12-01-preview')
                    )
                    
                    # Now use the correct client and deployment name
                    transcript_response = audio_client.audio.transcriptions.create(
                        model=transcription_model,
                        file=audio_file,
                        prompt='Extract transcript in English with proper dialogue structure. The following conversation is an AI need analysis and advisory meeting between AI advisors and company representatives. Under no circumstances create transcript in any other language than English. '
                    )
                else:
                    # Use OpenAI directly
                    openai.api_key = api_key
                    transcript_response = openai.audio.transcriptions.create(
                        model=transcription_model,
                        file=audio_file,
                        prompt='Extract transcript in English with proper dialogue structure. The following conversation is an AI need analysis and advisory meeting between AI advisors and company representatives. Under no circumstances create transcript in any other language than English.'
                    )

                
                raw_transcript = transcript_response.text
        
        # Save raw transcript to file for reference
        with open(raw_transcript_path, "w", encoding="utf-8") as f:
            f.write(raw_transcript)

        print("Raw transcription complete. Post-processing transcript for improved quality...")
        
        # Post-process the transcript using GPT-4.1 for improved quality and structure
        enhanced_transcript = post_process_transcript(raw_transcript, api_config)
        
        # Save enhanced transcript to file
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(enhanced_transcript)

    except Exception as e:
        print(f"Error during transcription: {e}")
        raise
    finally:
        # Clean up extracted audio file if applicable - COMMENTED OUT (keeping extracted audio files)
        if extracted_audio and 'extracted_audio_path' in locals() and os.path.exists(extracted_audio_path):
            try:
                os.remove(extracted_audio_path)  
            except Exception as e:
                print(f"Error with temporary audio file: {e}")
    
    return enhanced_transcript, transcript_path

def post_process_transcript(raw_transcript, api_config):
    """
    Post-process the raw transcript using GPT-4.1 to improve quality and structure
    
    Args:
        raw_transcript: The raw transcript text to enhance
        api_config: Dictionary containing API configuration
        
    Returns:
        str: Enhanced transcript with proper formatting and structure
    """
    model_name = api_config.get('model', 'GPT model')
    print(f"Enhancing transcript quality with {model_name}...")
    
    # Create prompt for transcript enhancement with advanced speaker diarization
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
    - If a dialogue's label/speaker cannot be determined, label it as 'UNKNOWN'.
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
    {raw_transcript}
    """


    ###Legacy prompt for transcript enhancement
    # prompt = f"""
    # You are an expert transcript editor specializing in AI consultation meeting transcription. Please improve the following raw transcript of an AI needs analysis and advisory meeting between AI experts and company representatives.
    
    # Your task is to:
    # 1. The transcript needs to be in English. Even if some or all parts of the transcript are in any other language, translate them in English.
    # 2. Fix any transcription errors, inconsistencies, and unclear speech
    # 3. Create proper dialogue structure with clear speaker identification and role classification
    # 4. Format the text with appropriate paragraphs and line breaks for readability
    # 5. Maintain consistent naming of speakers throughout the entire transcript
    # 6. Ensure the conversation flows naturally between segments and timestamp blocks
    # 7. Preserve all timestamp markers [Timestamp: XX:XX - XX:XX] if present
    # 8. Retain all factual information without altering meaning or context
    # 9. Do not add any content that wasn't in the original transcript

    # **CRITICAL: SPEAKER DIARIZATION & ROLE CLASSIFICATION**
    # Perform intelligent speaker diarization that:
    # - **Separates different speakers** based on voice patterns, speaking style, and context clues
    # - **Classifies speakers by role** using conversation context and content analysis:
      
    # **AI EXPERTS** typically:
    # - Ask probing questions about the company's AI needs, technical requirements, or business goals
    # - Provide recommendations, suggestions, or expert advice
    # - Discuss AI technologies, methodologies, or implementation strategies
    # - Use technical terminology related to AI, machine learning, or data science
    # - Guide the conversation toward assessment and solution design
    
    # **COMPANY REPRESENTATIVES** typically:
    # - Answer questions about their company, business, or current situation
    # - Describe their problems, needs, or objectives
    # - Share company-specific information, processes, or challenges
    # - Ask questions about services, costs, or implementation
    # - Provide business context and domain expertise

    # **CUSTOMER MANAGER** typically:
    # - Works as a liason between AI experts and company representatives
    # - Plays a neutral role to faciliate the meeting
    # - Plays an administrative role in scheduling follow up meetings and the next course of actions. 
    
    # **SPEAKER LABELING FORMAT:**
    # - Use the label "[AI Expert:]" for the dialogues uttered by AI consultation specialists
    # - Use the label "[Company rep.:]" for the dialogues uttered by company representatives
    # - Use the label "[Customer Manager:]" for the dialogues uttered by customer managers
    # - If a dialogue's label/speaker cannot be determined, label it as 'UNKNOWN'.
    # - **IMPORTANT:** Analyze each dialogue carefully to determine whether it has been uttered by a company representative, AI expert, or customer manager. The control of conversation may not always transfer from an AI expert's question to company representative. It could be from one AI expert to another. The same goes for company representatives. 
    # - Do not add any names with the labels. Do not use any other labels except those mentioned.
    # - Maintain consistent numbering throughout the transcript
    
    # **QUALITY ENHANCEMENT:**
    # - Remove filler words (um, uh, you know) for clarity while preserving natural speech patterns
    # - Fix grammatical errors and incomplete sentences
    # - Ensure proper capitalization and punctuation
    # - Group related statements by the same speaker into coherent paragraphs
    # - Add line breaks between different speakers for visual clarity
    
    # Return ONLY the enhanced transcript with proper speaker identification and role classification. Do not include any explanatory text or commentary.
    
    # RAW TRANSCRIPT:
    # {raw_transcript}
    # """

    
    # Use OpenAI or Azure OpenAI based on config
    try:
        use_azure = api_config.get('use_azure', False)
        
        if use_azure:
            # Use Azure OpenAI
            client = AzureOpenAI(
                api_key=api_config.get('api_key'),
                azure_endpoint=api_config.get('azure_endpoint', ''),
                api_version=api_config.get('api_version', '2024-12-01-preview')
            )
            
            chat_model = api_config.get('model', 'gpt-4.1')
            response = client.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role": "system", "content": "You are an expert transcript editor who improves the quality, readability, and structure of transcribed conversations."},
                    {"role": "user", "content": prompt}
                ],
                # temperature=0.0,
                # max_tokens=16000
            )
        else:
            # Use OpenAI directly
            openai.api_key = api_config.get('api_key')
            chat_model = api_config.get('model', 'gpt-4.1-2025-04-14')
            response = openai.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role": "system", "content": "You are an expert transcript editor who improves the quality, readability, and structure of transcribed conversations."},
                    {"role": "user", "content": prompt}
                ]
                # temperature=0.0,  
                # max_tokens=16000
            )
        
        # Extract the enhanced transcript
        enhanced_transcript = response.choices[0].message.content
        return enhanced_transcript
        
    except Exception as e:
        print(f"Error enhancing transcript: {e}")
        print("Falling back to raw transcript...")
        return raw_transcript

def split_and_transcribe_with_context(audio_path, api_config, max_size_mb=25, max_duration_seconds=1500, audio=None):
    """
    Split an audio file into chunks and transcribe each chunk while preserving context between chunks
    
    Args:
        audio_path: Path to the audio file
        api_config: Dictionary containing API configuration
        max_size_mb: Maximum file size in MB
        max_duration_seconds: Maximum duration in seconds
        audio: Pre-loaded AudioSegment (optional)
        
    Returns:
        str: Combined transcript from all chunks with preserved context
    """
    # Setup API configuration
    use_azure = api_config.get('use_azure', False)
    api_key = api_config.get('api_key')
    transcription_model = api_config.get('transcription_model', 'whisper-1')
    
    # Load the audio file if not provided
    if audio is None:
        audio = AudioSegment.from_file(audio_path)
    
    # Get audio duration in seconds
    duration_seconds = len(audio) / 1000
    
    # Calculate the number of chunks needed based on both size and duration
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    
    chunks_by_size = math.ceil(file_size_mb / (max_size_mb * 0.9))  # Use 90% of max to be safe
    chunks_by_duration = math.ceil(duration_seconds / (max_duration_seconds * 0.95))  # Use 95% of max to be safe
    # num_chunks = max(chunks_by_size, chunks_by_duration)
    num_chunks = chunks_by_size
    
    print(f"Splitting audio into {num_chunks} chunks based on size ({chunks_by_size})")
    
    # Calculate chunk duration in milliseconds
    chunk_length_ms = len(audio) // num_chunks
    
    # Create temp directory for chunks
    temp_dir = tempfile.mkdtemp()
    
    # Split the audio into chunks and transcribe each chunk
    transcripts = []
    context_text = ""  # Initialize context as empty for the first chunk

    if use_azure:
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=api_config.get('azure_endpoint', ''),
            api_version=api_config.get('api_version', '2025-03-01-preview')
        )
    
        # Create a separate client for audio transcription
        from openai import AzureOpenAI as AzureAudioClient
        # audio_endpoint_url = api_config.get('azure_audio_endpoint', 
        #                     api_config.get('azure_endpoint', '').replace("chat/completions?", "audio/transcriptions?"))

        audio_endpoint_url = api_config.get('azure_audio_endpoint')
        audio_client = AzureAudioClient(
            api_key=api_key,
            # azure_endpoint=audio_endpoint_url.split('/openai/')[0],  # Base URL part
            # api_version=api_config.get('api_version', '2024-12-01-preview')
            azure_endpoint=audio_endpoint_url,
            api_version=api_config.get('api_version', '2025-03-01-preview')
        )
    else:
        # Use OpenAI directly
        openai.api_key = api_key
    
    for i in range(num_chunks):
        # Calculate start and end times for this chunk
        start_ms = i * chunk_length_ms
        end_ms = min((i + 1) * chunk_length_ms, len(audio))
        
        # Extract the chunk
        chunk = audio[start_ms:end_ms]
        
        # Save the chunk to a temporary file
        chunk_path = os.path.join(temp_dir, f"chunk_{i}.mp3")
        chunk.export(chunk_path, format="mp3")
        
        # Log chunk information
        chunk_size_mb = os.path.getsize(chunk_path) / (1024 * 1024)
        chunk_duration = len(chunk) / 1000
        print(f"Chunk {i+1}/{num_chunks}: {chunk_size_mb:.2f}MB, {chunk_duration:.2f}s")
        
        # Format timestamp for header
        start_time = format_timestamp(start_ms/1000)
        end_time = format_timestamp(end_ms/1000)
        chunk_header = f"\n[Timestamp: {start_time} - {end_time}]\n"
        
        # Create appropriate prompt with context from previous chunk
        if i == 0:
            # For the first chunk, use a basic prompt
            prompt = 'The following conversation is an AI need analysis and advisory meeting between AI advisors and company representatives. Extract transcript in English with proper dialogue structure.'
        else:
            # For subsequent chunks, include context from previous transcript
            # Limit context to last 170 characters 
            trimmed_context = context_text[-170:] if len(context_text) > 170 else context_text
            prompt = f'''The following is a continuation of a conversation. Here is the previous part of the transcript:
            
{trimmed_context}

Continue the transcription, maintaining speaker consistency and dialogue structure. This is an AI need analysis and advisory meeting between AI advisors and company representatives.'''
        if use_azure:
            print("Using MS Azure endpoint for transcription")
        else:
            print("Using OpenAI direct endpoint for transcription")
        # Transcribe the chunk based on API selection
        try:
            with open(chunk_path, "rb") as chunk_file:

                if use_azure:
                    transcript_response = audio_client.audio.transcriptions.create(
                        model=transcription_model,
                        file=chunk_file,
                        prompt=prompt
                    )
                else:
                    transcript_response = openai.audio.transcriptions.create(
                        model=transcription_model,
                        file=chunk_file,
                        prompt=prompt
                    )
                
                chunk_transcript = transcript_response.text
                
                # Add to our list of transcripts with header
                transcripts.append(chunk_header + chunk_transcript)
                
                # Update context for the next chunk
                context_text = chunk_transcript
                
                # Add a small delay to avoid rate limiting
                time.sleep(1)
                
        except Exception as e:
            print(f"Error transcribing chunk {i+1}: {e}")
            # Add a placeholder for the failed chunk
            transcripts.append(f"[Transcription failed for segment {i+1}]")
            # Wait a bit longer if we hit an error (might be rate limiting)
            time.sleep(5)
        finally:
            # Clean up the temporary chunk file
            try:
                os.remove(chunk_path)
            except Exception as e:
                print(f"Error removing chunk file: {e}")
    
    # Clean up the temporary directory
    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"Error removing temporary directory: {e}")
    
    # Combine all transcripts
    combined_transcript = "\n\n".join(transcripts)
    
    return combined_transcript

# Keep the original function for backward compatibility
def split_and_transcribe(audio_path, api_config, max_size_mb=25, max_duration_seconds=1500, audio=None):
    """
    Split an audio file into chunks and transcribe each chunk (without context preservation)
    
    Args:
        audio_path: Path to the audio file
        api_config: Dictionary containing API configuration
        max_size_mb: Maximum file size in MB
        max_duration_seconds: Maximum duration in seconds
        audio: Pre-loaded AudioSegment (optional)
        
    Returns:
        str: Combined transcript from all chunks
    """
    return split_and_transcribe_with_context(audio_path, api_config, max_size_mb, max_duration_seconds, audio)

def format_timestamp(seconds):
    """Format seconds into MM:SS format"""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"
