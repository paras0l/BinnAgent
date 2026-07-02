from collections.abc import Awaitable, Callable
from typing import Any
import uuid

import httpx

from src.graph.main_graph import daily_lesson_graph
from src.simulation.assertions import AssertionEngine
from src.simulation.evaluator import SimulationEvaluator
from src.simulation.learner_agent import SimulatedLearnerAgent
from src.simulation.persona import LearnerPersona
from src.simulation.scenario import (
    SimulationReport,
    SimulationScenario,
    SimulationStep,
    SimulationStepResult,
)


GraphInvoker = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class ScenarioRunner:
    """Executes deterministic learner scenarios against BinnAgent APIs and graph."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        graph_invoker: GraphInvoker | None = None,
        seed: int = 42,
    ) -> None:
        self.client = client
        self.graph_invoker = graph_invoker or self._invoke_daily_graph
        self.seed = seed
        self.assertions = AssertionEngine()
        self.evaluator = SimulationEvaluator()
        self.api_calls = 0
        self.api_successes = 0
        self.agent_triggers = 0
        self.memory_writes = 0
        self.runtime_metrics: dict[str, float | int] = {
            "episode_count": 0,
            "completed_episode_count": 0,
            "failed_episode_count": 0,
            "verification_pass_count": 0,
            "verification_fail_count": 0,
            "avg_tool_latency_ms": 0,
        }

    async def run(
        self,
        *,
        scenario: SimulationScenario,
        persona: LearnerPersona,
    ) -> SimulationReport:
        context: dict[str, Any] = {"persona": persona.id, "vocabulary_items": []}
        learner_agent = SimulatedLearnerAgent(persona=persona, seed=self.seed)
        step_results: list[SimulationStepResult] = []

        for step in scenario.steps:
            result = await self._run_step(step, context, learner_agent)
            step_results.append(result)
            if result.status == "failed":
                break

        return self.evaluator.build_report(
            persona_id=persona.id,
            scenario_id=scenario.id,
            steps=step_results,
            api_calls=self.api_calls,
            api_successes=self.api_successes,
            agent_triggers=self.agent_triggers,
            memory_writes=self.memory_writes,
            runtime_metrics=self.runtime_metrics,
        )

    async def _run_step(
        self,
        step: SimulationStep,
        context: dict[str, Any],
        learner_agent: SimulatedLearnerAgent,
    ) -> SimulationStepResult:
        try:
            output = await self._dispatch(step, context, learner_agent)
            assertion_results = self.assertions.evaluate(step.assertions, output, context)
            failures = [result.message for result in assertion_results if not result.passed]
            return SimulationStepResult(
                name=step.name,
                status="failed" if failures else "passed",
                evidence=_evidence_for_output(output),
                output=_public_output(output),
                failures=failures,
            )
        except Exception as exc:
            return SimulationStepResult(
                name=step.name,
                status="failed",
                failures=[f"{type(exc).__name__}: {exc}"],
            )

    async def _dispatch(
        self,
        step: SimulationStep,
        context: dict[str, Any],
        learner_agent: SimulatedLearnerAgent,
    ) -> dict[str, Any]:
        if step.action == "create_learner":
            return await self._create_learner(context)
        if step.action == "chat":
            return await self._chat(step, context)
        if step.action == "memory_summary":
            return await self._memory_summary(context)
        if step.action == "daily_graph":
            return await self._daily_graph(context)
        if step.action == "list_vocabulary":
            return await self._list_vocabulary(context)
        if step.action == "add_vocabulary":
            return await self._add_vocabulary(step, context)
        if step.action == "vocabulary_practice":
            return await self._vocabulary_practice(step, context, learner_agent)
        if step.action == "daily_plan":
            return await self._daily_plan(step, context)
        if step.action == "start_daily_lesson":
            return await self._start_daily_lesson(step, context)
        if step.action == "submit_daily_lesson_answer":
            return await self._submit_daily_lesson_answer(step, context, learner_agent)
        if step.action == "fetch_episode_trace":
            return await self._fetch_episode_trace(context)
        if step.action == "fetch_verification_report":
            return await self._fetch_verification_report(context)
        raise ValueError(f"Unsupported simulation action: {step.action}")

    async def _create_learner(self, context: dict[str, Any]) -> dict[str, Any]:
        persona_id = str(context["persona"])
        response = await self._request(
            "POST",
            "/api/learners",
            json={"nickname": f"sim-{persona_id}", "email": f"{uuid.uuid4().hex}@simulation.local"},
        )
        payload = _json_or_empty(response)
        learner_id = payload.get("id")
        if learner_id:
            context["learner_id"] = learner_id
        return {"status_code": response.status_code, "json": payload}

    async def _chat(self, step: SimulationStep, context: dict[str, Any]) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        body = {"learner_id": learner_id, "message": step.payload.get("message", "I want to learn.")}
        if step.payload.get("skill_focus"):
            body["skill_focus"] = step.payload["skill_focus"]
        if step.payload.get("skill_id"):
            body["skill_id"] = step.payload["skill_id"]
        response = await self._request("POST", "/api/chat/send", json=body)
        payload = _json_or_empty(response)
        if payload.get("thread_id"):
            context["thread_id"] = payload["thread_id"]
        if payload.get("skill_id") == "vocabulary_deposit":
            self.agent_triggers += 1
        vocabulary_agent = _summarize_skill_events(payload.get("skill_events", []))
        return {
            "status_code": response.status_code,
            "json": payload,
            "vocabulary_agent": vocabulary_agent,
        }

    async def _memory_summary(self, context: dict[str, Any]) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        response = await self._request("GET", f"/api/learners/{learner_id}/memory/summary")
        payload = _json_or_empty(response)
        total_vocab = _lookup_int(payload, ["vocabulary", "total"], ["total_vocab"])
        context["memory_summary"] = payload
        self.memory_writes += int(_lookup_int(payload, ["events", "total"], ["total_events"]) or 0)
        return {"status_code": response.status_code, "json": payload, "memory": {"total_vocab": total_vocab}}

    async def _daily_graph(self, context: dict[str, Any]) -> dict[str, Any]:
        state = {
            "user_id": _require_context(context, "learner_id"),
            "thread_id": context.get("thread_id") or str(uuid.uuid4()),
            "target_exam": "CET6",
            "current_level": "intermediate",
            "daily_time_budget": 20,
            "active_skill": "vocabulary",
            "messages": [{"role": "user", "content": "I want today's vocabulary lesson."}],
        }
        graph_result = await self.graph_invoker(state)
        context["daily_graph"] = graph_result
        return {"graph": graph_result}

    async def _list_vocabulary(self, context: dict[str, Any]) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        response = await self._request("GET", f"/api/learners/{learner_id}/vocabulary")
        payload = _json_or_empty(response)
        total = len(payload) if isinstance(payload, list) else 0
        context["vocabulary_items"] = payload if isinstance(payload, list) else []
        return {"status_code": response.status_code, "json": payload, "vocabulary": {"total": total}}

    async def _add_vocabulary(self, step: SimulationStep, context: dict[str, Any]) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        created: list[dict[str, Any]] = []
        for word in step.payload.get("words", []):
            response = await self._request(
                "POST",
                f"/api/learners/{learner_id}/vocabulary/add",
                json={"word": word, "level": "simulation", "meanings": [f"simulation meaning for {word}"]},
            )
            payload = _json_or_empty(response)
            if response.status_code < 400:
                created.append(payload)
        context["vocabulary_items"] = created
        return {"vocabulary": {"total": len(created)}, "items": created}

    async def _vocabulary_practice(
        self,
        step: SimulationStep,
        context: dict[str, Any],
        learner_agent: SimulatedLearnerAgent,
    ) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        mode = step.payload.get("mode", "new")
        response = await self._request(
            "POST",
            f"/api/learners/{learner_id}/vocabulary/sessions",
            json={"mode": mode, "prompt_mode": "meaning", "limit": step.payload.get("limit", 1)},
        )
        session = _json_or_empty(response)
        session_id = session["session_id"]
        next_response = await self._request("GET", f"/api/learners/{learner_id}/vocabulary/sessions/{session_id}/next")
        task = _json_or_empty(next_response)
        word = task.get("display_word") or task.get("word") or ""
        item_id = task["vocabulary_item_id"]
        if mode == "spelling":
            answer = learner_agent.answer_spelling(word)
            body: dict[str, Any] = {
                "vocabulary_item_id": item_id,
                "idempotency_key": f"sim-{uuid.uuid4().hex[:12]}",
                "answer": answer,
                "hint_count": 1 if answer != word else 0,
                "response_time_ms": 2100,
            }
        else:
            answer = learner_agent.answer_vocabulary(word, prompt_type=task.get("prompt_mode", "meaning"))
            body = {
                "vocabulary_item_id": item_id,
                "idempotency_key": f"sim-{uuid.uuid4().hex[:12]}",
                "answer": answer,
                "rating": 4 if answer.casefold() == str(word).casefold() else 2,
                "hint_count": 0,
                "response_time_ms": 1600,
            }
        attempt_response = await self._request(
            "POST",
            f"/api/learners/{learner_id}/vocabulary/sessions/{session_id}/attempts",
            json=body,
        )
        attempt = _json_or_empty(attempt_response)
        if attempt_response.status_code < 400:
            self.memory_writes += 1
        await self._request(
            "POST",
            f"/api/learners/{learner_id}/vocabulary/sessions/{session_id}/advance",
            json={"vocabulary_item_id": item_id},
        )
        summary_response = await self._request(
            "GET", f"/api/learners/{learner_id}/vocabulary/sessions/{session_id}/summary"
        )
        summary = _json_or_empty(summary_response)
        detail_response = await self._request("GET", f"/api/learners/{learner_id}/vocabulary/{item_id}")
        detail = _json_or_empty(detail_response)
        return {
            "session": session,
            "task": task,
            "attempt": attempt,
            "summary": summary,
            "detail": detail,
        }

    async def _daily_plan(self, step: SimulationStep, context: dict[str, Any]) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        params = {"learner_id": learner_id}
        if step.payload.get("current_curriculum_node_id"):
            params["current_curriculum_node_id"] = step.payload["current_curriculum_node_id"]
        response = await self._request("GET", "/api/recommendations/daily-plan", params=params)
        payload = _json_or_empty(response)
        context["recommendation_plan"] = payload
        tasks = payload.get("tasks") if isinstance(payload, dict) else []
        if tasks:
            context["selected_task"] = tasks[0].get("task_spec")
        return {"status_code": response.status_code, "json": payload, "recommendation_plan": payload}

    async def _start_daily_lesson(self, step: SimulationStep, context: dict[str, Any]) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        body = dict(step.payload)
        response = await self._request(
            "POST",
            f"/api/learners/{learner_id}/daily-lessons/start",
            json=body,
        )
        payload = _json_or_empty(response)
        if payload.get("episode_id"):
            context["episode_id"] = payload["episode_id"]
        context["daily_lesson_start"] = payload
        return {"status_code": response.status_code, "json": payload, "daily_lesson": payload}

    async def _submit_daily_lesson_answer(
        self,
        step: SimulationStep,
        context: dict[str, Any],
        learner_agent: SimulatedLearnerAgent,
    ) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        episode_id = _require_context(context, "episode_id")
        answer = step.payload.get("answer")
        if answer is None:
            options = ((context.get("daily_lesson_start") or {}).get("initial_payload") or {}).get("options") or []
            answer = options[0] if options else learner_agent.answer_vocabulary("morning")
        response = await self._request(
            "POST",
            f"/api/learners/{learner_id}/daily-lessons/{episode_id}/answer",
            json={"answer": answer, "metadata": step.payload.get("metadata", {})},
        )
        payload = _json_or_empty(response)
        context["daily_lesson_answer"] = payload
        return {"status_code": response.status_code, "json": payload, "answer": payload}

    async def _fetch_episode_trace(self, context: dict[str, Any]) -> dict[str, Any]:
        episode_id = _require_context(context, "episode_id")
        response = await self._request("GET", f"/api/runtime/episodes/{episode_id}")
        payload = _json_or_empty(response)
        context["episode_trace"] = payload
        self._update_runtime_metrics_from_trace(payload)
        return {"status_code": response.status_code, "json": payload, "episode_trace": payload}

    async def _fetch_verification_report(self, context: dict[str, Any]) -> dict[str, Any]:
        episode_id = _require_context(context, "episode_id")
        response = await self._request("GET", f"/api/runtime/episodes/{episode_id}/verification")
        payload = _json_or_empty(response)
        context["verification_report"] = payload
        status = payload.get("status") if isinstance(payload, dict) else None
        if status == "passed":
            self.runtime_metrics["verification_pass_count"] += 1
        elif status == "failed":
            self.runtime_metrics["verification_fail_count"] += 1
        return {"status_code": response.status_code, "json": payload, "verification_report": payload}

    def _update_runtime_metrics_from_trace(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        episode = payload.get("episode") or {}
        status = episode.get("status")
        self.runtime_metrics["episode_count"] += 1
        if status == "completed":
            self.runtime_metrics["completed_episode_count"] += 1
        elif status == "failed":
            self.runtime_metrics["failed_episode_count"] += 1
        tool_calls = payload.get("tool_calls") or []
        latencies = [
            item.get("latency_ms")
            for item in tool_calls
            if isinstance(item, dict) and isinstance(item.get("latency_ms"), int | float)
        ]
        if latencies:
            self.runtime_metrics["avg_tool_latency_ms"] = sum(latencies) / len(latencies)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.api_calls += 1
        response = await self.client.request(method, url, **kwargs)
        if response.status_code < 500:
            self.api_successes += 1
        return response

    @staticmethod
    async def _invoke_daily_graph(state: dict[str, Any]) -> dict[str, Any]:
        return await daily_lesson_graph.ainvoke(state)


def _require_context(context: dict[str, Any], key: str) -> str:
    value = context.get(key)
    if not value:
        raise ValueError(f"Simulation context missing {key}")
    return str(value)


def _json_or_empty(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {}


def _summarize_skill_events(events: Any) -> dict[str, int]:
    if not isinstance(events, list):
        return {"saved_count": 0, "skipped_count": 0, "failed_count": 0}
    saved = 0
    skipped = 0
    failed = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        saved += int(event.get("saved_count") or 0)
        skipped += int(event.get("skipped_count") or 0)
        failed += 1 if event.get("status") == "failed" or event.get("failed") else 0
    return {"saved_count": saved, "skipped_count": skipped, "failed_count": failed}


def _lookup_int(payload: Any, *paths: list[str]) -> int:
    for path in paths:
        current = payload
        for part in path:
            current = current.get(part) if isinstance(current, dict) else None
            if current is None:
                break
        if isinstance(current, int):
            return current
    return 0


def _evidence_for_output(output: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    json_payload = output.get("json")
    if isinstance(json_payload, dict):
        for key in ("id", "thread_id", "message_id", "session_id", "attempt_id", "episode_id"):
            if json_payload.get(key):
                evidence.append(f"{key}:{json_payload[key]}")
    if "episode_trace" in output:
        evidence.append("episode_trace:fetched")
    if "verification_report" in output:
        evidence.append("verification_report:fetched")
    if "graph" in output:
        evidence.append("daily_graph:completed")
    if "attempt" in output and isinstance(output["attempt"], dict):
        attempt_id = output["attempt"].get("attempt_id")
        if attempt_id:
            evidence.append(f"attempt:{attempt_id}")
    return evidence


def _public_output(output: dict[str, Any]) -> dict[str, Any]:
    public = dict(output)
    json_payload = public.get("json")
    if isinstance(json_payload, dict) and "reply" in json_payload:
        public["json"] = {
            key: value
            for key, value in json_payload.items()
            if key in {"thread_id", "message_id", "skill_id", "skill_name", "skill_events"}
        }
    return public
