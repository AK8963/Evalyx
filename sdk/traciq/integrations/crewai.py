"""
CrewAI integration — automatically trace CrewAI agent runs.

Usage:
    from sdk.traciq.integrations.crewai import trace_crew

    @trace_crew(client=bt_client, project_id="my-project")
    def run_my_crew():
        crew = Crew(agents=[...], tasks=[...])
        return crew.kickoff()

    # Or wrap an existing crew instance:
    from sdk.traciq.integrations.crewai import TraceIQCrewCallback
    crew = Crew(agents=[...], tasks=[...], callbacks=[TraceIQCrewCallback(client, project_id)])
"""

import functools
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def trace_crew(client, project_id: str, name: Optional[str] = None, metadata: Optional[dict] = None):
    """
    Decorator that wraps a function which returns a CrewAI result.
    Traces the overall execution time, inputs and outputs.

    Example:
        @trace_crew(client=bt_client, project_id="proj-123")
        def run():
            return Crew(agents=[...], tasks=[...]).kickoff()
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            trace_name = name or fn.__name__
            start = time.perf_counter()
            error = None
            result = None
            try:
                result = fn(*args, **kwargs)
                return result
            except Exception as e:
                error = e
                raise
            finally:
                latency_ms = (time.perf_counter() - start) * 1000
                try:
                    client.trace(
                        project_id=project_id,
                        input_data={"function": trace_name, "args": str(args)[:500], "kwargs": str(kwargs)[:500]},
                        output_data={"result": str(result)[:2000]} if result is not None else None,
                        model="crewai",
                        latency_ms=round(latency_ms, 2),
                        status="error" if error else "success",
                        error_message=str(error) if error else None,
                        meta={
                            "framework": "crewai",
                            "trace_name": trace_name,
                            **(metadata or {}),
                        },
                    )
                except Exception as trace_err:
                    logger.warning(f"[TraceIQ] Failed to record CrewAI trace: {trace_err}")
        return wrapper
    return decorator


class TraceIQCrewCallback:
    """
    CrewAI callback that traces individual agent/task executions.

    Attach as a callback to your Crew:
        crew = Crew(..., callbacks=[TraceIQCrewCallback(client, project_id)])

    CrewAI's callback interface calls on_task_start / on_task_end / on_agent_action.
    We implement a duck-typed interface compatible with CrewAI 0.28+.
    """

    def __init__(self, client, project_id: str, metadata: Optional[dict] = None):
        self._client = client
        self._project_id = project_id
        self._metadata = metadata or {}
        self._task_starts: Dict[str, float] = {}

    # ── CrewAI callback hooks ──────────────────────────────────────────────

    def on_task_start(self, task: Any = None, **kwargs) -> None:
        task_id = _task_id(task)
        self._task_starts[task_id] = time.perf_counter()

    def on_task_end(self, task: Any = None, output: Any = None, **kwargs) -> None:
        task_id = _task_id(task)
        start = self._task_starts.pop(task_id, None)
        latency_ms = (time.perf_counter() - start) * 1000 if start else None

        task_desc = _get_attr(task, "description") or str(task)[:200]
        try:
            self._client.trace(
                project_id=self._project_id,
                input_data={"task": task_desc},
                output_data={"output": str(output)[:2000] if output is not None else None},
                model="crewai/task",
                latency_ms=round(latency_ms, 2) if latency_ms else None,
                status="success",
                meta={"framework": "crewai", "type": "task", **self._metadata},
            )
        except Exception as e:
            logger.warning(f"[TraceIQ] CrewAI task trace failed: {e}")

    def on_agent_action(self, agent: Any = None, action: Any = None, **kwargs) -> None:
        agent_role = _get_attr(agent, "role") or str(agent)[:100]
        action_tool = _get_attr(action, "tool") or str(action)[:100]
        action_input = _get_attr(action, "tool_input") or ""
        try:
            self._client.trace(
                project_id=self._project_id,
                input_data={"agent": agent_role, "tool": action_tool, "tool_input": str(action_input)[:500]},
                output_data=None,
                model="crewai/agent",
                status="success",
                meta={"framework": "crewai", "type": "agent_action", **self._metadata},
            )
        except Exception as e:
            logger.warning(f"[TraceIQ] CrewAI agent action trace failed: {e}")

    def on_crew_start(self, crew: Any = None, **kwargs) -> None:
        logger.debug("[TraceIQ] CrewAI crew started")

    def on_crew_end(self, crew: Any = None, output: Any = None, **kwargs) -> None:
        logger.debug("[TraceIQ] CrewAI crew finished")


def _task_id(task: Any) -> str:
    return str(getattr(task, "id", None) or id(task))


def _get_attr(obj: Any, attr: str, default=None):
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default
