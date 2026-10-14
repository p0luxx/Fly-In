class ParsingError(Exception):
    def __init__(self, error: str = "ParsingError ocurred"):
        self.error = error
        super().__init__(self.error)