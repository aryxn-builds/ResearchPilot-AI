from __future__ import annotations

import structlog

from app.core.database import get_service_client
from app.schemas.agent import (
    Claim,
    CriticResult,
    Evidence,
    ResearchPlan,
    Source,
)

logger = structlog.get_logger(__name__)


class PersistenceService:
    """Handles persisting LangGraph entities to the database.

    Uses the service role client because writes are backend-internal operations.
    """

    async def save_plan(self, session_id: str, plan: ResearchPlan) -> None:
        client = get_service_client()
        try:
            # 1. Save the plan
            plan_data = {
                "session_id": session_id,
                "sub_questions": [sq.model_dump(mode="json") for sq in plan.sub_questions],
                "sub_question_count": len(plan.sub_questions),
            }
            # ON CONFLICT DO UPDATE is handled gracefully if needed, but session_id is unique
            await (
                client.table("research_plans").upsert(plan_data, on_conflict="session_id").execute()
            )

            # 2. Save the initial tasks
            tasks_data = [
                {
                    "session_id": session_id,
                    "sub_question": sq.question,
                    "research_type": sq.research_type,
                    "status": "pending",
                    "iteration": 1,
                }
                for sq in plan.sub_questions
            ]
            if tasks_data:
                await client.table("research_tasks").insert(tasks_data).execute()

            logger.info("Saved research plan and tasks", session_id=session_id)
        except Exception as e:
            logger.error("Failed to save research plan", session_id=session_id, error=str(e))

    async def save_sources(self, session_id: str, sources: list[Source]) -> None:
        if not sources:
            return

        client = get_service_client()
        try:
            sources_data = [
                {
                    "id": str(s.id),
                    "session_id": session_id,
                    "task_id": str(s.task_id) if s.task_id else None,
                    "url": s.url,
                    "title": s.title,
                    "source_type": "web",  # Defaulting to web for now
                    "relevance_score": s.relevance_score,
                    "credibility_score": s.credibility_score,
                    "domain": s.domain,
                    "published_date": s.published_date,
                    "is_flagged": s.is_flagged,
                    "flag_reason": None,
                }
                for s in sources
            ]

            # Upsert using ON CONFLICT (session_id, url) deduplication
            await (
                client.table("sources").upsert(sources_data, on_conflict="session_id,url").execute()
            )

            logger.info("Saved sources", session_id=session_id, count=len(sources))
        except Exception as e:
            logger.error("Failed to save sources", session_id=session_id, error=str(e))

    async def save_evidence(self, session_id: str, evidence_items: list[Evidence]) -> None:
        if not evidence_items:
            return

        client = get_service_client()
        try:
            evidence_data = [
                {
                    "id": str(e.id),
                    "session_id": session_id,
                    "source_id": str(e.source_id),
                    "task_id": str(e.sub_question_id),  # sub_question maps to task for now
                    "content": e.snippet,
                    "sub_question": "Unknown",  # we don't have the text here
                    "position_in_source": None,
                    "extraction_confidence": None,
                }
                for e in evidence_items
            ]

            await client.table("evidence").upsert(evidence_data, on_conflict="id").execute()

            logger.info("Saved evidence", session_id=session_id, count=len(evidence_items))
        except Exception as e:
            logger.error("Failed to save evidence", session_id=session_id, error=str(e))

    async def save_claims(self, session_id: str, claims: list[Claim], iteration: int = 1) -> None:
        if not claims:
            return

        client = get_service_client()
        try:
            claims_data = [
                {
                    "id": str(c.id),
                    "session_id": session_id,
                    "content": c.statement,
                    "status": c.verification_status,
                    "iteration": iteration,
                }
                for c in claims
            ]

            await client.table("claims").upsert(claims_data, on_conflict="id").execute()

            # Save claim_evidence links
            claim_evidence_data = []
            for c in claims:
                for eid in c.evidence_ids:
                    claim_evidence_data.append(
                        {
                            "claim_id": str(c.id),
                            "evidence_id": str(eid),
                        }
                    )

            if claim_evidence_data:
                await (
                    client.table("claim_evidence")
                    .upsert(claim_evidence_data, on_conflict="claim_id,evidence_id")
                    .execute()
                )

            logger.info("Saved claims", session_id=session_id, count=len(claims))
        except Exception as e:
            logger.error("Failed to save claims", session_id=session_id, error=str(e))

    async def save_critic_result(
        self, session_id: str, result: CriticResult, iteration: int
    ) -> None:
        if not result or not result.claims:
            return

        client = get_service_client()
        try:
            # Update claims status
            for c in result.claims:
                await (
                    client.table("claims")
                    .update({"status": c.verification_status})
                    .eq("id", str(c.id))
                    .execute()
                )

            # Save critic results
            critic_data = [
                {
                    "session_id": session_id,
                    "claim_id": str(c.id),
                    "verification_status": c.verification_status,
                    "critic_notes": c.critic_notes,
                    "iteration": iteration,
                }
                for c in result.claims
            ]

            if critic_data:
                await client.table("critic_results").insert(critic_data).execute()

            logger.info("Saved critic results", session_id=session_id, count=len(result.claims))
        except Exception as e:
            logger.error("Failed to save critic results", session_id=session_id, error=str(e))

    async def save_agent_run(
        self,
        session_id: str,
        agent_name: str,
        status: str,
        input_summary: dict | None = None,
        output_summary: dict | None = None,
        error_message: str | None = None,
        llm_provider_used: str | None = None,
        tokens_used: int | None = None,
        duration_ms: int | None = None,
    ) -> None:
        client = get_service_client()
        try:
            await (
                client.table("agent_runs")
                .insert(
                    {
                        "session_id": session_id,
                        "agent_name": agent_name,
                        "status": status,
                        "input_summary": input_summary or {},
                        "output_summary": output_summary or {},
                        "error_message": error_message,
                        "llm_provider_used": llm_provider_used,
                        "tokens_used": tokens_used,
                        "duration_ms": duration_ms,
                    }
                )
                .execute()
            )
        except Exception as e:
            logger.error("Failed to save agent run", session_id=session_id, error=str(e))
