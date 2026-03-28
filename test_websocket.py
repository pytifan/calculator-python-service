"""
WebSocket test client to listen for calculation results from SpringBoot
"""
import asyncio
import websockets
import json
import sys

async def listen_to_calculation(calculation_id: str):
    """
    Connect to WebSocket and listen for calculation updates

    Usage:
        python test_websocket.py a5654d2e-01f0-4876-9757-eefde4a65b5a
    """

    # Build WebSocket URL
    ws_url = f"ws://localhost:8080/topic/calculation/{calculation_id}"

    print(f"\n{'='*60}")
    print(f"📡 Listening to WebSocket: {ws_url}")
    print(f"{'='*60}\n")

    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ Connected to WebSocket\n")

            # Listen for messages
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)

                    print(f"📬 Message received:")
                    print(json.dumps(data, indent=2))
                    print()

                    # Check if calculation is complete
                    if data.get("status") == "COMPLETED":
                        print("✅ Calculation COMPLETED!")
                        print(f"\n{'='*60}")
                        print("FINAL RESULTS")
                        print(f"{'='*60}")
                        print(json.dumps(data, indent=2))
                        break

                    elif data.get("status") == "FAILED":
                        print("❌ Calculation FAILED!")
                        print(json.dumps(data, indent=2))
                        break

                except asyncio.TimeoutError:
                    print("⏳ Waiting for next message...")
                    continue

    except ConnectionRefusedError:
        print(f"❌ Could not connect to {ws_url}")
        print("   Is SpringBoot running on port 8080?")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_websocket.py <calculation_id>")
        print("Example: python test_websocket.py a5654d2e-01f0-4876-9757-eefde4a65b5a")
        sys.exit(1)

    calculation_id = sys.argv[1]

    # Run async listener
    try:
        asyncio.run(listen_to_calculation(calculation_id))
    except KeyboardInterrupt:
        print("\n\n⛔ Interrupted by user")