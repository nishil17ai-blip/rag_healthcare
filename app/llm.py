from __future__ import annotations

import json
import re
from typing import Any

from ddgs import DDGS
from groq import Groq

from app.config import require_groq_key, settings
from app.schemas import RouteDecision


CITATION_RE = re.compile(r"[\[【]([SW]\d+)[\]】]")


class LLMService:

    def __init__(self) -> None:
        require_groq_key()

        self.client = Groq(
            api_key=settings.groq_api_key
        )

    # =====================================================
    # BASIC GENERATION
    # =====================================================

    def _generate(
        self,
        prompt: str
    ) -> str:

        response = self.client.chat.completions.create(
            model=settings.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0,
        )

        content = (
            response.choices[0]
            .message.content
        )

        if not content:
            raise RuntimeError(
                "Groq returned an empty response."
            )

        return content.strip()

    # =====================================================
    # ROUTER
    # =====================================================

    def route(
        self,
        question: str
    ) -> RouteDecision:

        prompt = f"""
You are routing questions for a health-insurance assistant.

Choose exactly one route.

POLICY_ONLY
Use when the answer should come only from the insurance policy.

Examples:
- coverage
- waiting periods
- exclusions
- definitions
- claims
- room-rent conditions
- policy limits

EXTERNAL_REQUIRED
Use when answering requires information outside the policy.

Examples:
- current treatment costs
- hospitals
- treatment options
- healthcare providers
- current market information

MIXED
Use when both policy information and external information
are needed.

Do not answer the question.
Do not assume facts.

Return valid JSON only:

{{
    "route": "POLICY_ONLY|EXTERNAL_REQUIRED|MIXED",
    "reason": "short reason"
}}

QUESTION:

{question}
""".strip()

        raw = self._generate(prompt)

        match = re.search(
            r"\{.*\}",
            raw,
            re.DOTALL,
        )

        if not match:
            raise RuntimeError(
                "Router returned invalid output:\n"
                + raw
            )

        try:
            data = json.loads(
                match.group(0)
            )

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Router returned invalid JSON:\n"
                + raw
            ) from exc

        return RouteDecision.model_validate(
            data
        )

    # =====================================================
    # NORMAL POLICY RAG
    # =====================================================

    def policy_answer(
        self,
        question: str,
        context: str
    ) -> str:

        prompt = f"""
You are a health-insurance policy assistant.

Answer the user's question ONLY using the supplied policy context.

RULES:

- Do not use outside knowledge.
- Do not assume missing facts.
- Clearly mention relevant conditions, exclusions,
  waiting periods and limitations.
- If information is insufficient, say so.
- Cite every material policy claim with its source ID,
  such as [S1] or [S2].
- Never invent a citation.
- Never invent page numbers, clauses or policy conditions.
- Do not provide medical advice.
- Keep the answer concise and easy to read.
- If the policy context gives different values for the same item
  (e.g. different waiting periods), state each value with its
  citation and say the policy schedule determines which applies.
  Do not pick one.
- Do not write conditional guesses such as "if X is listed". Check
  the context and state whether X is listed or that it was not found.
- When a time period is given in the question, compare it against
  every period found and state the result for each.

QUESTION:

{question}

POLICY CONTEXT:

{context}

Return only the answer.
""".strip()

        return self._generate(
            prompt
        )

    # =====================================================
    # AGENTIC SEARCH QUERY GENERATION
    # =====================================================

    def _build_search_queries(
        self,
        question: str
    ) -> list[str]:

        """
        Generate focused searches instead of passing the whole
        user question directly to DDGS.

        Location mentioned by the user must be preserved.
        """

        prompt = f"""
Create up to 3 focused web-search queries for the question below.

Requirements:

- Preserve any city, state or country explicitly mentioned.
- Prioritize the user's requested location.
- For medical treatment questions, search separately for:
  treatment options and local costs where appropriate.
- Prefer India-specific searches when an Indian location is given.
- Do not broaden an Ahmedabad question into U.S. pricing.
- Do not answer the question.

Return JSON only:

{{
    "queries": [
        "query 1",
        "query 2",
        "query 3"
    ]
}}

QUESTION:

{question}
""".strip()

        try:
            raw = self._generate(
                prompt
            )

            match = re.search(
                r"\{.*\}",
                raw,
                re.DOTALL,
            )

            if not match:
                return [question]

            data = json.loads(
                match.group(0)
            )

            queries = data.get(
                "queries",
                []
            )

            cleaned: list[str] = []

            for query in queries:

                if not isinstance(
                    query,
                    str
                ):
                    continue

                query = query.strip()

                if (
                    query
                    and query not in cleaned
                ):
                    cleaned.append(
                        query
                    )

            return (
                cleaned[:3]
                if cleaned
                else [question]
            )

        except Exception:
            return [question]

    # =====================================================
    # EXTERNAL WEB SEARCH
    # =====================================================

    def _search_external_sources(
        self,
        question: str
    ) -> list[dict]:

        queries = (
            self._build_search_queries(
                question
            )
        )

        results_by_url: dict[
            str,
            dict
        ] = {}

        for query in queries:

            try:
                results = DDGS().text(
                    query,
                    region="in-en",
                    safesearch="moderate",
                    max_results=4,
                )

            except Exception:
                continue

            for result in results:

                url = (
                    result.get("href")
                    or result.get("url")
                    or ""
                ).strip()

                if (
                    not url
                    or url in results_by_url
                ):
                    continue

                title = (
                    result.get("title")
                    or "External source"
                ).strip()

                snippet = (
                    result.get("body")
                    or result.get("snippet")
                    or ""
                ).strip()

                results_by_url[url] = {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "query": query,
                }

                # Keep external evidence small and focused.
                if len(results_by_url) >= 6:
                    break

            if len(results_by_url) >= 6:
                break

        evidence: list[dict] = []

        for index, result in enumerate(
            results_by_url.values(),
            start=1,
        ):

            evidence.append(
                {
                    "source_id": f"W{index}",
                    **result,
                }
            )

        return evidence

    # =====================================================
    # AGENTIC RAG
    # =====================================================

    def agentic_web_answer(
        self,
        question: str,
        policy_context: str,
    ) -> tuple[
        str,
        list[dict],
        list[dict],
    ]:

        web_evidence = (
            self._search_external_sources(
                question
            )
        )

        external_context_parts = []

        for source in web_evidence:

            external_context_parts.append(
                f"""
[{source["source_id"]}]
Title: {source["title"]}
URL: {source["url"]}
Search query: {source["query"]}
Content:
{source["snippet"]}
""".strip()
            )

        external_context = (
            "\n\n---\n\n".join(
                external_context_parts
            )
            if external_context_parts
            else
            "No reliable external search results were retrieved."
        )

        prompt = f"""
You are a health-insurance assistant.

Answer using TWO evidence categories.

POLICY CONTEXT
Use only this for:
- insurance coverage
- waiting periods
- exclusions
- policy limits
- claims
- policy conditions

Cite policy claims using [S1], [S2], etc.

EXTERNAL WEB CONTEXT
Use only this for:
- treatment options
- treatment costs
- hospitals
- providers
- market information

Cite external claims using [W1], [W2], etc.

STRICT RULES:

- Never invent policy coverage.
- Never invent prices.
- Never invent hospitals or providers.
- Never infer an Ahmedabad or India price from U.S. pricing.
- If local price evidence is unavailable, say so.
- Do not convert foreign prices into local estimates unless
  the supplied evidence directly supports that local estimate.
- Every numeric cost, duration, percentage or limit must have
  a citation supporting that value.
- Clearly distinguish policy information from external information.
- Do not diagnose the user.
- Do not recommend one medical treatment as superior.
- If evidence is insufficient, state that clearly.
- Keep the answer concise and readable.
- Do not use tables unless necessary.

QUESTION:

{question}

POLICY CONTEXT:

{policy_context}

EXTERNAL WEB CONTEXT:

{external_context}

Use short sections when relevant:

Policy coverage

Treatment options

Typical costs

Important note

Return only the answer.
""".strip()

        answer = self._generate(
            prompt
        )

        public_web_sources = [
            {
                "source_id":
                    source["source_id"],

                "title":
                    source["title"],

                "url":
                    source["url"],
            }
            for source in web_evidence
        ]

        return (
            answer,
            public_web_sources,
            web_evidence,
        )

    # =====================================================
    # FINAL GROUNDING VALIDATOR
    # =====================================================

    def validate_answer(
        self,
        answer: str,
        policy_items: list[dict],
        web_evidence: list[dict] | None = None,
    ) -> str:

        """
        Final grounding pass.

        This checks the generated answer against the exact
        evidence supplied to the model.

        Unsupported claims must be removed instead of guessed.
        """

        web_evidence = (
            web_evidence or []
        )

        policy_parts = []

        for item in policy_items:

            policy_parts.append(
                f"""
[{item["id"]}]
Page: {item["page"]}
Section: {item["section"]}
Clause: {item["clause"]}
Text:
{item["text"]}
""".strip()
            )

        policy_evidence = (
            "\n\n---\n\n".join(
                policy_parts
            )
        )

        web_parts = []

        for source in web_evidence:

            web_parts.append(
                f"""
[{source["source_id"]}]
Title: {source["title"]}
URL: {source["url"]}
Content:
{source["snippet"]}
""".strip()
            )

        web_context = (
            "\n\n---\n\n".join(
                web_parts
            )
            if web_parts
            else
            "No external evidence."
        )

        prompt = f"""
Act as a strict grounding validator.

Review the DRAFT ANSWER against the supplied evidence.

POLICY EVIDENCE:

{policy_evidence}

WEB EVIDENCE:

{web_context}

DRAFT ANSWER:

{answer}

VALIDATION RULES:

1. Keep only claims supported by the supplied evidence.

2. A policy claim must cite a valid [S#] source.

3. An external claim must cite a valid [W#] source.

4. Never create a new citation ID.

5. Pay special attention to:
   - prices
   - percentages
   - waiting periods
   - durations
   - monetary limits
   - quantities

6. A numeric claim may remain ONLY when the cited evidence
   directly supports that number or range.

7. Do not estimate, convert or infer a number that is not
   present in the evidence.

8. If Ahmedabad-specific pricing was not found, explicitly say:
   "Reliable Ahmedabad-specific pricing was not found in the
   retrieved sources."

9. If a claim is unsupported, remove it or replace it with a
   clear statement that the available evidence is insufficient.

10. Preserve the concise readable structure of the answer.

Return ONLY the corrected final answer.
""".strip()

        reviewed = self._generate(
            prompt
        )

        return self._remove_invalid_citations(
            reviewed,
            policy_items,
            web_evidence,
        )

    # =====================================================
    # DETERMINISTIC CITATION CHECK
    # =====================================================

    @staticmethod
    def _remove_invalid_citations(
        answer: str,
        policy_items: list[dict],
        web_evidence: list[dict],
    ) -> str:

        """
        Even after the validation LLM pass, never allow a
        citation ID that does not actually exist.
        """

        valid_ids = {
            item["id"]
            for item in policy_items
        }

        valid_ids.update(
            source["source_id"]
            for source in web_evidence
        )

        def replace(
            match: re.Match
        ) -> str:

            source_id = (
                match.group(1)
            )

            if source_id in valid_ids:
                return f"[{source_id}]"

            return ""

        return CITATION_RE.sub(
            replace,
            answer,
        ).strip()