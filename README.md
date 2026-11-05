# Empório da Música AI Support Assistant

A Python prototype of a text-based customer support assistant for **Empório da Música**, a fictional musical instrument store in Campo Grande, Brazil. The assistant uses a real language model to conduct the conversation and typed Python tools to read the supplied catalog, promotions, orders, and store policies.

The implementation favors a small, inspectable architecture over an agent framework. It uses the Gemini API function-calling loop through Google's official Gen AI SDK, Python's standard CSV and `Decimal` libraries, and a lightweight keyword index for the eight-page policy manual.

## What it does

- Searches instruments by text, category, availability, maximum current price, and an exact structured specification such as `electronics=yes` or `strings=nylon`.
- Exposes total/returned counts and `next_offset` so the model can consult remaining catalog pages before making a general conclusion.
- Reads list prices, stock, catalog status, and active promotions from the CSV files.
- Parses the JSON `specs` field and returns structured product specifications with an explicit parse status.
- Calculates PIX and promotional prices without floating-point errors or discount stacking.
- Assesses credit-card installments, rejects invalid counts explicitly, preserves the exact total after cent rounding, and reports any last-installment adjustment.
- Looks up orders only after matching the order ID and registered e-mail, then returns a privacy-limited view.
- Retrieves relevant policy sections for hours, address, payments, returns, delivery, warranty, privacy, and store scope.
- Asks for missing facts, distinguishes no result from a technical failure, and avoids claiming that it performed unsupported operations.
- Keeps conversational context during one CLI session.

## Architecture

```text
Customer
   |
   v
Python CLI -> SupportAgent orchestration loop -> Gemini API
                                              |
                          function calls -----+
                               |
              +----------------+----------------+
              v                                 v
      StoreRepository                     PolicyStore
   CSV lookup + Decimal math        reviewed section retrieval
```

