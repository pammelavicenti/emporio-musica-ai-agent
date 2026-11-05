from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from emporio_agent.cli import build_agent
from emporio_agent.config import Settings
from emporio_agent.model_access import ModelAccessError, validate_model_access


SCENARIOS = {
    "01_catalog_continuity": [
        "Quais opções de violões disponíveis custando até R$ 1.000?",
        "Desses, quais têm cordas de nylon e algum deles tem eletrônica?",
        "E considerando todo o catálogo, há algum violão disponível até R$ 1.000 com eletrônica?",
    ],
    "02_order_lookup": [
        (
            "Qual é o status do pedido 8? O e-mail cadastrado é "
            "anacarol.ferreira@coldmail.com."
        )
    ],
    "03_return_policy_continuity": [
        "Comprei um instrumento e me arrependi. Posso devolver?",
        "A compra foi online, recebi ontem e o instrumento está sem uso na embalagem.",
    ],
    "04_out_of_scope": [
        "Vocês vendem pedais de guitarra? E qual é a previsão do tempo para amanhã?"
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip transcript files that already exist.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=SCENARIOS,
        help="Generate only the selected scenario; may be supplied more than once.",
    )
    args = parser.parse_args()
    load_dotenv()
    output_dir = Path(__file__).resolve().parents[1] / "examples" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_environment()
    try:
        settings.validate()
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        raise SystemExit(2) from exc
    model = settings.model
    try:
        validate_model_access(genai.Client(api_key=settings.api_key), model)
    except ModelAccessError as exc:
        print(f"Model access check failed: {exc}")
        raise SystemExit(2) from exc
    except Exception as exc:
        print("Gemini API check failed. Check the API key, model, and connection.")
        raise SystemExit(2) from exc
    timestamp = datetime.now(timezone.utc).isoformat()

    for name, messages in SCENARIOS.items():
        if args.scenario and name not in args.scenario:
            continue
        output_file = output_dir / f"{name}.md"
        if args.resume and output_file.exists():
            print(f"Skipped existing {output_file}")
            continue
        agent = build_agent()
        lines = [
            f"# Real LLM transcript - {name.replace('_', ' ')}",
            "",
            f"- Executed at: {timestamp}",
            f"- Model: `{model}`",
            "- Interface: Gemini API with local function tools",
            "",
        ]
        for message in messages:
            answer = agent.chat(message)
            lines.extend(
                (f"**Customer:** {message}", "", f"**Assistant:** {answer}", "")
            )
        output_file.write_text("\n".join(lines), encoding="utf-8")
        # Keep actual calls/results so source review can verify which catalog
        # pages or specification filters supported the natural-language claims.
        trace = []
        for content in agent.history:
            for part in content.parts or []:
                if part.function_call is not None:
                    trace.append({"call": part.function_call.model_dump(exclude_none=True)})
                if part.function_response is not None:
                    trace.append({"result": part.function_response.model_dump(exclude_none=True)})
        output_file.with_suffix(".tools.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Wrote {output_file}")


if __name__ == "__main__":
    main()
