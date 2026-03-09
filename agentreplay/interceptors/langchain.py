"""LangChain callback handler that records all agent steps into AgentReplay."""
from __future__ import annotations

import time
import uuid
from typing import Any, Union
from uuid import UUID

from ..models import NodeType, Run, TraceNode
from ..sqlite_store import SQLiteStore, get_default_store

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
except ImportError as e:
    raise ImportError(
        "langchain-core is required for the LangChain interceptor. "
        "Install it with: pip install agentreplay[langchain]"
    ) from e


class AgentReplayCallback(BaseCallbackHandler):
    """Drop-in LangChain callback that captures every step into AgentReplay.

    Usage::

        from agentreplay.interceptors.langchain import AgentReplayCallback

        cb = AgentReplayCallback()
        agent.invoke({"input": "..."}, config={"callbacks": [cb]})
        cb.serve()   # open dashboard at http://localhost:7474
    """

    def __init__(
        self,
        run_name: str = "langchain-run",
        store: SQLiteStore | None = None,
    ) -> None:
        super().__init__()
        self._store = store or get_default_store()
        self._run = Run(name=run_name, start_time=time.time())
        self._store.upsert_run(self._run)

        # Maps LangChain's internal run UUIDs → our TraceNode ids
        self._node_map: dict[UUID, str] = {}
        # Maps LangChain's run UUID → parent run UUID
        self._parent_map: dict[UUID, UUID | None] = {}

    @property
    def run_id(self) -> str:
        return self._run.id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _node_id(self, lc_run_id: UUID) -> str:
        if lc_run_id not in self._node_map:
            self._node_map[lc_run_id] = str(uuid.uuid4())
        return self._node_map[lc_run_id]

    def _parent_node_id(self, parent_run_id: UUID | None) -> str | None:
        if parent_run_id is None:
            return None
        return self._node_map.get(parent_run_id)

    # ------------------------------------------------------------------
    # Chain
    # ------------------------------------------------------------------

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("id", ["unknown"])[-1]
        node = TraceNode(
            id=self._node_id(run_id),
            run_id=self._run.id,
            parent_id=self._parent_node_id(parent_run_id),
            node_type=NodeType.CHAIN,
            name=name,
            start_time=time.time(),
            inputs=inputs,
        )
        self._store.upsert_node(node)

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        node = self._get_node(run_id)
        if node:
            node.finish(outputs=outputs)
            self._store.upsert_node(node)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        node = self._get_node(run_id)
        if node:
            node.finish(outputs={}, error=str(error))
            self._store.upsert_node(node)

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name") or serialized.get("id", ["llm"])[-1]
        node = TraceNode(
            id=self._node_id(run_id),
            run_id=self._run.id,
            parent_id=self._parent_node_id(parent_run_id),
            node_type=NodeType.LLM,
            name=name,
            start_time=time.time(),
            inputs={"prompts": prompts},
            model_name=serialized.get("kwargs", {}).get("model_name"),
        )
        self._store.upsert_node(node)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        node = self._get_node(run_id)
        if node:
            generations = [
                [g.text for g in gen_list] for gen_list in response.generations
            ]
            token_usage: dict[str, int] | None = None
            if response.llm_output:
                usage = response.llm_output.get("token_usage", {})
                if usage:
                    token_usage = {str(k): int(v) for k, v in usage.items()}
            node.finish(outputs={"generations": generations})
            node.token_usage = token_usage
            self._store.upsert_node(node)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        node = self._get_node(run_id)
        if node:
            node.finish(outputs={}, error=str(error))
            self._store.upsert_node(node)

    # ------------------------------------------------------------------
    # Tool
    # ------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name", "unknown_tool")
        node = TraceNode(
            id=self._node_id(run_id),
            run_id=self._run.id,
            parent_id=self._parent_node_id(parent_run_id),
            node_type=NodeType.TOOL,
            name=name,
            start_time=time.time(),
            inputs={"input": input_str},
        )
        self._store.upsert_node(node)

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        node = self._get_node(run_id)
        if node:
            node.finish(outputs={"output": output})
            self._store.upsert_node(node)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        node = self._get_node(run_id)
        if node:
            node.finish(outputs={}, error=str(error))
            self._store.upsert_node(node)

    # ------------------------------------------------------------------
    # Agent action
    # ------------------------------------------------------------------

    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        action_run_id = uuid.uuid4()
        node = TraceNode(
            id=self._node_id(action_run_id),
            run_id=self._run.id,
            parent_id=self._parent_node_id(parent_run_id),
            node_type=NodeType.AGENT,
            name=f"action:{getattr(action, 'tool', 'unknown')}",
            start_time=time.time(),
            inputs={"tool": getattr(action, "tool", ""), "tool_input": getattr(action, "tool_input", "")},
        )
        node.finish(outputs={})
        self._store.upsert_node(node)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_node(self, lc_run_id: UUID) -> TraceNode | None:
        node_id = self._node_map.get(lc_run_id)
        if not node_id:
            return None
        return self._store.get_node(self._run.id, node_id)

    def serve(self, port: int = 7474) -> None:
        """Convenience method to open the dashboard for this run."""
        from ..server import serve

        serve(port=port, open_browser=True)
