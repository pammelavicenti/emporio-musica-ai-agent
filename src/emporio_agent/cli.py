from __future__ import annotations

from dotenv import load_dotenv

from emporio_agent.agent import AgentError, SupportAgent
from emporio_agent.config import Settings
from emporio_agent.policies import PolicyStore
from emporio_agent.repository import DataSourceError, StoreRepository
from emporio_agent.tools import ToolDispatcher


def build_agent() -> SupportAgent:
    load_dotenv()
    settings = Settings.from_environment()
    settings.validate()
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "O pacote google-genai não está instalado. Execute: python -m pip install -e ."
        ) from exc

    repository = StoreRepository(settings.data_dir)
    policies = PolicyStore(settings.data_dir / "policy_sections.json")
    dispatcher = ToolDispatcher(repository, policies)
    client = genai.Client(api_key=settings.api_key)
    return SupportAgent(client, settings.model, dispatcher)


def main() -> None:
    try:
        agent = build_agent()
    except (ValueError, RuntimeError, DataSourceError) as exc:
        print(f"Erro de configuração: {exc}")
        raise SystemExit(2) from exc

    print("Empório da Música - Assistente virtual")
    print("Digite 'sair' para encerrar.\n")
    while True:
        try:
            message = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté mais!")
            break
        if message.casefold() in {"sair", "exit", "quit"}:
            print("Até mais!")
            break
        try:
            answer = agent.chat(message)
        except AgentError as exc:
            answer = str(exc)
        print(f"\nAssistente: {answer}\n")


if __name__ == "__main__":
    main()
