"""
Chrome interaction via AppleScript.

No Chrome extension needed — AppleScript can:
- Read all tab URLs and titles from any Chrome window
- Close windows
- Open new windows with specific URLs
"""

import json
import subprocess


def _run_applescript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript error: {result.stderr.strip()}")
    return result.stdout.strip()


def get_frontmost_window_tabs() -> list[dict]:
    """Get all tabs from Chrome's frontmost window."""
    script = '''
    tell application "Google Chrome"
        if (count of windows) is 0 then
            return "[]"
        end if
        set w to front window
        set tabList to {}
        repeat with t in tabs of w
            set tabInfo to "{" & quoted form of ("url:" & URL of t & "|title:" & title of t) & "}"
            set end of tabList to tabInfo
        end repeat
        set AppleScript's text item delimiters to "|||"
        return tabList as text
    end tell
    '''
    raw = _run_applescript(script)
    if not raw or raw == "[]":
        return []

    tabs = []
    for entry in raw.split("|||"):
        entry = entry.strip().strip("{}'")
        if not entry:
            continue
        parts = entry.split("|title:", 1)
        if len(parts) == 2:
            url = parts[0].replace("url:", "", 1)
            title = parts[1]
            tabs.append({"url": url, "title": title})

    return tabs


def close_frontmost_window():
    """Close Chrome's frontmost window."""
    script = '''
    tell application "Google Chrome"
        if (count of windows) > 0 then
            close front window
        end if
    end tell
    '''
    _run_applescript(script)


def open_tabs_in_new_window(urls: list[str]):
    """Open a list of URLs in a new Chrome window."""
    if not urls:
        return

    # First URL opens in a new window, rest open as new tabs
    first_url = urls[0]
    script = f'''
    tell application "Google Chrome"
        set newWindow to make new window
        set URL of active tab of newWindow to "{first_url}"
    '''

    for url in urls[1:]:
        script += f'''
        tell newWindow
            make new tab with properties {{URL:"{url}"}}
        end tell
        '''

    script += '''
    end tell
    '''
    _run_applescript(script)
    activate_chrome()


def activate_chrome():
    """Bring Chrome to the front."""
    _run_applescript('tell application "Google Chrome" to activate')


def is_chrome_running() -> bool:
    """Check if Chrome is running."""
    try:
        result = _run_applescript(
            'tell application "System Events" to (name of processes) contains "Google Chrome"'
        )
        return result.lower() == "true"
    except Exception:
        return False
