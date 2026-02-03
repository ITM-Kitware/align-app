from trame.decorators import TrameApp


@TrameApp()
class AlertsController:
    def __init__(self, server):
        self.server = server
        self.server.state.alert_message = ""
        self.server.state.alert_visible = False
        self.server.state.alert_timeout = -1

    def show(self, message: str, timeout: int = -1):
        with self.server.state:
            self.server.state.alert_message = message
            self.server.state.alert_timeout = timeout
            self.server.state.alert_visible = True
