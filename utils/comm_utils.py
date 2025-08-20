import asyncio
import time
from typing import Union
from collections import deque
from utils.log import logger
from fastapi import WebSocket



async def reply_to_FE(websocket: WebSocket, msg_type: str, payload: Union[dict, list, int, float, bool]):
    await websocket.send_json({
        "type":  msg_type,
        "payload": payload
    })

audio_queue = asyncio.Queue()
sending_task = None



# Global audio queue and control variables
audio_queue = deque()
is_processing = False
current_sentence_id = 0
sentences_completed = set()

async def enqueue_audio(websocket: WebSocket, base64_audio: str, sentence_id: int):
    """Add audio to queue with sentence ID for ordering"""
    audio_queue.append({
        'websocket': websocket,
        'audio_data': base64_audio,
        'sentence_id': sentence_id,
        'timestamp': time.time()
    })
    
    logger.debug(f"Audio enqueued for sentence {sentence_id}, queue size: {len(audio_queue)}")
    
    # Start processing if not already running
    if not is_processing:
        asyncio.create_task(audio_processing_loop())

async def audio_processing_loop():
    """Process audio items in order, ensuring no overlap"""
    global is_processing, current_sentence_id
    
    is_processing = True
    logger.debug("Audio processing loop started")
    
    try:
        while audio_queue:
            # Check if the next item in queue is the expected sentence
            next_item = audio_queue[0]
            
            # If it's not the next expected sentence, wait
            if next_item['sentence_id'] != current_sentence_id:
                # Check if we've already processed this sentence
                if next_item['sentence_id'] in sentences_completed:
                    # Remove duplicate or already processed sentence
                    audio_queue.popleft()
                    continue
                    
                # Wait a bit before checking again
                await asyncio.sleep(0.1)
                continue
            
            # Process the next item
            item = audio_queue.popleft()
            
            # Send the audio
            await send_audio_directly(item['websocket'], item['audio_data'], item['sentence_id'])
            
            # Mark as completed and move to next sentence
            sentences_completed.add(item['sentence_id'])
            current_sentence_id += 1
            
            # Small delay to ensure frontend has time to process
            await asyncio.sleep(0.05)
            
    except Exception as e:
        logger.error(f"Error in audio processing loop: {e}")
    finally:
        is_processing = False
        logger.debug("Audio processing loop finished")

async def send_audio_directly(websocket: WebSocket, base64_audio: str, sentence_id: int):
    """Send audio directly to frontend with sequence information"""
    try:
        if is_websocket_connected(websocket):
            await websocket.send_text(json.dumps({
                "type": "audio",
                "sentence_id": sentence_id,
                "data": base64_audio,
                "format": "wav",
                "sample_rate": SAMPLE_RATE,
                "timestamp": time.time()
            }))
            logger.info(f"Sent audio for sentence {sentence_id}")
    except Exception as e:
        logger.error(f"Failed to send audio for sentence {sentence_id}: {e}")
        # Re-queue the failed audio
        audio_queue.append({
            'websocket': websocket,
            'audio_data': base64_audio,
            'sentence_id': sentence_id,
            'timestamp': time.time()
        })