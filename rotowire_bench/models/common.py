class ModelError(RuntimeError):
    def __init__(self, status, message, *, attempted=True):
        super().__init__(message)
        self.status = status
        self.attempted = attempted


class RequestBudgetReached(ModelError):
    def __init__(self):
        super().__init__("blocked", "Request budget reached; resume with a larger request limit", attempted=False)
