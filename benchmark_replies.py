import time
from automation.replies import ReviewItem, parse_reply

def benchmark():
    N = 10000
    items = [ReviewItem(i, "r1", "会议", "Speaker", "Name", "action", "high", "note") for i in range(1, N + 1)]

    # Generate text with many ACCEPT commands
    # 1对; 2对; 3对; ... N对
    text = ";".join([f"{i}对" for i in range(1, N + 1)])

    start_time = time.time()
    parsed = parse_reply(text, items)
    end_time = time.time()

    print(f"Parsed {len(parsed.decisions)} decisions.")
    print(f"Time taken: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    benchmark()
