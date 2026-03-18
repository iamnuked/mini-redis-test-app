from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "internal.arena.lane_b.api.app:create_app",
        factory=True,
        host=os.getenv("ARENA_LANE_B_HOST", "0.0.0.0"),
        port=int(os.getenv("ARENA_LANE_B_PORT", "8002")),
    )


if __name__ == "__main__":
    main()
