const form = document.getElementById("ask-form");
const input = document.getElementById("question");
const send = document.getElementById("send");
const chat = document.getElementById("chat");


/* -------------------------------------------------------
   HTML escaping
------------------------------------------------------- */

const escapeHtml = (value = "") =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");


/* -------------------------------------------------------
   Answer formatting
------------------------------------------------------- */
function formatAnswer(text = "", policySources = [], webSources = []) {
  // Drop a trailing "Sources:" block; the source cards already cover it
  text = text.replace(/\n+\s*(?:\*\*)?Sources?:?(?:\*\*)?[\s\S]*$/i, "");

  const policyMap = Object.fromEntries(policySources.map(s => [s.source_id, s]));
  const webMap = Object.fromEntries(webSources.map(s => [s.source_id, s]));

  const inline = (line) => {
    let s = escapeHtml(line).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    s = s.replace(/(?:\[|\(|【)(S\d+)(?:\]|\)|】)/g, (m, id) => {
      const src = policyMap[id];
      if (!src) return `[${id}]`;
      const title = escapeHtml(`Open ${src.source} — Page ${src.page}`);
      return `<a class="inline-citation" href="/policy-document#page=${encodeURIComponent(src.page)}" target="_blank" rel="noopener noreferrer" title="${title}">[${id}]</a>`;
    });

    s = s.replace(/(?:\[|\(|【)(W\d+)(?:\]|\)|】)/g, (m, id) => {
      const src = webMap[id];
      if (!src || !src.url) return `[${id}]`;
      return `<a class="inline-web-citation" href="${escapeHtml(src.url)}" target="_blank" rel="noopener noreferrer">[${id}]</a>`;
    });

    return s;
  };

  return text
    .trim()
    .split(/\n\s*\n/)
    .map((block) => {
      const lines = block.split("\n").map(l => l.trim()).filter(Boolean);
      if (lines.length && lines.every(l => /^([-*•]|\d+[.)])\s+/.test(l))) {
        const items = lines
          .map(l => `<li>${inline(l.replace(/^([-*•]|\d+[.)])\s+/, ""))}</li>`)
          .join("");
        return `<ul class="answer-list">${items}</ul>`;
      }
      return `<p>${lines.map(inline).join("<br>")}</p>`;
    })
    .join("");
}

/* -------------------------------------------------------
   Scroll
------------------------------------------------------- */

function scrollToBottom() {

  requestAnimationFrame(() => {

    window.scrollTo({
      top: document.body.scrollHeight,
      behavior: "smooth"
    });

  });
}


/* -------------------------------------------------------
   Welcome screen
------------------------------------------------------- */

function removeWelcome() {

  const welcome =
    chat.querySelector(".welcome-card");

  if (welcome) {
    welcome.remove();
  }
}


/* -------------------------------------------------------
   User message
------------------------------------------------------- */

function addUserMessage(text) {

  removeWelcome();

  const el =
    document.createElement("div");

  el.className =
    "message user";

  el.innerHTML = `
    <div class="bubble">
      ${escapeHtml(text)}
    </div>

    <div class="avatar user-avatar">
      You
    </div>
  `;

  chat.appendChild(el);

  scrollToBottom();
}


/* -------------------------------------------------------
   Loading animation
------------------------------------------------------- */

function addLoading() {

  const el =
    document.createElement("div");

  el.className =
    "message assistant";

  el.id =
    "loading-message";

  el.innerHTML = `
    <div class="avatar">
      AI
    </div>

    <div class="bubble loading-bubble">

      <div class="thinking-text">
        Checking policy evidence
      </div>

      <span class="loading">
        <i></i>
        <i></i>
        <i></i>
      </span>

    </div>
  `;

  chat.appendChild(el);

  scrollToBottom();
}


/* -------------------------------------------------------
   Policy source cards
------------------------------------------------------- */

function sourceCards(sources = []) {

    if (!sources.length) {
        return "";
    }

    return sources.map((src) => {

        const sourceId =
            escapeHtml(src.source_id || "");

        const sourceName =
            escapeHtml(
                src.source || "Policy document"
            );

        const page =
            escapeHtml(
                String(src.page || "")
            );

        const section =
            escapeHtml(
                src.section ||
                "Not explicitly identified"
            );

        const clause =
            escapeHtml(
                src.clause ||
                "Not explicitly identified"
            );

        const sourceUrl =
            `/policy-document#page=${encodeURIComponent(src.page)}`;

        return `
            <a
                class="source-card clickable-source"
                href="${sourceUrl}"
                target="_blank"
                rel="noopener noreferrer"
                title="Open policy PDF at page ${page}"
            >

                <div class="source-head">

                    <span class="source-id">
                        [${sourceId}] ${sourceName}
                    </span>

                    <span class="source-page">
                        Page ${page} ↗
                    </span>

                </div>

                <div class="source-section">
                    ${section}
                </div>

                <div class="source-clause">
                    ${clause}
                </div>

                <div class="source-open">
                    View source in policy →
                </div>

            </a>
        `;
    }).join("");
}


/* -------------------------------------------------------
   External web source cards
------------------------------------------------------- */

