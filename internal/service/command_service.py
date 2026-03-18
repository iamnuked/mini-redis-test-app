from internal.command.command import Command
from internal.protocol.resp.types import RespValue


class CommandService:
    def execute(self, command: Command) -> RespValue:
        raise NotImplementedError("Command execution is not implemented yet")
