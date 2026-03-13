"""
Workspace Manager menu bar app.

- Shows current Space name in menu bar
- Global hotkey (Cmd+Shift+K) to shelve Chrome tabs
- Dropdown to restore shelved bundles
- Space renaming
"""

import threading
import time

import requests
import rumps

from chrome_bridge import (
    activate_chrome,
    close_frontmost_window,
    get_frontmost_window_tabs,
    is_chrome_running,
    open_tabs_in_new_window,
)

BACKEND_URL = "http://localhost:8001"
POLL_INTERVAL = 2  # seconds


class WorkspaceManagerApp(rumps.App):
    def __init__(self):
        super().__init__("⌂", quit_button=None)
        self._current_space_name = "..."
        self._bundles = []
        self._space_index = None

        # Build initial menu
        self.menu = [
            rumps.MenuItem("Shelve Window (⌘⇧K)", callback=self.on_shelve),
            None,  # separator
            rumps.MenuItem("Shelved Sessions", callback=None),
            None,
            rumps.MenuItem("Rename This Space", callback=self.on_rename_space),
            None,
            rumps.MenuItem("Quit", callback=self.on_quit),
        ]

        # Start background threads
        self._setup_global_hotkey()
        self._start_space_monitor()
        self._refresh_bundles()

    def _setup_global_hotkey(self):
        """Register Cmd+Shift+K as global hotkey via NSEvent monitor."""
        def monitor_thread():
            try:
                from AppKit import NSEvent, NSKeyDownMask
                from AppKit import (
                    NSCommandKeyMask,
                    NSShiftKeyMask,
                )

                def handler(event):
                    flags = event.modifierFlags()
                    key_code = event.keyCode()
                    # K = keyCode 40, check Cmd+Shift
                    if (key_code == 40
                            and flags & NSCommandKeyMask
                            and flags & NSShiftKeyMask):
                        self.on_shelve(None)
                    return event

                NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                    NSKeyDownMask, handler
                )

                # Keep thread alive (NSEvent monitor needs a run loop)
                from AppKit import NSRunLoop, NSDate
                while True:
                    NSRunLoop.currentRunLoop().runUntilDate_(
                        NSDate.dateWithTimeIntervalSinceNow_(1)
                    )
            except ImportError:
                print("Warning: pyobjc not available, global hotkey disabled")

        t = threading.Thread(target=monitor_thread, daemon=True)
        t.start()

    def _start_space_monitor(self):
        """Poll for Space changes and update title."""
        def poll():
            while True:
                try:
                    resp = requests.get(f"{BACKEND_URL}/active-space", timeout=2)
                    if resp.ok:
                        data = resp.json()
                        new_name = data.get("name", "...")
                        new_index = data.get("index")
                        if new_name != self._current_space_name:
                            self._current_space_name = new_name
                            self._space_index = new_index
                            self.title = f"⌂ {new_name}"
                except requests.RequestException:
                    pass
                time.sleep(POLL_INTERVAL)

        t = threading.Thread(target=poll, daemon=True)
        t.start()

    def _refresh_bundles(self):
        """Fetch bundles from backend and update menu."""
        def refresh():
            while True:
                try:
                    resp = requests.get(f"{BACKEND_URL}/bundles", timeout=5)
                    if resp.ok:
                        self._bundles = resp.json()
                        self._update_bundle_menu()
                except requests.RequestException:
                    pass
                time.sleep(5)

        t = threading.Thread(target=refresh, daemon=True)
        t.start()

    def _update_bundle_menu(self):
        """Rebuild the shelved sessions submenu."""
        # Clear existing bundle items
        sessions_key = "Shelved Sessions"
        if sessions_key in self.menu:
            submenu = self.menu[sessions_key]
            submenu.clear()

            if not self._bundles:
                submenu.add(rumps.MenuItem("(empty)"))
                return

            for bundle in self._bundles[:20]:
                name = bundle.get("name", "Untitled")
                tab_count = bundle.get("tab_count", 0)
                bundle_id = bundle.get("id")
                restored = bundle.get("restored_at")

                label = f"{name} ({tab_count} tabs)"
                if restored:
                    label += " ✓"

                item = rumps.MenuItem(label, callback=self._make_restore_callback(bundle_id))
                submenu.add(item)

            submenu.add(None)  # separator
            submenu.add(rumps.MenuItem("Clear All", callback=self.on_clear_all))

    def _make_restore_callback(self, bundle_id):
        def callback(_):
            self._restore_bundle(bundle_id)
        return callback

    def on_shelve(self, _):
        """Shelve all tabs in Chrome's frontmost window."""
        if not is_chrome_running():
            rumps.notification(
                "Workspace Manager", "", "Chrome is not running.", sound=False
            )
            return

        tabs = get_frontmost_window_tabs()
        if not tabs:
            rumps.notification(
                "Workspace Manager", "", "No tabs in frontmost window.", sound=False
            )
            return

        try:
            payload = {
                "tabs": tabs,
                "space_index": self._space_index,
            }
            resp = requests.post(
                f"{BACKEND_URL}/shelve", json=payload, timeout=10
            )
            if resp.ok:
                data = resp.json()
                name = data.get("name", "Untitled")
                count = data.get("tab_count", 0)
                close_frontmost_window()
                rumps.notification(
                    "Workspace Manager",
                    f"Shelved: {name}",
                    f"{count} tabs saved.",
                    sound=False,
                )
            else:
                rumps.notification(
                    "Workspace Manager", "", f"Shelve failed: {resp.status_code}", sound=False
                )
        except requests.RequestException as e:
            rumps.notification(
                "Workspace Manager", "", f"Backend error: {e}", sound=False
            )

    def _restore_bundle(self, bundle_id: str):
        """Restore a shelved bundle."""
        try:
            resp = requests.post(
                f"{BACKEND_URL}/restore/{bundle_id}", timeout=10
            )
            if resp.ok:
                data = resp.json()
                urls = [t["url"] for t in data.get("tabs", [])]
                if urls:
                    open_tabs_in_new_window(urls)
                    rumps.notification(
                        "Workspace Manager",
                        f"Restored: {data.get('name', '')}",
                        f"{len(urls)} tabs opened.",
                        sound=False,
                    )
            else:
                rumps.notification(
                    "Workspace Manager", "", f"Restore failed: {resp.status_code}", sound=False
                )
        except requests.RequestException as e:
            rumps.notification(
                "Workspace Manager", "", f"Error: {e}", sound=False
            )

    def on_rename_space(self, _):
        """Rename the current Space."""
        if self._space_index is None:
            rumps.notification(
                "Workspace Manager", "", "Could not detect current Space.", sound=False
            )
            return

        response = rumps.Window(
            message=f"Rename Space {self._space_index}:",
            title="Rename Space",
            default_text=self._current_space_name,
            ok="Save",
            cancel="Cancel",
        ).run()

        if response.clicked:
            new_name = response.text.strip()
            if new_name:
                try:
                    requests.put(
                        f"{BACKEND_URL}/spaces/{self._space_index}/name",
                        json={"name": new_name},
                        timeout=5,
                    )
                    self._current_space_name = new_name
                    self.title = f"⌂ {new_name}"
                except requests.RequestException:
                    pass

    def on_clear_all(self, _):
        """Delete all shelved bundles."""
        for bundle in self._bundles:
            try:
                requests.delete(
                    f"{BACKEND_URL}/bundles/{bundle['id']}", timeout=5
                )
            except requests.RequestException:
                pass
        self._bundles = []
        self._update_bundle_menu()

    def on_quit(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    WorkspaceManagerApp().run()
