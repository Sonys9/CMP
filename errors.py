class InitializingError(Exception):
    """
        Happens, when client could not initialized the connection.
    """
    pass

class AuthError(Exception):
    """
        Happens, when credentials are wrong.
    """
    pass