The LLM decides **which** read-only tool is needed and writes the natural-language answer. Python remains the source of truth for data access, authorization checks, and money calculations. Tool results are JSON and are returned to the model through the standard function-calling flow described in the [official Gemini documentation](https://ai.google.dev/gemini-api/docs/function-calling).

### Why this design

- **Function calling, not SQL generation:** the data is small and the permitted operations are narrow. Explicit functions are easier to validate and safer than model-generated queries.
- **No vector database:** the policy source is only eight pages and has strong section headings. A reviewed JSON extraction plus accent-insensitive keyword retrieval is transparent, fast, and reproducible.
- **No agent framework:** the Gemini function-calling loop is small and has no need for framework abstractions.
- **CLI interface:** the challenge explicitly accepts a CLI and evaluates agent behavior rather than front-end polish.
- **`Decimal` for BRL:** prices and percentage discounts must not use binary floats.
- **Stateless API requests:** conversation history is kept only in the local process and is resent with each GenerateContent request while the CLI is running.

## Project structure

```text
src/emporio_agent/
  agent.py          # Gemini API tool-calling loop
  cli.py            # terminal interface and dependency wiring
  config.py         # environment configuration
  policies.py       # lightweight policy retrieval
  prompt.py         # persona, grounding, privacy, and safety instructions
  repository.py     # CSV access and deterministic business rules
  tools.py          # strict tool schemas and safe dispatcher
data/
  *.csv             # supplied operational data
  políticas_da_loja.pdf
  policy_sections.json  # reviewed runtime extraction of the PDF
tests/              # standard-library unit and orchestration tests
examples/
  generated/        # ignored raw API output
  reviewed/         # source-checked real Gemini transcripts, versioned
docs/               # data notes, conversation review, and summary source
```

## Requirements

- Python 3.11 or newer
- A Gemini API key
- An explicit `GEMINI_MODEL` confirmed for the same Google AI project; the corrected catalog run used `gemini-2.5-flash`, while scenarios 02-04 used `gemini-3.5-flash-lite`
- Internet access when running the assistant

The runtime code deliberately has **no implicit model default**: configuration must remain explicit. The supplied `.env.example` records the original `gemini-3.5-flash-lite` configuration; the catalog correction was executed with `gemini-2.5-flash` after the original model returned 503 high-demand errors. Availability must still be confirmed for the caller's key/project. The access-check script uses the key's model catalog and then forces a small Gemini function call before the model is considered validated. See the [official model-list API](https://ai.google.dev/api/models).

## Installation

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
Copy-Item .env.example .env
```

Edit `.env` and set your own key:

```dotenv
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

Create or copy a key in [Google AI Studio](https://aistudio.google.com/app/apikey). To list the models visible to the key/project, temporarily leave `GEMINI_MODEL` blank and run:

```powershell
python scripts/check_model_access.py
```

Choose an appropriate text model from that project-specific output, set `GEMINI_MODEL`, and run the same command again. A successful result confirms both catalog visibility and an actual Gemini function call. Merely copying a model ID from public documentation is not treated as validation.

The `.env` file is ignored by Git. Do not place a key in source code, examples, logs, or screenshots.

On macOS or Linux, activate the environment with `source .venv/bin/activate` and copy the environment file with `cp .env.example .env`.

## Run

```powershell
python -m emporio_agent
```

or, after editable installation:

```powershell
emporio-assistant
```

Type `sair` to end the session.

## Tests

The test suite does not need an API key. It validates the deterministic tools and uses a fake Gemini client to exercise the orchestration loop without pretending that a real model was called.

```powershell
python -m unittest discover -s tests -v
```

Current local result: **39 tests passed** on Python 3.13.1. Covered risks include:

- source loading and expected row counts;
- accent-insensitive product filtering and price sorting;
- remaining catalog pages, specification filters applied before pagination, valid page bounds, and consistent empty-page metadata;
- exact GN-15 source cents (`689.00`) and discovery of Shelby 107 (`799.00`, `electronics=yes`) beyond the first eight results;
- active, out-of-stock, coming-soon, and discontinued availability states;
- exact promotion and PIX calculations;
- non-cumulative discounts;
- structured parsing and error reporting for product specifications;
- explicit rejection of zero, negative, and excessive installment counts;
- exact reconciliation of the final price with rounded installment values;
- contradictory installment thresholds;
- privacy-preserving order verification;
- contact, payment-policy, CNPJ, tracking, promotion-calendar, response-time, and policy-governance retrieval;
- project-specific model-list and forced function-call validation with mocks;
- conversation continuity across user messages;
- sanitized unknown-tool and invalid-argument failures;
- Gemini's manual model -> tool -> model round trip, including a `user`-role function response and preservation of the function-call ID.

## Interaction examples

[`examples/illustrative_conversations.md`](examples/illustrative_conversations.md) contains four **illustrative, not API-executed** conversations. They are based on real deterministic tool outputs and are included so the intended behavior can be reviewed without misrepresenting a model run.

After configuring a key and confirming the model, generate four real LLM transcripts with:

```powershell
python scripts/generate_examples.py
```

The generator supports resuming a partial run and regenerating one scenario:

```powershell
python scripts/generate_examples.py --resume
python scripts/generate_examples.py --scenario 01_catalog_continuity
```

The script first performs the project-specific model/function-calling check. It then writes one Markdown file per conversation and a `.tools.json` trace of actual tool calls/results to `examples/generated/`, records the configured model, and labels the files as real API executions. Raw generated output remains ignored by Git. Scenario 01 keeps the two original questions and adds a third explicitly about the whole matching catalog. Source-checked transcripts are preserved verbatim in [`examples/reviewed/`](examples/reviewed/); the prior rejected catalog output is retained in `examples/rejected/`. Supporting evidence and caveats are documented in [`docs/conversation_review.md`](docs/conversation_review.md).

### Live Gemini result

- Provider/interface: Gemini API through `google-genai`.
- Models: `gemini-2.5-flash` for the corrected scenario 01; `gemini-3.5-flash-lite` for unchanged scenarios 02-04.
- Completed scenarios: catalog continuity and specifications, privacy-limited order lookup, multi-turn online-return policy, and out-of-scope handling.
- The previous approval of scenario 01 was revoked: its second answer changed the GN-15 price and incorrectly generalized from eight displayed products to the entire budget range. See the corrected review record in `docs/conversation_review.md`; passing deterministic tests alone does not approve model responses.
- The regenerated scenario 01 (2026-11-05, 17:52 America/Sao_Paulo) preserves GN-15 at R$ 689,00 across turns, limits the initial electronics statement to the eight shown products, and queries the whole matching catalog with `electronics=yes` to find Shelby 107 at R$ 799,00. Its tool trace and all nine returned records were checked against the CSVs; the reviewed response was copied byte-for-byte from generated output.
- Operational observation: other model probes encountered intermittent API-capacity errors, so the executed model is recorded explicitly rather than described as a universal default.

## Source interpretation and known ambiguities

The original files were inspected before implementation. Detailed evidence is in [`docs/data_quality_notes.md`](docs/data_quality_notes.md). Important decisions are:

1. **Conflicting contacts:** page 2 lists `(67) 3341-4444`, while page 6 lists WhatsApp `(67) 3321-4500`. The cover and page 2 also disagree on whether the e-mail domain contains an accent. The agent reports the conflict and asks the customer to confirm with staff; it does not choose a definitive remote contact.
2. **Conflicting installment minimums:** the payment table says BRL 100.00 per credit installment. The detailed rules allow BRL 50.00 for up to 3 installments and BRL 80.00 for 4 to 6. Calculations below BRL 100.00 are therefore marked for manager confirmation instead of being approved automatically.
3. **Catalog state overrides physical stock:** a `coming_soon` item and a `discontinued` item both have positive stock. Only `status == active` and stock above zero is treated as available for sale.
4. **Returns need receipt facts:** orders have an order date and sometimes an estimated delivery date, but no actual receipt date or purchase channel. The agent asks for these facts and product condition instead of deciding eligibility from the order row.
5. **Historical totals are authoritative:** two stored order totals differ from today's list-price sum. The assistant reports the stored order total and does not recalculate a historical purchase using current prices.
6. **Promotion state comes from data:** campaign descriptions in the manual are not enough to claim a current discount. Only rows with `is_active == 1` are applied.

## Privacy and security boundaries

- Order lookup requires order ID plus exact registered e-mail. A nonexistent order and a wrong e-mail return the same response to reduce order-ID enumeration.
- Successful order output excludes name, phone number, e-mail, city, and the full customer row.
- This is still **prototype verification, not authentication**. Production should use a signed-in account or one-time code, rate limiting, audit logs, and explicit consent.
- User text, CSV values, product descriptions, and retrieved policies are treated as untrusted data in the system prompt. Tools are read-only and cannot execute arbitrary code or mutate an order.
- Messages sent to the configured Gemini API may contain the verification e-mail typed by the user. A production privacy review should minimize or tokenize this value before sending model requests.

## Limitations

- The completed live evaluation contains four curated scenarios; it is evidence of those executions, not a statistically comprehensive model-quality benchmark.
- Policy retrieval is lexical. It is appropriate for this short manual but may miss an unusual paraphrase.
- The CLI keeps history in memory only. It has no user accounts or persistence.
- It cannot place, reserve, cancel, exchange, return, or modify orders, and it does not register complaints.
- The CSV snapshot is not a real-time transactional system and concurrent stock changes are outside the prototype.
- Live Gemini calls depend on external capacity and quotas; deterministic tests remain the repeatable regression gate.
- Exact price copying and the scope of natural-language conclusions are instructed in the prompt; live output still requires source review. Tool tests do not guarantee that every model response follows those instructions.

## What I would improve with more time

1. Expand the four reviewed live scenarios into a larger evaluation set with measured tool-call accuracy, groundedness, clarification behavior, and refusal quality.
2. Replace e-mail matching with authenticated customer sessions or one-time codes.
3. Move catalog and order access behind a production API with authorization, rate limiting, observability, and freshness guarantees.
4. Add policy-source citations to customer replies and a staff workflow for resolving contradictory source content.
5. Add structured telemetry that redacts personal data and tracks tool errors without logging message content by default.
6. Add a small web or messaging-channel adapter only after the core behavior is proven.

## Use of AI coding assistants

OpenAI Codex was used as a development assistant to inspect the supplied files, propose the architecture, draft and revise code, create tests, and help write the documentation. Its outputs were not accepted blindly: source facts were checked against the original PDFs and CSVs, deterministic behavior was covered by tests, and ambiguous source rules were preserved instead of silently resolved. The candidate, **Pammela Vicenti Ribeiro**, is responsible for reviewing, understanding, running, and presenting the final work.

## Submission note

Public repository: [pammelavicenti/emporio-musica-ai-agent](https://github.com/pammelavicenti/emporio-musica-ai-agent).

The English delivery summary is in [`docs/submission_summary.md`](docs/submission_summary.md). The final PDF is [`Pammela Vicenti Ribeiro - AI Engineer - Full-Stack para Aplicações com IA Generativa.pdf`](<output/pdf/Pammela Vicenti Ribeiro - AI Engineer - Full-Stack para Aplicações com IA Generativa.pdf>); its filename follows the requested delivery format. To rebuild it, install `reportlab` and run `python scripts/build_submission_pdf.py`.

This local copy had no existing Git metadata, commits, or remotes when publication was prepared. Its Git history starts with the actual delivery preparation; no retroactive history was created. No e-mail or form submission has been sent. The repository must remain unchanged after the exact submission date and time, even if that timestamp is earlier than the process's final deadline. Future portfolio development belongs in a separate repository.
