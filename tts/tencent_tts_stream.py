# -*- coding: utf-8 -*-
import asyncio
import re
import base64
import json
import time
import io
import wave
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from tts.speech_synthesizer_ws import SpeechSynthesizer, SpeechSynthesisListener
from utils.log import logger
from utils.credential import Credential
from config.constants import TENCENT_APP_ID, TENCENT_SECRET_ID, TENCENT_SECRET_KEY

VOICETYPE = 101019  # Cantonese Female
FASTVOICETYPE = ""
CODEC = "pcm"  # 音频格式：pcm/mp3
SAMPLE_RATE = 16000  # 音频采样率：8000/16000
ENABLE_SUBTITLE = True

# Thread pool for handling TTS requests
executor = ThreadPoolExecutor(max_workers=5)

# Audio processing queue
audio_queue = deque()
is_processing = False
current_sentence_id = 0

def pcm_to_wav(pcm_data, sample_rate=16000, sample_width=2, channels=1):
    """Convert PCM data to WAV format with proper headers"""
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        return wav_buffer.getvalue()

def is_websocket_connected(websocket):
    """Check if WebSocket connection is still open"""
    try:
        # For Starlette/FastAPI
        if hasattr(websocket, 'client_state') and hasattr(websocket.client_state, 'name'):
            from starlette.websockets import WebSocketState
            return websocket.client_state != WebSocketState.DISCONNECTED
        
        # For other implementations with 'closed' attribute
        if hasattr(websocket, 'closed'):
            return not websocket.closed
            
        # For websockets library
        if hasattr(websocket, 'open'):
            return websocket.open
            
        # Default: assume connected if we can't determine
        return True
    except:
        # If anything fails, assume disconnected
        return False

class OrderedSpeechSynthesisListener(SpeechSynthesisListener):
    def __init__(self, sentence_id, fe_websocket):
        super().__init__()
        self.sentence_id = sentence_id
        self.fe_websocket = fe_websocket
        self.audio_data = b''
        self.start_time = time.time()
        self.loop = asyncio.get_event_loop()

    def on_synthesis_start(self, session_id):
        logger.info(f"Synthesis started for sentence {self.sentence_id}, session: {session_id}")
        self.audio_data = b''

    def on_audio_result(self, audio_bytes):
        super().on_audio_result(audio_bytes)
        self.audio_data += audio_bytes

    def on_synthesis_end(self):
        super().on_synthesis_end()
        processing_time = time.time() - self.start_time
        
        # Convert PCM to WAV format
        wav_data = pcm_to_wav(self.audio_data, self.sample_rate)
        b64_audio = base64.b64encode(wav_data).decode()
        
        # Add to processing queue
        audio_queue.append({
            'sentence_id': self.sentence_id,
            'audio_data': b64_audio,
            'websocket': self.fe_websocket
        })
        
        logger.info(f"Synthesis completed for sentence {self.sentence_id}: "
                   f"{len(self.audio_data)} bytes PCM -> {len(wav_data)} bytes WAV, "
                   f"time: {processing_time:.2f}s")
        
        # Start processing if not already running
        global is_processing
        if not is_processing:
            asyncio.create_task(process_audio_queue())

    def on_synthesis_fail(self, response):
        super().on_synthesis_fail(response)
        err_code = response.get("code", "N/A")
        err_msg = response.get("message", "")
        logger.error(f"TTS synthesis failed for sentence {self.sentence_id}: {err_code}, {err_msg}")

async def process_audio_queue():
    """Process audio items from the queue in the correct order"""
    global is_processing, current_sentence_id
    
    is_processing = True
    logger.debug("Audio queue processing started")
    
    try:
        while audio_queue:
            # Check if the next item in queue is the expected sentence
            if not audio_queue or audio_queue[0]['sentence_id'] != current_sentence_id:
                # Wait a bit before checking again
                await asyncio.sleep(0.1)
                continue
            
            # Process the next item
            item = audio_queue.popleft()
            
            # Send the audio
            await send_audio_to_frontend(
                item['websocket'], 
                item['audio_data'], 
                item['sentence_id']
            )
            
            # Move to next sentence
            current_sentence_id += 1
            
    except Exception as e:
        logger.error(f"Error in audio queue processing: {e}")
    finally:
        is_processing = False
        logger.debug("Audio queue processing finished")

