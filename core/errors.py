class BotError(Exception):
    """Base exception for the bot."""
    pass

class IntegrationError(BotError):
    """Raised when an external service fails."""
    pass
