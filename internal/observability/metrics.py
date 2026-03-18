class Metrics:
    def __init__(self) -> None:
        self.connections_total = 0
        self.active_connections = 0
        self.requests_total = 0
        self.errors_total = 0

    def increment_connections(self) -> None:
        self.connections_total += 1

    def increment_active_connections(self) -> None:
        self.active_connections += 1

    def decrement_active_connections(self) -> None:
        if self.active_connections > 0:
            self.active_connections -= 1

    def increment_requests(self) -> None:
        self.requests_total += 1

    def increment_errors(self) -> None:
        self.errors_total += 1
