import json
from datetime import datetime
from typing import Optional, Any
import re

def serialize_tool_output(output: Any) -> Any:
    """
    Recursively convert sets to lists in a dictionary/list structure.
    This is useful for JSON serialization of tool outputs that might contain sets.
    """
    if isinstance(output, dict):
        return {k: serialize_tool_output(v) for k, v in output.items()}
    elif isinstance(output, list):
        return [serialize_tool_output(i) for i in output]
    elif isinstance(output, set):
        return list(output)
    else:
        return output

def sanitize_log(text: str) -> str:
    """
    Remove ANSI escape sequences, carriage returns, and other terminal noise.
    """
    if not text:
        return ""
    
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)
    
    # Remove carriage returns that might be used for progress bars
    # This is a simple approach: replace \r with \n or just remove lines that are overwritten
    # For now, let's just strip \r to avoid weird formatting
    text = text.replace('\r', '\n')
    
    return text.strip()
