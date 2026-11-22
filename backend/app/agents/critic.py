from __future__ import annotations

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.research_mode import fast_research
from app.llm.router import LLMRouter
from app.prompts.critic import CRITIC_SYSTEM_PROMPT
from app.schemas.agent import Claim, CriticResult, Evidence

logger = structlog.get_logger(__name__)


class CriticAgent:
    """Agent responsible for verifying claims against evidence."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self.llm_router = llm_router

    async def run(
        self, claims: list[Claim], evidence_list: list[Evidence], callbacks: list | None = None
    ) -> CriticResult:
        """Verify the synthesized claims.

        Args:
            claims: The synthesized claims to verify.
            evidence_list: The original extracted evidence items.
            callbacks: Optional LangChain callbacks.

        Returns:
            The CriticResult containing verified/unverified/contradicted statuses.
        """
        if not claims:
            logger.info("No claims to verify")
            return CriticResult(claims=[])

        logger.info("CriticAgent starting", num_claims=len(claims))

        # Prepare inputs
        claims_data = [
            {
                "id": str(c.id),
                "statement": c.statement,
                "evidence_ids": [str(eid) for eid in c.evidence_ids],
            }
            for c in claims
        ]

        evidence_data = [
            {
                "id": str(ev.id),
                "snippet": ev.snippet,
            }
            for ev in evidence_list
        ]

        import json

        human_content = (
            f"Evidence Items:\n<raw_source>\n{json.dumps(evidence_data, indent=2)}\n</raw_source>\n\n"
            f"Claims to Verify:\n{json.dumps(claims_data, indent=2)}"
        )

        messages = [
            SystemMessage(content=CRITIC_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]

        result = await self.llm_router.generate_structured(
            messages, CriticResult, callbacks=callbacks
        )

        if fast_research.get():
            # Keep authoritative claim IDs and references. Conflicting or omitted
            # decisions remain unverified rather than being inferred from position.
            decisions: dict[str, list[Claim]] = {}
            for decision in result.claims:
                decisions.setdefault(decision.id, []).append(decision)
            checked = []
            for claim in claims:
                matches = decisions.get(claim.id, [])
                decision = matches[0] if len(matches) == 1 else None
                if decision is None or decision.statement != claim.statement:
                    checked.append(claim.model_copy(update={"verification_status": "unverified"}))
                    continue
                status = decision.verification_status
                if status == "pending" or not claim.evidence_ids:
                    status = "unverified"
                checked.append(claim.model_copy(update={
                    "verification_status": status, "critic_notes": decision.critic_notes,
                }))
            return CriticResult(claims=checked)

        original_claims_map = {c.statement: c for c in claims}
        
        verified_claims = []
        for rc in result.claims:
            if rc.statement in original_claims_map:
                orig_c = original_claims_map[rc.statement]
                orig_c.verification_status = rc.verification_status
                orig_c.critic_notes = rc.critic_notes
                verified_claims.append(orig_c)
        
        # Replace the potentially hallucinated claims with the original instances
        result.claims = verified_claims

        logger.info("CriticAgent completed")
        return result
