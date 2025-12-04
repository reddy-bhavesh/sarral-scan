
import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("Verifying backend modules...")

try:
    print("Importing app.core.tool_config...")
    from app.core.tool_config import TOOL_CONFIG
    print("✅ app.core.tool_config imported successfully.")
except Exception as e:
    print(f"❌ Failed to import app.core.tool_config: {e}")
    sys.exit(1)

try:
    print("Importing app.core.exit_codes...")
    from app.core.exit_codes import EXIT_CODE_MAP, get_exit_message
    print("✅ app.core.exit_codes imported successfully.")
except Exception as e:
    print(f"❌ Failed to import app.core.exit_codes: {e}")
    sys.exit(1)

try:
    print("Importing app.services.utils...")
    from app.services.utils import serialize_tool_output, sanitize_log
    print("✅ app.services.utils imported successfully.")
except Exception as e:
    print(f"❌ Failed to import app.services.utils: {e}")
    sys.exit(1)

try:
    print("Importing app.services.post_processing...")
    from app.services.post_processing import PostProcessor
    print("✅ app.services.post_processing imported successfully.")
except Exception as e:
    print(f"❌ Failed to import app.services.post_processing: {e}")
    sys.exit(1)

try:
    print("Importing app.services.scan_manager...")
    # We might not be able to instantiate ScanManager without a DB connection, but we can check imports
    from app.services.scan_manager import ScanManager
    print("✅ app.services.scan_manager imported successfully.")
except Exception as e:
    print(f"❌ Failed to import app.services.scan_manager: {e}")
    sys.exit(1)

print("\n🎉 All backend modules verified successfully!")
