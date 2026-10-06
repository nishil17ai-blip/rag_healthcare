from __future__ import annotations
import re
from langgraph.graph import (
    END,
    START,
    StateGraph,
)
from app.llm import LLMService
from app.retrieval import (
    PolicyRetriever,
    context_block,
)
from app.schemas import (
    AskResponse,
    SourceCitation,
    WebSource,
    WorkflowState,
)
from app.cache import SemanticCache


SOURCE_TOKEN_RE = re.compile(
    r"(?:\[|【|\()(S\d+)(?:\]|】|\))"
)


class InsuranceAssistant:

    def __init__(self) -> None:
        self.retriever = PolicyRetriever()
        self.llm = LLMService()

        self.cache = SemanticCache(
            threshold=0.92,
            max_entries=200,
        )

        self.graph = self._build_graph()

    # =====================================================
    # GRAPH
    # =====================================================

    def _build_graph(
        self
    ):

        graph = StateGraph(
            WorkflowState
        )

        graph.add_node(
            "route",
            self._route,
        )

        graph.add_node(
            "retrieve_policy",
            self._retrieve_policy,
        )

        graph.add_node(
            "policy_answer",
            self._policy_answer,
        )

        graph.add_node(
            "agentic_answer",
            self._agentic_answer,
        )

        graph.add_edge(
            START,
            "route",
        )

        graph.add_edge(
            "route",
            "retrieve_policy",
        )

        graph.add_conditional_edges(
            "retrieve_policy",

            lambda state: (
                "policy"
                if state["route"]
                == "POLICY_ONLY"
                else "agentic"
            ),

            {
                "policy":
                    "policy_answer",

                "agentic":
                    "agentic_answer",
            },
        )

        graph.add_edge(
            "policy_answer",
            END,
        )

        graph.add_edge(
            "agentic_answer",
            END,
        )

        return graph.compile()

    # =====================================================
    # ROUTE
    # =====================================================

    def _route(
        self,
        state: WorkflowState,
    ) -> WorkflowState:

        decision = (
            self.llm.route(
                state["question"]
            )
        )

        return {
            "route":
                decision.route,

            "route_reason":
                decision.reason,
        }

    # =====================================================
    # RETRIEVAL
    # =====================================================

    def _retrieve_policy(
        self,
        state: WorkflowState,
    ) -> WorkflowState:

        items = (
            self.retriever.search(
                state["question"]
            )
        )

        return {
            "policy_context":
                items
        }

    # =====================================================
    # CITED SOURCES ONLY
    # =====================================================

    @staticmethod
    def _sources_from_answer(
        answer: str,
        items: list[dict],
    ) -> list[dict]:

        """
        Return ONLY policy chunks actually cited
        by the final answer.

        There is deliberately NO fallback.
        """

        by_id = {
            item["id"]: item
            for item in items
        }

        ordered_ids: list[str] = []

        for source_id in (
            SOURCE_TOKEN_RE.findall(
                answer
            )
        ):

            if (
                source_id in by_id
                and
                source_id not in ordered_ids
            ):
                ordered_ids.append(
                    source_id
                )

        sources: list[dict] = []

        for source_id in ordered_ids:

            item = by_id[
                source_id
            ]

            sources.append(
                {
                    "source_id":
                        source_id,

                    "source":
                        item["source"],

                    "page":
                        item["page"],

                    "section":
                        item["section"],

                    "clause":
                        item["clause"],
                }
            )

        return sources

    # =====================================================
    # NEEDS MORE INFORMATION
    # =====================================================

    @staticmethod
    def _needs_more_information(
        answer: str
    ) -> bool:

        opening = answer.lower()[:250]

        phrases = (
            "don't have enough information",
            "do not have enough information",
            "not enough information",
            "need more information",
            "insufficient information",
            "insufficient evidence",
            "cannot determine",
            "unable to determine",
            "cannot confirm",
            "was not found",
            "were not found",
        )

        return any(
            phrase in opening
            for phrase in phrases
        )

    # =====================================================
    # POLICY ANSWER
    # =====================================================

    def _policy_answer(
        self,
        state: WorkflowState,
    ) -> WorkflowState:

        items = (
            state[
                "policy_context"
            ]
        )

        context = (
            context_block(
                items
            )
        )

        # First generation
        draft_answer = (
            self.llm.policy_answer(
                state["question"],
                context,
            )
        )

        # Final grounding validation
        answer = (
            self.llm.validate_answer(
                answer=draft_answer,
                policy_items=items,
            )
        )

        policy_sources = (
            self._sources_from_answer(
                answer,
                items,
            )
        )

        return {
            "answer":
                answer,

            "policy_sources":
                policy_sources,

            "web_sources":
                [],

            "needs_more_information":
                self._needs_more_information(
                    answer
                ),
        }

    # =====================================================
    # AGENTIC ANSWER
    # =====================================================

    def _agentic_answer(
        self,
        state: WorkflowState,
    ) -> WorkflowState:

        items = (
            state[
                "policy_context"
            ]
        )

        context = (
            context_block(
                items
            )
        )

        (
            draft_answer,
            web_sources,
            web_evidence,
        ) = (
            self.llm.agentic_web_answer(
                state["question"],
                context,
            )
        )

        # Validate final answer against BOTH
        # policy and web evidence.
        answer = (
            self.llm.validate_answer(
                answer=draft_answer,
                policy_items=items,
                web_evidence=web_evidence,
            )
        )

        policy_sources = (
            self._sources_from_answer(
                answer,
                items,
            )
        )

        # Only display external sources that are
        # actually cited in the final validated answer.
        web_sources = (
            self._web_sources_from_answer(
                answer,
                web_sources,
            )
        )

        return {
            "answer":
                answer,

            "policy_sources":
                policy_sources,

            "web_sources":
                web_sources,

            "needs_more_information":
                self._needs_more_information(
                    answer
                ),
        }

    # =====================================================
    # CITED WEB SOURCES ONLY
    # =====================================================

    @staticmethod
    def _web_sources_from_answer(
        answer: str,
        web_sources: list[dict],
    ) -> list[dict]:

        by_id = {
            source["source_id"]:
                source
            for source in web_sources
        }

        cited_ids = re.findall(
            r"(?:\[|【|\()(W\d+)(?:\]|】|\))",
            answer,
        )

        ordered_ids = []

        for source_id in cited_ids:

            if (
                source_id in by_id
                and
                source_id not in ordered_ids
            ):
                ordered_ids.append(
                    source_id
                )

        return [
            by_id[source_id]
            for source_id
            in ordered_ids
        ]

    # =====================================================
    # PUBLIC ASK
    # =====================================================

    def ask(
        self,
        question: str,
    ) -> AskResponse:

        has_number = any(c.isdigit() for c in question)

        if not has_number:
            cached = self.cache.get(question)

            if cached is not None:
                return cached

        result = self.graph.invoke({"question": question})

        response = AskResponse(
            route=result["route"],
            answer=result["answer"],
            policy_sources=[
                SourceCitation(**source)
                for source in result.get("policy_sources", [])
            ],
            web_sources=[
                WebSource(**source)
                for source in result.get("web_sources", [])
            ],
            needs_more_information=result.get(
                "needs_more_information",
                False,
            ),
        )

        if not has_number and response.route == "POLICY_ONLY":
            self.cache.put(question, response)

        return response