from internal.command.command import Command
from internal.command.errors import CommandValidationError


class CommandParser:
    def parse(self, parts: list[str]) -> Command:
        if not parts:
            raise CommandValidationError("empty command")
        return Command(name=parts[0].upper(), arguments=parts[1:])
