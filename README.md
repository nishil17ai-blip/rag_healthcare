# PolicyCare AI — HealthCare RAG + Agentic RAG

PolicyCare AI is an end-to-end Health Insurance RAG application built for answering policy-related questions using the **HDFC ERGO Optima Secure Policy Wording** as the primary knowledge source.

The system supports both:

- **Policy RAG** — answers questions strictly from the insurance policy.
- **Agentic RAG** — handles questions requiring information beyond the policy, such as treatment options, approximate market costs, or location-specific information.

The application includes a lightweight chat UI, source-level citations, clickable policy references, external web sources, grounding validation, and semantic caching.

---

## Features

- HDFC ERGO Optima Secure policy as the knowledge source
- Page-aware PDF extraction using PyMuPDF
- Local SentenceTransformer embeddings
- ChromaDB vector database
- Groq `openai/gpt-oss-20b` for:
  - question routing
  - answer generation
  - grounding validation
- LangGraph workflow orchestration
- Policy-only RAG
- Agentic RAG for external-information questions
- DDGS-based external web search
- Policy citation metadata:
  - Source
  - Page
  - Section
  - Clause
- Clickable policy citations that open the actual PDF page
- External web-source links
- Semantic caching for repeated / semantically similar policy questions
- FastAPI backend
- HTML / CSS / JavaScript chat UI
- No React or frontend framework required
- Can perform much better if we use any closed source model
---

# Architecture

```text
                     User / Browser UI
                             |
                             v
                       FastAPI /ask
                             |
                             v
                       Semantic Cache
                             |
                 Cache Hit? | | Cache Miss
                       Yes   | |   No
                             | v
                             | LangGraph Router
                             |       |
                             |       v
                             | Policy Retrieval
                             |       |
                             |       |
                  +----------+-------+-----------+
                  |                              |
             POLICY_ONLY               MIXED / EXTERNAL_REQUIRED
                  |                              |
                  v                              v
           Groq Draft Answer             Focused Search Queries
                  |                              |
                  v                              v
        Grounding Validation                DDGS Search
                  |                              |
                  |                       External Evidence
                  |                              |
                  |                     Policy + Web Context
                  |                              |
                  |                              v
                  |                       Groq Draft Answer
                  |                              |
                  |                              v
                  |                    Grounding Validation
                  |                              |
                  +---------------+--------------+
                                  |
                                  v
                     Citation Verification
                                  |
                                  v
                   Answer + Verified Sources
                                  |
                                  v
                         Browser Chat UI
