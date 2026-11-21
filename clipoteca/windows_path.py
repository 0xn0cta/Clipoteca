import os
import sys


def refresh_windows_user_path() -> None:
    """Make persisted user PATH updates visible to launchers with a stale environment."""
    if sys.platform != "win32":
        return

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            user_path, _ = winreg.QueryValueEx(key, "Path")
    except (ImportError, OSError):
        return

    if not isinstance(user_path, str) or not user_path:
        return

    process_entries = os.environ.get("PATH", "").split(os.pathsep)
    existing = {
        os.path.normcase(os.path.normpath(os.path.expandvars(entry.strip().strip('"'))))
        for entry in process_entries
        if entry.strip()
    }
    missing_entries = []
    for entry in os.path.expandvars(user_path).split(os.pathsep):
        entry = entry.strip().strip('"')
        if not entry:
            continue
        normalized = os.path.normcase(os.path.normpath(entry))
        if normalized not in existing:
            missing_entries.append(entry)
            existing.add(normalized)

    if missing_entries:
        os.environ["PATH"] = os.pathsep.join([*missing_entries, *process_entries])
