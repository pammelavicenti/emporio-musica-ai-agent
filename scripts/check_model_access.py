from __future__ import annotations

from dotenv import load_dotenv
from google import genai

from emporio_agent.config import Settings
from emporio_agent.model_access import ModelAccessError, validate_model_access


def main() -> None:
    load_dotenv()
    settings = Settings.from_environment()
    if not settings.api_key:
        print("GEMINI_API_KEY is not configured.")
        raise SystemExit(2)
    client = genai.Client(api_key=settings.api_key)
    if not settings.model:
        try:
            catalog = client.models.list()
        except Exception as exc:
            print("Could not list Gemini models. Check the API key and connection.")
            raise SystemExit(2) from exc
        model_ids = sorted(
            item.name.removeprefix("models/") for item in catalog if item.name
        )
        print("Models listed for this account/project:")
        for model_id in model_ids:
            print(f"- {model_id}")
        print("Set GEMINI_MODEL in .env, then run this command again to probe it.")
        raise SystemExit(2)
    try:
        result = validate_model_access(client, settings.model)
    except ModelAccessError as exc:
        print(f"Model access check failed: {exc}")
        raise SystemExit(2) from exc
    except Exception as exc:
        print("Gemini API check failed. Check the API key, model, and connection.")
        raise SystemExit(2) from exc
    print(f"Model confirmed for this account/project: {result['model']}")
    print("Gemini API function calling: confirmed")


if __name__ == "__main__":
    main()
