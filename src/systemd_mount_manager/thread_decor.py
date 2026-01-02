from typing import Callable, TypeVar, ParamSpec, Awaitable
import functools
import asyncio
import concurrent.futures

P = ParamSpec("P")
R = TypeVar("R")

_executor = concurrent.futures.ThreadPoolExecutor()


def run_in_thread_executor(fn: Callable[P, R]) -> Callable[P, concurrent.futures.Future[R]]:
    """Synchronous: returns concurrent.futures.Future[R].
    You use concurrent.futures.Future when:
    - Your program is fundamentally synchronous
    - You want background work without committing to asyncio
    - Blocking is acceptable at explicit points
    - You're writing libraries that shouldn't force asyncio on users
    """
    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> concurrent.futures.Future[R]:
        return _executor.submit(fn, *args, **kwargs)
    
    # submit() returns a concurrent.futures.Future object. These
    # cannot be awaited with the async/await syntax. Generally, the common
    # pattern is to get the result by scheduling a callback using the
    # add_done_callback method (shown below). But in some cases you may
    # just store the future and check the result later. Its open ended.

    return wrapper


def run_in_thread_awaitable(fn: Callable[P, R]) -> Callable[P, Awaitable[R]]:
    """Async-friendly: returns an awaitable.
    You use Awaitable / asyncio Futures when you already have an event loop.
    If there is an asyncio loop in the current thread, we must provide
    an asyncio awaitable in order to allow the existing loop to await the result.
"""

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        loop = asyncio.get_running_loop()
        # run in the same executor so threads are reused
        return await loop.run_in_executor(
            _executor, functools.partial(fn, *args, **kwargs)
        )
        # get_running_loop is the new way to get the current loop.
        # It is preferred over get_event_loop for modern python.
        # run_in_executor returns an asyncio.Future, which is an awaitable
        # (specifically an asyncio Future bound to the current loop, not a
        # generic awaitable. This might matter if there's multiple loops).

    return wrapper


# For testing / Demonstration
if __name__ == "__main__":
    # Test #1 : sync

    @run_in_thread_executor
    def blocking_work(n: int) -> int:
        # blocking / CPU / C-extension work
        return sum(i * i for i in range(n))

    f = blocking_work(10_000_000)
    
    # Generally speaking you want to avoid using the f.result() method.
    # It blocks the thread it is called in until the result is ready.
    # The typical design pattern is to schedule a callback using the
    # add_done_callback method.
    
    f.add_done_callback(lambda x: print(x.result()))
    
    # The function passed to the callback runs in the thread that completes 
    # the future (That's usually the thread doing the work but not always).
    # You must treat it as an arbitrary background thread and avoid touching 
    # shared mutable state. Always best to use pure functions without side effects.

    # ===============================#
    # Test #2: Async

    @run_in_thread_awaitable
    def blocking_io(path: str) -> str:
        with open(path, "r") as fh:
            return fh.read()

    async def main() -> None:
        text = await blocking_io("/some/huge/file")
        print(len(text))
        
        # Now since blocking_io returns an awaitable, asyncio can treat
        # it as a coroutine and await it. Asyncio doesn't care how the work gets
        # done, it just sees an awaitable.


# NOTE: executor has no shutdown path. In long-running apps (GUIs, TUIs, servers) 
# that’s fine. In short scripts or tests, Python will clean it up on exit, but 
# explicitly shutting it down on program exit is cleaner.