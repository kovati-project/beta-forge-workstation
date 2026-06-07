#!/usr/bin/env python3
"""
Real-time speech-to-text transcription via faster-whisper WebSocket API.
Streams audio input from microphone and displays live transcription.
"""
import asyncio
import websockets
import json
import sys
import pyaudio

WHISPER_WS = "ws://10.10.10.2:9099/v1/audio/transcriptions/realtime"
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
AUDIO_FORMAT = pyaudio.paInt16

async def transcribe_realtime():
    """Stream audio from microphone to Whisper and display live transcription."""
    
    try:
        import websockets
    except ImportError:
        print("ERROR: websockets not installed")
        print("Install with: pip3 install websockets pyaudio")
        sys.exit(1)
    
    print("Real-time Transcription")
    print("=" * 60)
    print(f"Whisper endpoint: {WHISPER_WS}")
    print("Sample rate: 16kHz, mono")
    print("Press Ctrl+C to stop")
    print()
    
    # Initialize audio
    audio = pyaudio.PyAudio()
    try:
        stream = audio.open(
            format=AUDIO_FORMAT,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            input_device_index=0  # Default microphone
        )
    except Exception as e:
        print(f"ERROR: Could not open audio device: {e}")
        print("Available devices:")
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"  {i}: {info['name']}")
        sys.exit(1)
    
    # Connect to WebSocket
    try:
        async with websockets.connect(
            WHISPER_WS,
            subprotocols=["whisper-binary"],
            close_timeout=10
        ) as ws:
            print("Connected to Whisper WebSocket")
            print("Listening for audio...")
            print()
            
            current_text = ""
            final_text = ""
            
            async def send_audio():
                """Send audio chunks from microphone."""
                try:
                    while True:
                        data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                        await ws.send(data)
                        await asyncio.sleep(0.01)  # Small delay to prevent overwhelming
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"ERROR in send_audio: {e}")
            
            async def receive_transcriptions():
                """Receive transcriptions from WebSocket."""
                nonlocal current_text, final_text
                try:
                    async for message in ws:
                        try:
                            result = json.loads(message)
                            
                            if result.get("result"):
                                # Partial result
                                current_text = result["result"][0].get("partial", "")
                                print(f"\r[partial] {current_text}", end="", flush=True)
                            
                            if result.get("result_final"):
                                # Final transcription
                                final_result = result["result"][0].get("result", "")
                                if final_result:
                                    final_text += " " + final_result
                                    print(f"\n[final] {final_result}")
                                    print(f"Full text: {final_text.strip()}")
                                    print()
                                    current_text = ""
                        except json.JSONDecodeError:
                            print(f"ERROR: Could not parse message: {message}")
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"ERROR in receive_transcriptions: {e}")
            
            # Run both tasks concurrently
            send_task = asyncio.create_task(send_audio())
            recv_task = asyncio.create_task(receive_transcriptions())
            
            try:
                await asyncio.gather(send_task, recv_task)
            except KeyboardInterrupt:
                print("\n\nStopping transcription...")
                send_task.cancel()
                recv_task.cancel()
                try:
                    await asyncio.gather(send_task, recv_task)
                except asyncio.CancelledError:
                    pass
    
    except ConnectionRefusedError:
        print(f"ERROR: Could not connect to Whisper WebSocket at {WHISPER_WS}")
        print("Make sure Whisper service is running: docker compose -f docker/compose.voice.yml ps")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        print("Audio stream closed")

def main():
    """Main entry point."""
    if sys.version_info < (3, 7):
        print("ERROR: Python 3.7+ required")
        sys.exit(1)
    
    try:
        asyncio.run(transcribe_realtime())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
