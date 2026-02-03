from trame.decorators import TrameApp


@TrameApp()
class AlertsController:
    def __init__(self, server):
        self.server = server
        self.server.state.alert_messages = []

    def show(self, message: str, timeout: int = -1):
        self.server.state.alert_messages = [
            *self.server.state.alert_messages,
            {"text": message, "timeout": timeout},
        ]
