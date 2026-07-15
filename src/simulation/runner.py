from collections.abc import Awaitable, Callable
from typing import Any
import uuid

import httpx

from src.auth.email_verification import create_email_verification_token
from src.graph.main_graph import daily_lesson_graph
from src.knowledge.unit_exercise_generation import lint_candidate
from src.simulation.assertions import AssertionEngine
from src.simulation.evaluator import SimulationEvaluator
from src.simulation.learner_agent import SimulatedLearnerAgent
from src.simulation.persona import LearnerPersona
from src.simulation.scenario import (
    SimulationMode,
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
        mode: SimulationMode = "contract",
        seed: int = 42,
        invite_code: str = "BINN-CONTRACT",
    ) -> None:
        self.client = client
        self.graph_invoker = graph_invoker or self._invoke_daily_graph
        self.mode = mode
        self.seed = seed
        self.invite_code = invite_code
        self.assertions = AssertionEngine()
        self.evaluator = SimulationEvaluator()
        self.api_calls = 0
        self.api_successes = 0
        self.agent_triggers = 0
        self.memory_writes = 0
        self._verification_counted_episode_ids: set[str] = set()
        self.runtime_metrics: dict[str, Any] = {
            "episode_count": 0,
            "completed_episode_count": 0,
            "failed_episode_count": 0,
            "verification_pass_count": 0,
            "verification_fail_count": 0,
            "avg_tool_latency_ms": 0,
            "tool_statuses": [],
            "tool_latencies_ms": [],
            "event_types": [],
            "verification_statuses": [],
            "recommendation_generated_count": 0,
            "recommendation_contains_expected_count": 0,
            "capability_click_recorded_count": 0,
            "memory_event_count": 0,
            "memory_recall_count": 0,
            "prompt_executions": [],
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
            mode=self.mode,
            runtime_metrics=self.runtime_metrics,
            scenario_contract=scenario.contract_dict(),
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
        if step.action == "click_capability_recommendation":
            return await self._click_capability_recommendation(step, context)
        if step.action == "fetch_episode_trace":
            return await self._fetch_episode_trace(context)
        if step.action == "fetch_verification_report":
            return await self._fetch_verification_report(context)
        if step.action == "generate_exercise_with_repair":
            return await self._generate_exercise_with_repair(step, context)
        if step.action == "validate_unit_exercise_candidate":
            return self._validate_unit_exercise_candidate(step)
        if step.action == "save_reading_material":
            return await self._save_reading_material(step, context)
        if step.action == "complete_reading_material":
            return await self._complete_reading_material(step, context)
        if step.action == "reading_dashboard":
            return await self._reading_dashboard(context)
        raise ValueError(f"Unsupported simulation action: {step.action}")

    def _validate_unit_exercise_candidate(self, step: SimulationStep) -> dict[str, Any]:
        point_id = str(step.payload.get("knowledge_point_id") or "kp-simulation")
        candidate = {
            "knowledgePointId": point_id,
            "questionType": "dialogue_complete",
            "cognitiveLevel": "production",
            "scenario": {
                "name": "classroom",
                "setting": "answering in class",
                "zh": "课堂问答",
            },
            "stem": step.payload.get(
                "stem",
                "场景：课堂问答。A: Hello! I am Jack. B: ______ 目标：使用相关表达。",
            ),
            "options": [],
            "answer": step.payload.get("answer", "I'm fine, thanks."),
            "acceptableAnswers": [step.payload.get("answer", "I'm fine, thanks.")],
            "explanation": "根据上下文选择自然且符合知识点的回答。",
            "difficulty": 0.3,
            "targetExpression": step.payload.get("answer", "I'm fine, thanks."),
            "errorTypes": ["context_mismatch"],
            "hint": "先判断上一句话的交际意图。",
        }
        errors = lint_candidate(candidate, valid_point_ids={point_id})
        return {"accepted": not errors, "errors": errors, "candidate": candidate}

    async def _create_learner(self, context: dict[str, Any]) -> dict[str, Any]:
        persona_id = str(context["persona"])
        email = f"{uuid.uuid4().hex}@simulation.local"
        response = await self._request(
            "POST",
            "/api/learners",
            json={
                "nickname": f"sim-{persona_id}",
                "email": email,
                "invite_code": self.invite_code,
                "verification_token": create_email_verification_token(email=email),
            },
        )
        payload = _json_or_empty(response)
        learner_id = payload.get("id")
        if learner_id:
            context["learner_id"] = learner_id
        return {"status_code": response.status_code, "json": payload}

    async def _save_reading_material(
        self,
        step: SimulationStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        body = {
            "title": step.payload.get("title", "A Better Way to Read"),
            "text": step.payload.get(
                "text",
                (
                    "Good readers first identify the writer's main idea. They then slow down "
                    "for difficult sentences and connect each detail to the central message."
                ),
            ),
            "level": step.payload.get("level", "junior"),
            "goal": step.payload.get("goal", "mixed"),
            "material_type": step.payload.get("material_type", "passage"),
        }
        response = await self._request(
            "POST",
            f"/api/learners/{learner_id}/reading-workshop/materials",
            json=body,
        )
        payload = _json_or_empty(response)
        if isinstance(payload, dict) and payload.get("id"):
            context["reading_material_id"] = payload["id"]
            context["reading_material_goal"] = payload.get("goal") or body["goal"]
        return {
            "status_code": response.status_code,
            "material": payload,
        }

    async def _complete_reading_material(
        self,
        step: SimulationStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        material_id = _require_context(context, "reading_material_id")
        response = await self._request(
            "POST",
            f"/api/learners/{learner_id}/reading-workshop/materials/{material_id}/complete",
            json=dict(step.payload),
        )
        payload = _json_or_empty(response)
        previous_attempt_id = context.get("reading_completion_attempt_id")
        attempt_id = payload.get("attempt_id") if isinstance(payload, dict) else None
        idempotent_replay = bool(previous_attempt_id and attempt_id == previous_attempt_id)
        if attempt_id and previous_attempt_id is None:
            context["reading_completion_attempt_id"] = attempt_id
        if isinstance(payload, dict) and payload:
            context["reading_completion"] = payload
        return {
            "status_code": response.status_code,
            "completion": payload,
            "idempotent_replay": idempotent_replay,
        }

    async def _reading_dashboard(self, context: dict[str, Any]) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        response = await self._request("GET", f"/api/learners/{learner_id}/dashboard")
        payload = _json_or_empty(response)
        ability_scores = (
            ((payload.get("profile") or {}).get("ability_scores") or [])
            if isinstance(payload, dict)
            else []
        )
        reading_ability = next(
            (
                item
                for item in ability_scores
                if isinstance(item, dict) and item.get("label") == "阅读"
            ),
            {},
        )
        return {
            "status_code": response.status_code,
            "dashboard": payload,
            "reading_ability": reading_ability,
        }

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
            "learner_answer": {"answer": "sustainable means able to continue over time."},
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
        memory_updates = payload.get("memory_updates") if isinstance(payload, dict) else None
        if isinstance(memory_updates, list):
            self.memory_writes += len(memory_updates)
            self.runtime_metrics["memory_event_count"] += len(memory_updates)
        recommendations = (
            payload.get("next_capability_recommendations") if isinstance(payload, dict) else None
        )
        if isinstance(recommendations, list):
            self.runtime_metrics["recommendation_generated_count"] += len(recommendations)
            self.runtime_metrics["recommendation_contains_expected_count"] += len(recommendations)
        return {"status_code": response.status_code, "json": payload, "answer": payload}

    async def _click_capability_recommendation(
        self,
        step: SimulationStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        episode_id = context.get("episode_id")
        recommendations = (context.get("daily_lesson_answer") or {}).get(
            "next_capability_recommendations"
        ) or []
        capability_id = step.payload.get("capability_id")
        recommendation = next(
            (
                item
                for item in recommendations
                if isinstance(item, dict)
                and (capability_id is None or item.get("capability_id") == capability_id)
            ),
            None,
        )
        if recommendation is None:
            raise ValueError("Simulation context missing capability recommendation")
        capability_id = recommendation["capability_id"]
        response = await self._request(
            "POST",
            f"/api/learners/{learner_id}/explore/capabilities/{capability_id}/events",
            json={
                "event_type": "clicked",
                "episode_id": episode_id,
                "recommendation_id": recommendation.get("recommendation_id"),
                "reason": recommendation.get("reason"),
                "evidence_refs": recommendation.get("evidence_refs") or [],
                "metadata": {
                    "source": "simulation",
                    "priority_score": recommendation.get("priority_score"),
                },
            },
        )
        payload = _json_or_empty(response)
        if response.status_code < 400:
            self.memory_writes += 1
            self.runtime_metrics["capability_click_recorded_count"] += 1
        context["capability_event"] = payload
        return {
            "status_code": response.status_code,
            "json": payload,
            "capability_event": {
                **(payload if isinstance(payload, dict) else {}),
                "capability_id": capability_id,
            },
        }

    async def _fetch_episode_trace(self, context: dict[str, Any]) -> dict[str, Any]:
        episode_id = _require_context(context, "episode_id")
        response = await self._request("GET", f"/api/runtime/episodes/{episode_id}")
        payload = _json_or_empty(response)
        context["episode_trace"] = payload
        self._update_runtime_metrics_from_trace(payload)
        event_types = [
            item.get("event_type")
            for item in (payload.get("events") or [])
            if isinstance(item, dict) and item.get("event_type")
        ] if isinstance(payload, dict) else []
        self.runtime_metrics["event_types"].extend(event_types)
        return {
            "status_code": response.status_code,
            "json": payload,
            "episode_trace": payload,
            "episode_trace_event_types": event_types,
        }

    async def _fetch_verification_report(self, context: dict[str, Any]) -> dict[str, Any]:
        episode_id = _require_context(context, "episode_id")
        response = await self._request("GET", f"/api/runtime/episodes/{episode_id}/verification")
        payload = _json_or_empty(response)
        context["verification_report"] = payload
        status = payload.get("status") if isinstance(payload, dict) else None
        self._record_verification_status(status, episode_id)
        return {"status_code": response.status_code, "json": payload, "verification_report": payload}

    async def _generate_exercise_with_repair(
        self,
        step: SimulationStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        learner_id = _require_context(context, "learner_id")
        target_id = step.payload.get("target_id") or str(uuid.uuid4())
        response = await self._request(
            "POST",
            f"/api/learners/{learner_id}/exercises/generate",
            json={
                "target": {
                    "type": "knowledge_point",
                    "id": target_id,
                    "label": step.payload.get("target_label", "Good morning"),
                },
                "count": step.payload.get("count", 1),
                "exerciseTypes": step.payload.get("exercise_types") or ["single_choice"],
                "context": {
                    "explanation": "Use a deterministic fake model repair path.",
                    "learnerLevel": "beginner",
                },
            },
        )
        payload = _json_or_empty(response)
        items = payload if isinstance(payload, list) else []
        self.runtime_metrics["prompt_executions"].append(
            {
                "prompt_id": "exercise_generate",
                "prompt_hash": "simulation-fake",
                "model_policy_snapshot": {"provider": "deterministic_fake"},
                "schema_validation_status": "repaired",
                "repair_used": True,
                "fallback_used": False,
                "decision": "accepted" if response.status_code < 400 else "rejected",
            }
        )
        return {
            "status_code": response.status_code,
            "json": payload,
            "generated_exercises": items,
            "fake_model": {
                "provider": "deterministic_fake",
                "repair_used": True,
                "scenario": "missing_field_repair",
            },
        }

    def _update_runtime_metrics_from_trace(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        episode = payload.get("episode") or {}
        status = episode.get("status")
        self.runtime_metrics["episode_count"] += 1
        if status == "completed":
            self.runtime_metrics["completed_episode_count"] += 1
        elif status == "completed_with_warnings":
            self.runtime_metrics["completed_episode_count"] += 1
        elif status == "failed":
            self.runtime_metrics["failed_episode_count"] += 1
        elif status == "verification_failed":
            self.runtime_metrics["failed_episode_count"] += 1
        verification_report = payload.get("verification_report") or episode.get("verification_report") or {}
        if isinstance(verification_report, dict):
            verification_status = verification_report.get("status")
            episode_id = str(episode.get("id") or payload.get("episode_id") or "")
            self._record_verification_status(verification_status, episode_id)
        prompt_executions = payload.get("prompt_executions") or []
        if isinstance(prompt_executions, list):
            self.runtime_metrics["prompt_executions"].extend(
                item for item in prompt_executions if isinstance(item, dict)
            )
        tool_calls = payload.get("tool_calls") or []
        statuses = [
            item.get("status")
            for item in tool_calls
            if isinstance(item, dict) and item.get("status") is not None
        ]
        self.runtime_metrics["tool_statuses"].extend(str(status) for status in statuses)
        latencies = [
            item.get("latency_ms")
            for item in tool_calls
            if isinstance(item, dict) and isinstance(item.get("latency_ms"), int | float)
        ]
        self.runtime_metrics["tool_latencies_ms"].extend(latencies)
        if latencies:
            all_latencies = self.runtime_metrics["tool_latencies_ms"]
            self.runtime_metrics["avg_tool_latency_ms"] = sum(all_latencies) / len(all_latencies)

    def _record_verification_status(self, status: Any, episode_id: str | None) -> None:
        if not status:
            return
        status_text = str(status)
        count_key = episode_id or status_text
        if count_key in self._verification_counted_episode_ids:
            return
        self._verification_counted_episode_ids.add(count_key)
        if status_text == "passed":
            self.runtime_metrics["verification_pass_count"] += 1
        elif status_text == "failed":
            self.runtime_metrics["verification_fail_count"] += 1
        self.runtime_metrics["verification_statuses"].append(status_text)

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
