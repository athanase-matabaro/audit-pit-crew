#!/usr/bin/env python3
"""
Patch Mythril's util.py to handle network failures gracefully.

Mythril v0.23.0 calls solcx.get_installable_solc_versions() at import time (line 138 of util.py).
This causes the entire module import to fail if the network is unavailable.
This script patches the file to wrap the call in try/except with a fallback.
"""
import sys
import os

def patch_mythril_util():
    try:
        import mythril.ethereum.util as util_module
        util_path = util_module.__file__
    except ImportError:
        print("Mythril not installed, skipping patch")
        return False
    except Exception as e:
        # Mythril might fail to import due to network issues - find path manually
        import site
        for site_path in site.getsitepackages():
            candidate = os.path.join(site_path, 'mythril', 'ethereum', 'util.py')
            if os.path.exists(candidate):
                util_path = candidate
                break
        else:
            print(f"Could not find Mythril util.py: {e}")
            return False

    print(f"Patching Mythril util.py at: {util_path}")
    
    with open(util_path, 'r') as f:
        content = f.read()
    
    # Find and replace the problematic line
    old_code = "all_versions = solcx.get_installable_solc_versions()"
    
    new_code = """# PATCHED: Wrap network call in try/except to handle offline mode
try:
    all_versions = solcx.get_installable_solc_versions()
except Exception as _solcx_err:
    import logging as _mythril_logging
    _mythril_logging.getLogger(__name__).warning(
        f"Failed to fetch solc versions from network: {_solcx_err}. Using locally installed versions only."
    )
    # Fall back to locally installed versions
    try:
        all_versions = solcx.get_installed_solc_versions() or []
    except Exception:
        all_versions = []"""
    
    if old_code not in content:
        if "# PATCHED:" in content:
            print("Mythril util.py already patched")
            return True
        else:
            print("Could not find target code to patch in util.py")
            return False
    
    patched_content = content.replace(old_code, new_code)
    
    with open(util_path, 'w') as f:
        f.write(patched_content)
    
    print("Successfully patched Mythril util.py!")
    return True

if __name__ == "__main__":
    success = patch_mythril_util()
    sys.exit(0 if success else 1)