function webSourceCards(sources = []) {

  if (!sources.length) {
    return "";
  }

  return sources
    .map((src, index) => {

      const sourceId =
        escapeHtml(
          src.source_id ||
          `W${index + 1}`
        );

      const title =
        escapeHtml(
          src.title ||
          src.url ||
          "External source"
        );

      const url =
        escapeHtml(
          src.url || "#"
        );

      return `
        <a
          class="source-card clickable-source web-card"
          href="${url}"
          target="_blank"
          rel="noopener noreferrer"
        >

          <div class="source-top">

            <span class="source-number web-number">
              [${sourceId}]
            </span>

            <span class="source-page-pill">
              Web ↗
            </span>

          </div>

          <div class="web-source-title">
            ${title}
          </div>

          <div class="source-action">
            Open external source
            <span>→</span>
          </div>

        </a>
      `;
    })
    .join("");
}


/* -------------------------------------------------------
   Assistant answer
------------------------------------------------------- */

function addAssistantMessage(data) {

  document
    .getElementById("loading-message")
    ?.remove();

  const route =
    data.route || "POLICY_ONLY";

  const routeClass =
    route === "POLICY_ONLY"
      ? "policy"
      : route === "MIXED"
      ? "mixed"
      : "external";

  const policyCount =
    data.policy_sources?.length || 0;

  const webCount =
    data.web_sources?.length || 0;

  const el =
    document.createElement("div");

  el.className =
    "message assistant";

  el.innerHTML = `

    <div class="avatar">
      AI
    </div>

    <div class="bubble assistant-bubble">

      <div class="answer-meta">

        <span class="route-badge ${routeClass}">
          ${escapeHtml(
            route.replaceAll("_", " ")
          )}
        </span>

        ${
          data.needs_more_information
            ? `
              <span class="info-badge">
                Additional information may be required
              </span>
            `
            : ""
        }

      </div>

      <div class="answer-text">
        ${formatAnswer(
            data.answer,
            data.policy_sources || [],
            data.web_sources || []
        )}
      </div>


      ${
        policyCount
          ? `
            <details
              class="sources"
              open
            >

              <summary>

                <span>
                  Policy sources
                </span>

                <span class="source-count">
                  ${policyCount}
                </span>

              </summary>

              <div class="source-grid">

                ${sourceCards(
                  data.policy_sources
                )}

              </div>

            </details>
          `
          : ""
      }


      ${
        webCount
          ? `
            <details
              class="sources"
            >

              <summary>

                <span>
                  External web sources
                </span>

                <span class="source-count">
                  ${webCount}
                </span>

              </summary>

              <div class="source-grid">

                ${webSourceCards(
                  data.web_sources
                )}

              </div>

            </details>
          `
          : ""
      }

    </div>
  `;

  chat.appendChild(el);

  scrollToBottom();
}


/* -------------------------------------------------------
   Error
------------------------------------------------------- */

function addError(message) {

  document
    .getElementById("loading-message")
    ?.remove();

  const el =
    document.createElement("div");

  el.className =
    "message assistant";

  el.innerHTML = `

    <div class="avatar">
      AI
    </div>

    <div class="bubble">

      <div class="error-box">

        <strong>
          Unable to complete the request
        </strong>

        <div>
          ${escapeHtml(message)}
        </div>

      </div>

    </div>
  `;

  chat.appendChild(el);

  scrollToBottom();
}


/* -------------------------------------------------------
   Ask API
------------------------------------------------------- */

async function ask(question) {
    const cleanQuestion = question.trim();

    if (!cleanQuestion) return;

    addUserMessage(cleanQuestion);
    addLoading();

    send.disabled = true;
    input.disabled = true;

    try {
        const formData = new FormData();

        formData.append(
            "question",
            cleanQuestion
        );

        const response = await fetch(
            "/ask",
            {
                method: "POST",
                body: formData
            }
        );

        const data = await response.json();

        if (!response.ok) {
            console.error(
                "Backend error:",
                data
            );

            let message =
                "The assistant could not answer the question.";

            if (typeof data.detail === "string") {
                message = data.detail;
            }

            else if (Array.isArray(data.detail)) {
                message = data.detail
                    .map(item => {
                        const field =
                            item.loc?.join(" → ") || "";

                        return `${field}: ${item.msg}`;
                    })
                    .join(" | ");
            }

            throw new Error(message);
        }

        addAssistantMessage(data);

    } catch (error) {

        console.error(error);

        addError(
            error.message ||
            "Something went wrong."
        );

    } finally {

        send.disabled = false;
        input.disabled = false;
        input.focus();
    }
}

/* -------------------------------------------------------
   Form submit
------------------------------------------------------- */

form.addEventListener(
  "submit",
  (event) => {

    event.preventDefault();

    const question =
      input.value;

    input.value = "";

    input.style.height =
      "auto";

    ask(
      question
    );
  }
);


/* -------------------------------------------------------
   Enter to submit
------------------------------------------------------- */

input.addEventListener(
  "keydown",
  (event) => {

    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {

      event.preventDefault();

      form.requestSubmit();
    }
  }
);


/* -------------------------------------------------------
   Auto-resize textarea
------------------------------------------------------- */

input.addEventListener(
  "input",
  () => {

    input.style.height =
      "auto";

    input.style.height =
      `${Math.min(
        input.scrollHeight,
        150
      )}px`;
  }
);


/* -------------------------------------------------------
   Suggested questions
------------------------------------------------------- */

document
  .querySelectorAll(".suggestion")
  .forEach((button) => {
    button.addEventListener("click", () => {
      const question = button.dataset.question || "";
      if (!question || send.disabled) return;

      input.value = "";
      input.style.height = "auto";
      ask(question);
    });
  });