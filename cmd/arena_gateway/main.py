from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "internal.arena.api.app:create_app",
        factory=True,
        host=os.getenv("ARENA_HOST", "0.0.0.0"),
        port=int(os.getenv("ARENA_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
