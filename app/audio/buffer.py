"""
Audio Buffer implementation for ring buffer / thread-safe streaming.
Provides lock-free or lightweight queue/circular buffer for inter-stream transfer.
"""

import queue
import numpy as np


class AudioRingQueue:
    """
    Lightweight FIFO buffer for transferring audio blocks between independent
    audio input and output streams.
    """

    def __init__(self, maxsize: int = 16):
        self._queue = queue.Queue(maxsize=maxsize)

    def write(self, data: np.ndarray) -> bool:
        """Push an audio chunk into queue. Drops oldest if full to avoid lag."""
        try:
            self._queue.put_nowait(data)
            return True
        except queue.Full:
            try:
                # Discard stale buffer to keep real-time latency tight
                _ = self._queue.get_nowait()
                self._queue.put_nowait(data)
                return True
            except (queue.Empty, queue.Full):
                return False

    def read(self, shape, dtype=np.float32) -> np.ndarray:
        """Pop an audio chunk or return silence if empty."""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return np.zeros(shape, dtype=dtype)

    def clear(self):
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
