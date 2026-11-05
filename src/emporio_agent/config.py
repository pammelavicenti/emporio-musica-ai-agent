from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    data_dir: Path

    @classmethod
    def from_environment(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[2]
        data_dir = Path(
            os.getenv("EMPORIO_DATA_DIR", str(project_root / "data"))
        ).expanduser()
        return cls(
            api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            model=os.getenv("GEMINI_MODEL", "").strip(),
            data_dir=data_dir,
        )

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY não está configurada. Copie .env.example para .env "
                "e adicione sua chave."
            )
        if not self.model:
            raise ValueError(
                "GEMINI_MODEL não está configurado. Use a checagem de acesso para "
                "selecionar um modelo disponível na sua conta."
            )
        if not self.data_dir.is_dir():
            raise ValueError(f"A pasta de dados não existe: {self.data_dir}")
