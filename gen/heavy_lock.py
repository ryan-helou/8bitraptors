"""One heavy job at a time on Ryan's 8 GB Mac (2026-11-18: three parallel builds crashed it).
Use: `python3 gen/heavy_lock.py <command...>` runs the command while holding /tmp/8bit_heavy.lock; other callers wait.
Python code can `import heavy_lock; heavy_lock.hold()` instead."""
import fcntl, os, sys, subprocess, time
PATH = "/tmp/8bit_heavy.lock"
_fd = None
def hold():
    global _fd
    if _fd is not None: return
    _fd = open(PATH, "w"); t = time.time()
    fcntl.flock(_fd, fcntl.LOCK_EX)
    if time.time() - t > 1: print(f"[heavy_lock] waited {time.time() - t:.0f} s for another build", file=sys.stderr)
if __name__ == "__main__":
    hold(); sys.exit(subprocess.run(sys.argv[1:]).returncode)
