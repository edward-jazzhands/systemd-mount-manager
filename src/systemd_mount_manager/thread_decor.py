from typing import Callable, TypeVar, ParamSpec, Awaitable
import functools
import asyncio
import concurrent.futures

P = ParamSpec("P")
R = TypeVar("R")

_executor = concurrent.futures.ThreadPoolExecutor()


def run_in_thread_executor(fn: Callable[P, R]) -> Callable[P, concurrent.futures.Future[R]]:
    """Synchronous: returns concurrent.futures.Future[R].
    Note that generally speaking there's no practical reason you would use this.
    that I am aware of. It's here for reference."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> concurrent.futures.Future[R]:
        return _executor.submit(fn, *args, **kwargs)

    return wrapper


def run_in_thread_awaitable(fn: Callable[P, R]) -> Callable[P, Awaitable[R]]:
    """Async-friendly: returns an awaitable."""

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        loop = asyncio.get_running_loop()
        # run in the same executor so threads are reused
        return await loop.run_in_executor(
            _executor, functools.partial(fn, *args, **kwargs)
        )

    return wrapper


# For testing / Demonstration
if __name__ == "__main__":
    # Test #1 : sync

    @run_in_thread_executor
    def blocking_work(n: int) -> int:
        # blocking / CPU / C-extension work
        return sum(i * i for i in range(n))

    f = blocking_work(10_000_000)
    result = f.result()  # blocks here until done
    
    # Note that as stated above, since this blocks thread it is called in, there's
    # no practical reason to use it at all. You need the async extension to
    # get the practical benefit.
    # Remember even with the async extension, Python is still inherently
    # single-threaded due to being GIL locked (unless using the new
    # 3.13t build). Doing CPU-blocking work in an async context
    # will only give marginal benefits to app latency.

    # ===============================#
    # Test #2: Async

    @run_in_thread_awaitable
    def blocking_io(path: str) -> str:
        with open(path, "r") as fh:
            return fh.read()

    async def main() -> None:
        text = await blocking_io("/some/huge/file")
        print(len(text))
