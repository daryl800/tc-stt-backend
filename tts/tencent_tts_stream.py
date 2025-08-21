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

VOICETYPE = 101019  # 音色类型
FASTVOICETYPE = ""
CODEC = "pcm"  # 音频格式：pcm/mp3
SAMPLE_RATE = 16000  # 音频采样率：8000/16000
ENABLE_SUBTITLE = True

# Thread pool for handling TTS requests
executor = ThreadPoolExecutor(max_workers=5)

# Global audio queue and state management
audio_queue = deque()
current_sentence_id = 0
sentence_processors = {}  # Track sentence processors by ID
queue_processor_task = None

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

import queue

# Replace the global deque with a thread-safe queue
audio_queue = queue.Queue()

class OrderedSpeechSynthesisListener(SpeechSynthesisListener):
    def __init__(self, sentence_id, fe_websocket):
        super().__init__()
        self.sentence_id = sentence_id
        self.fe_websocket = fe_websocket
        self.audio_data = b''
        self.start_time = time.time()
        self.chunk_count = 0
        # REMOVE this line - it causes the error
        # self.loop = asyncio.get_event_loop()
        self.is_complete = False

    def on_audio_result(self, audio_bytes):
        super().on_audio_result(audio_bytes)
        self.audio_data += audio_bytes
        self.chunk_count += 1
        
        # Convert PCM to WAV for this chunk
        wav_chunk = pcm_to_wav(audio_bytes, SAMPLE_RATE)
        b64_audio = base64.b64encode(wav_chunk).decode()
        
        # Put item in thread-safe queue (no async operations here)
        audio_queue.put({
            'sentence_id': self.sentence_id,
            'audio_data': b64_audio,
            'websocket': self.fe_websocket,
            'chunk_number': self.chunk_count,
            'is_complete': False,
            'timestamp': time.time()
        })

    def on_synthesis_end(self):
        super().on_synthesis_end()
        self.is_complete = True
        processing_time = time.time() - self.start_time
        
        # Put completion marker in queue
        audio_queue.put({
            'sentence_id': self.sentence_id,
            'audio_data': '',
            'websocket': self.fe_websocket,
            'chunk_number': self.chunk_count + 1,
            'is_complete': True,
            'timestamp': time.time()
        })

    def on_synthesis_fail(self, response):
        super().on_synthesis_fail(response)
        err_code = response.get("code", "N/A")
        err_msg = response.get("message", "")
        logger.error(f"TTS synthesis failed for sentence {self.sentence_id}: {err_code}, {err_msg}")

async def process_audio_queue():
    """Process audio items from the queue in the correct order"""
    global current_sentence_id
    
    logger.debug("Audio queue processor started")
    
    # Track the next expected chunk for each sentence
    next_chunk_per_sentence = {}
    
    try:
        while audio_queue:
            # Find the next item that should be processed
            next_item_index = -1
            for i, item in enumerate(audio_queue):
                sentence_id = item['sentence_id']
                
                # Initialize tracking for this sentence if needed
                if sentence_id not in next_chunk_per_sentence:
                    next_chunk_per_sentence[sentence_id] = 1
                
                # Check if this is the next expected chunk for this sentence
                if item['chunk_number'] == next_chunk_per_sentence[sentence_id]:
                    next_item_index = i
                    break
            
            if next_item_index == -1:
                # No items ready for processing, wait a bit
                await asyncio.sleep(0.01)
                continue
            
            # Process the next item
            item = audio_queue[next_item_index]
            del audio_queue[next_item_index]
            
            sentence_id = item['sentence_id']
            chunk_number = item['chunk_number']
            
            if item['is_complete']:
                # This is a completion marker
                await send_completion_marker(item['websocket'], sentence_id)
                # Remove sentence from tracking
                if sentence_id in next_chunk_per_sentence:
                    del next_chunk_per_sentence[sentence_id]
            else:
                # This is an audio chunk
                await send_audio_to_frontend(
                    item['websocket'],
                    item['audio_data'],
                    sentence_id,
                    chunk_number,
                    False
                )
                # Update expected next chunk
                next_chunk_per_sentence[sentence_id] = chunk_number + 1
            
            # Small delay to prevent overwhelming the frontend
            await asyncio.sleep(0.001)
                
    except Exception as e:
        logger.error(f"Error in audio queue processing: {e}")
    finally:
        logger.debug("Audio queue processor finished")

async def send_audio_to_frontend(websocket, base64_audio, sentence_id, chunk_number, is_complete):
    """Send audio to frontend with proper error handling"""
    try:
        if is_websocket_connected(websocket):
            await websocket.send_text(json.dumps({
                "type": "audio_chunk",
                "sentence_id": sentence_id,
                "data": base64_audio,
                "format": "wav",
                "sample_rate": SAMPLE_RATE,
                "chunk_number": chunk_number,
                "is_complete": is_complete,
                "timestamp": time.time()
            }))
            logger.debug(f"Sent audio chunk {chunk_number} for sentence {sentence_id}")
    except Exception as e:
        logger.error(f"Failed to send audio for sentence {sentence_id}, chunk {chunk_number}: {e}")
        # Re-queue the failed audio with backoff
        await asyncio.sleep(0.1)
        audio_queue.append({
            'sentence_id': sentence_id,
            'audio_data': base64_audio,
            'websocket': websocket,
            'chunk_number': chunk_number,
            'is_complete': is_complete,
            'timestamp': time.time()
        })

async def send_completion_marker(websocket, sentence_id):
    """Send completion marker for a sentence"""
    try:
        if is_websocket_connected(websocket):
            await websocket.send_text(json.dumps({
                "type": "sentence_complete",
                "sentence_id": sentence_id,
                "timestamp": time.time()
            }))
            logger.info(f"Sent completion marker for sentence {sentence_id}")
    except Exception as e:
        logger.warning(f"Failed to send completion marker for sentence {sentence_id}: {e}")

def run_synthesizer(synthesizer):
    """Run the synthesizer in a thread"""
    synthesizer.start()
    synthesizer.wait()

async def process_sentence(text, sentence_id, fe_websocket):
    """Process a single sentence asynchronously"""
    logger.info(f"Starting TTS for sentence {sentence_id}: {text[:50]}...")
    
    # Get the main event loop
    main_loop = asyncio.get_event_loop()
    listener = OrderedSpeechSynthesisListener(sentence_id, fe_websocket, main_loop)
    """Process a single sentence asynchronously"""
    logger.info(f"Starting TTS for sentence {sentence_id}: {text[:50]}...")
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
    
    # Clean up
    global current_sentence_id
    current_sentence_id = 0
    audio_queue.clear()