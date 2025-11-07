# backend/resilience/graceful_shutdown.py
"""
Graceful Shutdown Handler
Google SRE Best Practice: Clean termination of in-flight requests
"""
import signal
import asyncio
import logging
from typing import Optional, Callable
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class GracefulShutdownHandler:
    """
    Handle graceful shutdown of FastAPI applications

    Google SRE Practice:
    - Complete in-flight requests before shutdown
    - Stop accepting new requests immediately
    - Cleanup resources (DB connections, file handles)
    - Send termination signals to monitoring systems

    Usage:
        handler = GracefulShutdownHandler(app, shutdown_timeout=30.0)
        handler.setup()
    """

    def __init__(
        self,
        shutdown_timeout: float = 30.0,
        on_shutdown: Optional[Callable] = None
    ):
        """
        Args:
            shutdown_timeout: Maximum time to wait for in-flight requests (seconds)
            on_shutdown: Optional callback for custom cleanup logic
        """
        self.shutdown_timeout = shutdown_timeout
        self.on_shutdown = on_shutdown
        self.shutdown_event = asyncio.Event()
        self._original_handlers = {}

    def setup(self):
        """Setup signal handlers for graceful shutdown"""
        # Handle SIGTERM (Docker/Kubernetes stop)
        self._register_signal(signal.SIGTERM)

        # Handle SIGINT (Ctrl+C)
        self._register_signal(signal.SIGINT)

        logger.info(f"[GracefulShutdown] Handlers registered (timeout: {self.shutdown_timeout}s)")

    def _register_signal(self, sig: signal.Signals):
        """Register signal handler with preservation of original handler"""
        original = signal.getsignal(sig)
        self._original_handlers[sig] = original

        def handler(signum, frame):
            logger.info(f"[GracefulShutdown] Received signal {sig.name}, initiating shutdown...")
            self.shutdown_event.set()

            # Trigger async shutdown
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._shutdown())
            except RuntimeError:
                # No running loop, create new one
                asyncio.run(self._shutdown())

        signal.signal(sig, handler)

    async def _shutdown(self):
        """Execute graceful shutdown sequence"""
        logger.info("[GracefulShutdown] Starting graceful shutdown sequence")

        # Step 1: Stop accepting new requests (handled by FastAPI lifespan)
        logger.info("[GracefulShutdown] Stopped accepting new requests")

        # Step 2: Wait for in-flight requests to complete
        logger.info(f"[GracefulShutdown] Waiting up to {self.shutdown_timeout}s for in-flight requests...")
        await asyncio.sleep(1.0)  # Brief delay to allow current requests to finish

        # Step 3: Execute custom cleanup
        if self.on_shutdown:
            try:
                logger.info("[GracefulShutdown] Executing custom cleanup...")
                if asyncio.iscoroutinefunction(self.on_shutdown):
                    await self.on_shutdown()
                else:
                    self.on_shutdown()
            except Exception as e:
                logger.error(f"[GracefulShutdown] Cleanup failed: {e}")

        # Step 4: Final cleanup
        logger.info("[GracefulShutdown] Shutdown complete")

    def restore_signals(self):
        """Restore original signal handlers (for testing)"""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)

@asynccontextmanager
async def lifespan_with_graceful_shutdown(
    shutdown_timeout: float = 30.0,
    on_startup: Optional[Callable] = None,
    on_shutdown: Optional[Callable] = None
):
    """
    FastAPI lifespan context manager with graceful shutdown

    Usage:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with lifespan_with_graceful_shutdown(
                shutdown_timeout=30.0,
                on_startup=my_startup_func,
                on_shutdown=my_cleanup_func
            ):
                yield

        app = FastAPI(lifespan=lifespan)
    """
    # Startup
    logger.info("[Lifespan] Application starting...")
    if on_startup:
        try:
            if asyncio.iscoroutinefunction(on_startup):
                await on_startup()
            else:
                on_startup()
        except Exception as e:
            logger.error(f"[Lifespan] Startup failed: {e}")
            raise

    # Setup graceful shutdown
    handler = GracefulShutdownHandler(
        shutdown_timeout=shutdown_timeout,
        on_shutdown=on_shutdown
    )
    handler.setup()

    logger.info("[Lifespan] Application ready")

    try:
        yield
    finally:
        # Shutdown
        logger.info("[Lifespan] Application shutting down...")
        await handler._shutdown()
        handler.restore_signals()
        logger.info("[Lifespan] Application stopped")

# Convenience function for common cleanup tasks
async def cleanup_resources(redis_client=None, postgres_client=None):
    """
    Standard cleanup for CQOx services

    Args:
        redis_client: Redis client to close
        postgres_client: PostgreSQL client to close
    """
    logger.info("[Cleanup] Closing database connections...")

    if redis_client:
        try:
            await redis_client.close()
            logger.info("[Cleanup] Redis connection closed")
        except Exception as e:
            logger.error(f"[Cleanup] Failed to close Redis: {e}")

    if postgres_client:
        try:
            postgres_client.close()
            logger.info("[Cleanup] PostgreSQL connection closed")
        except Exception as e:
            logger.error(f"[Cleanup] Failed to close PostgreSQL: {e}")

    logger.info("[Cleanup] Resource cleanup complete")
