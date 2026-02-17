"""
Worker management utilities.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def start_worker(concurrency: int = 4, queues: str = "default"):
    """Start Celery worker."""
    cmd = [
        "celery", "-A", "app.core.celery_app",
        "worker",
        "--loglevel=info",
        f"--concurrency={concurrency}",
        f"--queues={queues}",
    ]
    
    print(f"Starting worker with command: {' '.join(cmd)}")
    subprocess.run(cmd)


def start_beat():
    """Start Celery beat scheduler."""
    cmd = [
        "celery", "-A", "app.core.celery_app",
        "beat",
        "--loglevel=info",
    ]
    
    print(f"Starting beat scheduler: {' '.join(cmd)}")
    subprocess.run(cmd)


def start_flower(port: int = 5555):
    """Start Flower monitoring."""
    cmd = [
        "celery", "-A", "app.core.celery_app",
        "flower",
        f"--port={port}",
    ]
    
    print(f"Starting Flower on port {port}")
    subprocess.run(cmd)


def purge_queue(queue: str = "default"):
    """Purge all tasks from a queue."""
    cmd = [
        "celery", "-A", "app.core.celery_app",
        "purge",
        "-Q", queue,
        "-f",  # Force, no confirmation
    ]
    
    print(f"Purging queue: {queue}")
    subprocess.run(cmd)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage Celery workers")
    parser.add_argument("command", choices=["worker", "beat", "flower", "purge"])
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--queues", default="default,documents,processing")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--queue", default="default", help="Queue to purge")
    
    args = parser.parse_args()
    
    if args.command == "worker":
        start_worker(args.concurrency, args.queues)
    elif args.command == "beat":
        start_beat()
    elif args.command == "flower":
        start_flower(args.port)
    elif args.command == "purge":
        purge_queue(args.queue)