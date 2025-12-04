
EXIT_CODE_MAP = {
    0: "Success",
    1: "General Error",
    2: "Misuse of Shell Builtins",
    126: "Command Invoked Cannot Execute",
    127: "Command Not Found",
    128: "Invalid Exit Argument",
    130: "Script Terminated by Control-C",
    137: "Process Killed (OOM or Timeout)",
    124: "Command Timed Out",
    255: "Exit Status Out of Range"
}

def get_exit_message(code: int) -> str:
    return EXIT_CODE_MAP.get(code, f"Unknown Error (Code: {code})")
