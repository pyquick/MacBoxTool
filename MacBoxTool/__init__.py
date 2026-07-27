"""MacBoxTool package entry point."""


def main():
    """Import the application only when it is launched."""
    from .app_entry import main as application_main

    return application_main()
