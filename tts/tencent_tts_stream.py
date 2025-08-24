# -*- coding: utf-8 -*-
import asyncio
import io
import re
import base64
import json
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import wave
from tts.speech_synthesizer_ws import SpeechSynthesizer, SpeechSynthesisListener
from utils.log import logger
from utils.credential import Credential
from config.constants import TENCENT_APP_ID, TENCENT_SECRET_ID, TENCENT_SECRET_KEY

VOICETYPE = 101019  # 音色类型
FASTVOICETYPE = ""
CODEC = "pcm"  # 音频格式：pcm/mp3
SAMPLE_RATE = 16000  # 音频采样率：8000/16000
ENABLE_SUBTITLE = True

# Thread pool for handling TTS requests
executor = ThreadPoolExecutor(max_workers=5)

# Global queue for ordered audio delivery
audio_queue = deque()
current_sentence_id = 0
is_processing_queue = False

def pcm_to_wav(pcm_data, sample_rate=16000, sample_width=2, channels=1):
    """Convert PCM data to WAV format"""
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
        if hasattr(websocket, 'client_state') and hasattr(websocket.client_state, 'name'):
            from starlette.websockets import WebSocketState
            return websocket.client_state != WebSocketState.DISCONNECTED
        if hasattr(websocket, 'closed'):
            return not websocket.closed
        if hasattr(websocket, 'open'):
            return websocket.open
        return True
    except:
        return False

class SentenceSynthesisListener(SpeechSynthesisListener):
    def __init__(self, sentence_id, fe_websocket):
        super().__init__()
        self.sentence_id = sentence_id
        self.fe_websocket = fe_websocket
        self.audio_data = b''
        self.start_time = time.time()

    def on_synthesis_start(self, session_id):
        logger.info(f"Synthesis started for sentence {self.sentence_id}")
        self.audio_data = b''

    def on_audio_result(self, audio_bytes):
        super().on_audio_result(audio_bytes)
        self.audio_data += audio_bytes  # Accumulate audio data

    def on_synthesis_end(self):
        super().on_synthesis_end()
        processing_time = time.time() - self.start_time
        
        # Convert complete PCM sentence to WAV
        wav_data = pcm_to_wav(self.audio_data, SAMPLE_RATE)
        b64_audio = base64.b64encode(wav_data).decode()
        
        # Add to queue for ordered delivery
        audio_queue.append({
            'sentence_id': self.sentence_id,
            'audio_data': b64_audio,
            'websocket': self.fe_websocket,
            'processing_time': processing_time
        })
        
        logger.info(f"Synthesis completed for sentence {self.sentence_id}: "
                   f"{len(self.audio_data)} bytes, time: {processing_time:.2f}s")
        
        # Start queue processor if not running
        global is_processing_queue
        if not is_processing_queue:
            asyncio.create_task(process_audio_queue())

    def on_synthesis_fail(self, response):
        super().on_synthesis_fail(response)
        err_code = response.get("code", "N/A")
        err_msg = response.get("message", "")
        logger.error(f"TTS synthesis failed for sentence {self.sentence_id}: {err_code}, {err_msg}")

async def process_audio_queue():
    """Process audio items in the correct order (sentence 0, 1, 2, ...)"""
    global is_processing_queue, current_sentence_id
    
    is_processing_queue = True
    logger.debug("Audio queue processor started")
    
    try:
        while audio_queue:
            # Check if the next item in queue is the expected sentence
            next_item = None
            for item in audio_queue:
                if item['sentence_id'] == current_sentence_id:
                    next_item = item
                    break
            
            if not next_item:
                # Wait for the next expected sentence to arrive
                await asyncio.sleep(0.1)
                continue
            
            # Remove the item from queue
            audio_queue.remove(next_item)
            
            # Send the audio
            await send_complete_sentence(
                next_item['websocket'],
                next_item['audio_data'],
                next_item['sentence_id']
            )
            
            # Move to next sentence
            current_sentence_id += 1
            
    except Exception as e:
        logger.error(f"Error in audio queue processing: {e}")
    finally:
        is_processing_queue = False
        logger.debug("Audio queue processor finished")

async def send_complete_sentence(websocket, b64_audio, sentence_id):
    """Send complete sentence audio to frontend"""
    try:
        if is_websocket_connected(websocket):
            await websocket.send_text(json.dumps({
                "type": "audio",
                "sentence_id": sentence_id,
                "data": b64_audio,
                "format": "wav",
                "sample_rate": SAMPLE_RATE,
                "timestamp": time.time()
            }))
            logger.info(f"✅ Sent complete audio for sentence {sentence_id}")
    except Exception as e:
        logger.error(f"❌ Failed to send audio for sentence {sentence_id}: {e}")

def run_synthesizer(synthesizer):
    """Run the synthesizer in a thread"""
    synthesizer.start()
    synthesizer.wait()

async def process_sentence(text, sentence_id, fe_websocket):
    """Process a single sentence asynchronously"""
    logger.info(f"Starting TTS for sentence {sentence_id}: {text[:50]}...")
    
    listener = SentenceSynthesisListener(sentence_id, fe_websocket)
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
    """Process full text through TTS with parallel execution but ordered delivery"""
    logger.info(f"Starting TTS stream processing: {full_text[:100]}...")
    start_time = time.time()
    
    sentences = split_sentences(full_text)
    total_sentences = len(sentences)
    
    # Send start message
    try:
        await fe_websocket.send_text(json.dumps({
            "type": "tts_start",
            "total_sentences": total_sentences,
            "timestamp": time.time()
        }))
    except Exception as e:
        logger.warning(f"Failed to send start message: {e}")
    
    # Create all TTS tasks to run in parallel
    tasks = []
    for idx, sentence in enumerate(sentences):
        task = asyncio.create_task(
            process_sentence(sentence, idx, fe_websocket)
        )
        tasks.append(task)
    
    # Wait for all tasks to complete with timeout
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=300)
    except asyncio.TimeoutError:
        logger.error("TTS processing timed out after 5 minutes")
        # Cancel all remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
    
    # Wait for audio queue to be fully processed
    max_wait_time = 10
    wait_start = time.time()
    while audio_queue and (time.time() - wait_start) < max_wait_time:
        await asyncio.sleep(0.1)
    
    processing_time = time.time() - start_time
    logger.info(f"Completed TTS stream processing in {processing_time:.2f} seconds")
    
    # Send completion message
    try:
        await fe_websocket.send_text(json.dumps({
            "type": "tts_complete",
            "total_sentences": total_sentences,
            "processing_time": processing_time,
            "timestamp": time.time()
        }))
    except Exception as e:
        logger.warning(f"Failed to send completion message: {e}")
    
    # Reset for next stream
    global current_sentence_id
    current_sentence_id = 0
    audio_queue.clear()