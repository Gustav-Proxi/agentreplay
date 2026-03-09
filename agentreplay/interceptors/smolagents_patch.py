"""Wrapper interceptor for smolagents agents."""
from __future__ import annotations

import functools
import time
import traceback
from typing import Any, TypeVar

from ..models import NodeType, Run, RunStatus, TraceNode
from ..sqlite_store import SQLiteStore, get_default_store

T = TypeVar("T")


def wrap(
    agent: Any, run_name: str = "smolagents-run", store: SQLiteStore | None = None
) -> Any:
    """
    Wrap a smolagents agent to record all runs and steps into AgentReplay.

    Args:
        agent: A smolagents MultiStepAgent instance
        run_name: Name for the recorded run
        store: SQLiteStore instance (uses default if None)

    Returns:
        A proxy object with wrapped .run() method

    Raises:
        ImportError: If smolagents is not installed
        TypeError: If agent is not a MultiStepAgent
    """
    try:
        from smolagents import MultiStepAgent
    except ImportError as e:
        raise ImportError(
            "smolagents package not found. Install it with: pip install smolagents"
        ) from e

    try:
        is_multistep_agent = isinstance(agent, MultiStepAgent)
    except TypeError:
        is_multistep_agent = False

    if not is_multistep_agent:
        raise TypeError(
            f"agent must be an instance of smolagents.MultiStepAgent, "
            f"got {type(agent).__name__}"
        )

    store = store or get_default_store()

    class WrappedAgent:
        """Proxy for a smolagents agent with recording enabled."""

        def __init__(self, wrapped_agent: Any, store: SQLiteStore, run_name: str):
            self._agent = wrapped_agent
            self._store = store
            self._run_name = run_name
            self._current_run: Run | None = None
            self._root_node: TraceNode | None = None

        def run(self, task: str) -> Any:
            """Execute agent.run(task) with full tracing."""
            import time as time_module

            # Create run
            self._current_run = Run(
                name=self._run_name,
                start_time=time_module.time(),
            )
            self._store.upsert_run(self._current_run)

            # Create root node
            self._root_node = TraceNode(
                run_id=self._current_run.id,
                parent_id=None,
                node_type=NodeType.AGENT,
                name="smolagents_run",
                start_time=time_module.time(),
                inputs={"task": task},
            )
            self._store.upsert_node(self._root_node)

            try:
                # Wrap the step method if it exists
                original_step = None
                if hasattr(self._agent, "_step"):
                    original_step = self._agent._step
                    self._agent._step = functools.partial(
                        self._wrapped_step, original_step=original_step
                    )
                elif hasattr(self._agent, "step"):
                    original_step = self._agent.step
                    self._agent.step = functools.partial(
                        self._wrapped_step, original_step=original_step
                    )

                try:
                    # Call original run
                    result = self._agent.run(task)

                    # Finish root node with result
                    self._root_node.finish({"result": str(result)})
                    self._store.upsert_node(self._root_node)

                    # Finish run
                    self._current_run.finish()
                    self._store.upsert_run(self._current_run)

                    return result

                finally:
                    # Restore original step method
                    if original_step is not None:
                        if hasattr(self._agent, "_step"):
                            self._agent._step = original_step
                        elif hasattr(self._agent, "step"):
                            self._agent.step = original_step

            except Exception as e:
                # Record error in root node
                error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
                self._root_node.error = error_msg
                self._root_node.end_time = time.time()
                self._store.upsert_node(self._root_node)

                # Record error in run
                self._current_run.finish(error=error_msg)
                self._store.upsert_run(self._current_run)

                raise

        def _wrapped_step(self, original_step: Any, *args: Any, **kwargs: Any) -> Any:
            """Wrap individual step calls."""
            step_node = TraceNode(
                run_id=self._current_run.id,
                parent_id=self._root_node.id,
                node_type=NodeType.CHAIN,
                name="step",
                start_time=time.time(),
                inputs={"args": str(args), "kwargs": str(kwargs)},
            )
            self._store.upsert_node(step_node)

            try:
                result = original_step(*args, **kwargs)
                step_node.finish({"result": str(result)})
                self._store.upsert_node(step_node)
                return result
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                step_node.error = error_msg
                step_node.end_time = time.time()
                self._store.upsert_node(step_node)
                raise

        def __getattr__(self, name: str) -> Any:
            """Forward all other attributes to the wrapped agent."""
            return getattr(self._agent, name)

    return WrappedAgent(agent, store, run_name)
