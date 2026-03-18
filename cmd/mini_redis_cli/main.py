from internal.config.runtime_config import RuntimeConfig


def main() -> int:
    _ = RuntimeConfig.default()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
