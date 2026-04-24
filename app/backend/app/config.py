from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "phish-detector-api"
    cors_allow_origins: str = "http://localhost:3000"
    cors_origins: str = ""
    frontend_origin: str = ""

    @property
    def resolved_cors_origins(self) -> list[str]:
        """Resolve CORS origins from env in a deployment-friendly order.

        Priority and merge behavior:
        - Always allow localhost:3000 for local frontend development.
        - Include values from `cors_allow_origins` (legacy support).
        - Include values from `cors_origins` (preferred comma-separated env).
        - Include `frontend_origin` (single deployed frontend URL).
        """
        values = []
        if self.cors_allow_origins:
            values.extend(self.cors_allow_origins.split(","))
        if self.cors_origins:
            values.extend(self.cors_origins.split(","))
        if self.frontend_origin:
            values.append(self.frontend_origin)
        values.append("http://localhost:3000")

        deduped: list[str] = []
        seen = set()
        for value in values:
            item = value.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped


settings = Settings()
