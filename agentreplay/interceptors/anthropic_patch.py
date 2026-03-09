"""Monkey-patch interceptor for Anthropic messages."""
from __future__ import annotations

import time
import traceback
from contextlib import contextmanager
from typing import Any, AsyncGenerator, Generator

from ..models import NodeType, TraceNode
from ..sqlite_store import SQLiteStore, get_default_store

# Module-level state for patching — guarded by _state_lock
import threading as _threading
_state_lock = _threading.Lock()
_original_anthropic_create: Any = None
_original_anthropic_async_create: Any = None
_patch_state: dict[str, Any] = {
    "run_id": None,
    "store": None,
    "patched": False,
}


def patch(run_id: str, store: SQLiteStore | None = None) -> None:
    """Patch Anthropic client to intercept messages.create calls."""
    global _original_anthropic_create, _original_anthropic_async_create

    with _state_lock:
        if _patch_state["patched"]:
            return

        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "anthropic package not found. Install it with: pip install anthropic"
            ) from e

        _patch_state["run_id"] = run_id
        _patch_state["store"] = store or get_default_store()
        _patch_state["patched"] = True

    # Patch sync version
    _original_anthropic_create = anthropic.Anthropic.messages.create

    def patched_create(self: Any, **kwargs: Any) -> Any:
        return _patched_create_sync(self, **kwargs)

    anthropic.Anthropic.messages.create = patched_create

    # Patch async version
    _original_anthropic_async_create = anthropic.AsyncAnthropic.messages.create

    async def patched_async_create(self: Any, **kwargs: Any) -> Any:
        return await _patched_create_async(self, **kwargs)

    anthropic.AsyncAnthropic.messages.create = patched_async_create


def unpatch() -> None:
    """Restore original Anthropic implementations."""
    global _original_anthropic_create, _original_anthropic_async_create

    if not _patch_state["patched"]:
        return

    try:
        import anthropic
    except ImportError:
        return

    if _original_anthropic_create is not None:
        anthropic.Anthropic.messages.create = _original_anthropic_create
        _original_anthropic_create = None

    if _original_anthropic_async_create is not None:
        anthropic.AsyncAnthropic.messages.create = _original_anthropic_async_create
        _original_anthropic_async_create = None

    _patch_state["patched"] = False
    _patch_state["run_id"] = None
    _patch_state["store"] = None


@contextmanager
def patched(run_id: str, store: SQLiteStore | None = None) -> Generator[None, None, None]:
    """Context manager for temporary Anthropic patching."""
    patch(run_id, store)
    try:
        yield
    finally:
        unpatch()


def _patched_create_sync(self: Any, **kwargs: Any) -> Any:
    """Wrapped sync messages.create."""
    run_id = _patch_state["run_id"]
    store = _patch_state["store"]

    if not run_id or not store:
        return _original_anthropic_create(self, **kwargs)

    # Extract model and messages for recording
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    system = kwargs.get("system", None)

    # Build inputs dict
    inputs: dict[str, Any] = {
        "messages": messages,
        "model": model,
        **{k: v for k, v in kwargs.items() if k not in ("messages", "model")},
    }
    if system is not None:
        inputs["system"] = system

    # Create trace node
    node = TraceNode(
        run_id=run_id,
        parent_id=None,
        node_type=NodeType.LLM,
        name=f"anthropic_{model}",
        start_time=time.time(),
        inputs=inputs,
        model_name=model,
    )

    try:
        # Call original
        response = _original_anthropic_create(self, **kwargs)

        # Extract outputs
        content = None
        stop_reason = None

        if response.content and len(response.content) > 0:
            for block in response.content:
                # Look for text block
                if hasattr(block, "text"):
                    content = block.text
                    break

        stop_reason = getattr(response, "stop_reason", None)

        outputs: dict[str, Any] = {
            "content": content,
            "stop_reason": stop_reason,
        }

        # Extract token usage if present
        if hasattr(response, "usage"):
            usage = response.usage
            node.token_usage = {
                "input_tokens": getattr(usage, "input_tokens", 0),
                "output_tokens": getattr(usage, "output_tokens", 0),
            }

        node.finish(outputs)
        store.upsert_node(node)

        return response

    except Exception as e:
        node.error = str(e)
        node.end_time = time.time()
        store.upsert_node(node)
        raise


async def _patched_create_async(self: Any, **kwargs: Any) -> Any:
    """Wrapped async messages.create."""
    run_id = _patch_state["run_id"]
    store = _patch_state["store"]

    if not run_id or not store:
        return await _original_anthropic_async_create(self, **kwargs)

    # Extract model and messages for recording
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    system = kwargs.get("system", None)

    # Build inputs dict
    inputs: dict[str, Any] = {
        "messages": messages,
        "model": model,
        **{k: v for k, v in kwargs.items() if k not in ("messages", "model")},
    }
    if system is not None:
        inputs["system"] = system

    # Create trace node
    node = TraceNode(
        run_id=run_id,
        parent_id=None,
        node_type=NodeType.LLM,
        name=f"anthropic_{model}",
        start_time=time.time(),
        inputs=inputs,
        model_name=model,
    )

    try:
        # Call original
        response = await _original_anthropic_async_create(self, **kwargs)

        # Extract outputs
        content = None
        stop_reason = None

        if response.content and len(response.content) > 0:
            for block in response.content:
                # Look for text block
                if hasattr(block, "text"):
                    content = block.text
                    break

        stop_reason = getattr(response, "stop_reason", None)

        outputs: dict[str, Any] = {
            "content": content,
            "stop_reason": stop_reason,
        }

        # Extract token usage if present
        if hasattr(response, "usage"):
            usage = response.usage
            node.token_usage = {
                "input_tokens": getattr(usage, "input_tokens", 0),
                "output_tokens": getattr(usage, "output_tokens", 0),
            }

        node.finish(outputs)
        store.upsert_node(node)

        return response

    except Exception as e:
        node.error = str(e)
        node.end_time = time.time()
        store.upsert_node(node)
        raise