async def send_audio_to_frontend(websocket, base64_audio, sentence_id):
    """Send audio to frontend with proper error handling"""
    try:
        if is_websocket_connected(websocket):
            await websocket.send_text(json.dumps({
                "type": "audio",
                "sentence_id": sentence_id,
                "payload": base64_audio,
                "format": "wav",
                "sample_rate": SAMPLE_RATE,
                "timestamp": time.time()
            }))
            logger.info(f"Sent audio for sentence {sentence_id}")
    except Exception as e:
        logger.error(f"Failed to send audio for sentence {sentence_id}: {e}")
        # Re-queue the failed audio
        audio_queue.append({
            'sentence_id': sentence_id,
            'audio_data': base64_audio,
            'websocket': websocket
        })

def run_synthesizer(synthesizer):
    """Run the synthesizer in a thread"""
    synthesizer.start()
    synthesizer.wait()

async def process_sentence(text, sentence_id, fe_websocket):
    """Process a single sentence asynchronously"""
    logger.info(f"Starting TTS for sentence {sentence_id}: {text[:50]}...")
    
    listener = OrderedSpeechSynthesisListener(sentence_id, fe_websocket)
    credential_var = Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
    
    synthesizer = SpeechSynthesizer(
        TENCENT_APP_ID, credential_var, listener
    )
    synthesizer.set_text(text)
    synthesizer.set_voice_type(VOICETYPE)
    synthesizer.set_codec(CODEC)
    synthesizer.set_sample_rate(SAMPLE_RATE)
    synthesizer.set_enable_subtitle(ENABLE_SUBTITLE)
    synthesizer.set_fast_voice_type(FASTVOICETYPE)
    
    # Run synthesizer in thread pool to avoid blocking
    await asyncio.get_event_loop().run_in_executor(
        executor, run_synthesizer, synthesizer
    )
    
    logger.info(f"Completed TTS processing for sentence {sentence_id}")

def split_sentences(text: str):
    """Split Chinese/English text into sentences"""
    pattern = r'[。！？.!?\n]+'
    sentences = re.split(pattern, text)
    logger.info(f"Split text into {len(sentences)} sentences")
    return [s.strip() for s in sentences if s.strip()]

async def process_tts_stream(full_text, fe_websocket):
    """Process full text through TTS with parallel execution"""
    logger.info(f"Starting TTS stream processing: {full_text[:100]}...")
    start_time = time.time()
    
    sentences = split_sentences(full_text)
    
    # Create all TTS tasks to run in parallel
    tasks = []
    for idx, sentence in enumerate(sentences):
        task = asyncio.create_task(
            process_sentence(sentence, idx, fe_websocket)
        )
        tasks.append(task)
    
    # Wait for all tasks to complete with timeout
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=300)  # 5-minute timeout
    except asyncio.TimeoutError:
        logger.error("TTS processing timed out after 5 minutes")
        # Cancel all remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
    
    # Wait for audio queue to be fully processed
    while audio_queue:
        await asyncio.sleep(0.1)
    
    processing_time = time.time() - start_time
    logger.info(f"Completed TTS stream processing in {processing_time:.2f} seconds")
    
    # Send completion message
    try:
        await fe_websocket.send_text(json.dumps({
            "type": "tts_complete",
            "total_sentences": len(sentences),
            "processing_time": processing_time
        }))
    except Exception as e:
        logger.warning(f"Failed to send completion message: {e}")
    
    # Reset for next stream
    global current_sentence_id
    current_sentence_id = 0
    audio_queue.clear()