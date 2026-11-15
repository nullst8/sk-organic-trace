from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anchor_rpc_url: str | None = None
    anchor_private_key: str | None = None
    anchor_contract_address: str | None = None
    anchor_chain_id: int | None = None
    anchor_force_local: bool = False
    # Public origin used inside QR codes, e.g. https://trace.example.org
    public_base_url: str | None = None

    @property
    def rpc_configured(self) -> bool:
        return bool(
            self.anchor_rpc_url
            and self.anchor_private_key
            and self.anchor_contract_address
            and not self.anchor_force_local
        )


settings = Settings()
