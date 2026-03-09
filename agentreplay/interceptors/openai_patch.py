"""Monkey-patch interceptor for OpenAI chat completions."""
from __future__ import annotations

import time
import traceback
from contextlib import contextmanager
from typing import Any, AsyncGenerator, Generator

from ..models import NodeType, TraceNode
from ..sqlite_store import SQLiteStore, get_default_store

# Module-level state for patching
_original_openai_create: Any = None
_original_openai_async_create: Any = None
_patch_state: dict[str, Any] = {
    "run_id": None,
    "store": None,
    "patched": False,
}


def patch(run_id: str, store: SQLiteStore | None = None) -> None:
    """Patch OpenAI client to intercept chat.completions.create calls."""
    global _original_openai_create, _original_openai_async_create

    if _patch_state["patched"]:
        return

    try:
        import openai
    except ImportError as e:
        raise ImportError(
            "openai package not found. Install it with: pip install openai"
        ) from e

    _patch_state["run_id"] = run_id
    _patch_state["store"] = store or get_default_store()
    _patch_state["patched"] = True

    # Patch sync version
    _original_openai_create = openai.OpenAI.chat.completions.create

    def patched_create(self: Any, **kwargs: Any) -> Any:
        return _patched_create_sync(self, **kwargs)

    openai.OpenAI.chat.completions.create = patched_create

    # Patch async version
    _original_openai_async_create = openai.AsyncOpenAI.chat.completions.create

    async def patched_async_create(self: Any, **kwargs: Any) -> Any:
        return await _patched_create_async(self, **kwargs)

    openai.AsyncOpenAI.chat.completions.create = patched_async_create


def unpatch() -> None:
    """Restore original OpenAI implementations."""
    global _original_openai_create, _original_openai_async_create

    if not _patch_state["patched"]:
        return

    try:
        import openai
    except ImportError:
        return

    if _original_openai_create is not None:
        openai.OpenAI.chat.completions.create = _original_openai_create
        _original_openai_create = None

    if _original_openai_async_create is not None:
        openai.AsyncOpenAI.chat.completions.create = _original_openai_async_create
        _original_openai_async_create = None

    _patch_state["patched"] = False
    _patch_state["run_id"] = None
    _patch_state["store"] = None


@contextmanager
def patched(run_id: str, store: SQLiteStore | None = None) -> Generator[None, None, None]:
    """Context manager for temporary OpenAI patching."""
    patch(run_id, store)
    try:
        yield
    finally:
        unpatch()


def _patched_create_sync(self: Any, **kwargs: Any) -> Any:
    """Wrapped sync chat.completions.create."""
    run_id = _patch_state["run_id"]
    store = _patch_state["store"]

    if not run_id or not store:
        return _original_openai_create(self, **kwargs)

    # Extract model and messages for recording
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])

    # Create trace node
    node = TraceNode(
        run_id=run_id,
        parent_id=None,
        node_type=NodeType.LLM,
        name=f"openai_{model}",
        start_time=time.time(),
        inputs={
            "messages": messages,
            "model": model,
            **{k: v for k, v in kwargs.items() if k not in ("messages", "model")},
        },
        model_name=model,
    )

    try:
        # Call original
        response = _original_openai_create(self, **kwargs)

        # Extract outputs
        content = None
        finish_reason = None
        if response.choices and len(response.choices) > 0:
            choice = response.choices[0]
            if choice.message and choice.message.content:
                content = choice.message.content
            finish_reason = choice.finish_reason

        outputs: dict[str, Any] = {
            "content": content,
            "finish_reason": finish_reason,
        }

        # Extract token usage if present
        if response.usage:
            node.token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
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
    """Wrapped async chat.completions.create."""
    run_id = _patch_state["run_id"]
    store = _patch_state["store"]

    if not run_id or not store:
        return await _original_openai_async_create(self, **kwargs)

    # Extract model and messages for recording
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])

    # Create trace node
    node = TraceNode(
        run_id=run_id,
        parent_id=None,
        node_type=NodeType.LLM,
        name=f"openai_{model}",
        start_time=time.time(),
        inputs={
            "messages": messages,
            "model": model,
            **{k: v for k, v in kwargs.items() if k not in ("messages", "model")},
        },
        model_name=model,
    )

    try:
        # Call original
        response = await _original_openai_async_create(self, **kwargs)

        # Extract outputs
        content = None
        finish_reason = None
        if response.choices and len(response.choices) > 0:
            choice = response.choices[0]
            if choice.message and choice.message.content:
                content = choice.message.content
            finish_reason = choice.finish_reason

        outputs: dict[str, Any] = {
            "content": content,
            "finish_reason": finish_reason,
        }

        # Extract token usage if present
        if response.usage:
            node.token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        node.finish(outputs)
        store.upsert_node(node)

        return response

    except Exception as e:
        node.error = str(e)
        node.end_time = time.time()
        store.upsert_node(node)
        raise
