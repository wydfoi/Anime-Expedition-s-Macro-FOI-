"""Portal mode (Tier 5 only): the main screen's own Items tab -> the Tier 5
portal card -> Activate Portal -> the same solo Start/teleport tail every
other mode already uses. Repeats are shorter -- the win screen's own Select
Portal button jumps straight to a portal-selection screen, where picking the
card again and confirming with Select drops directly back into the next
match, with no separate Activate Portal or Start click that time.

Split out of core/runner.py mechanically -- a mixin providing part of
MacroRunner's behavior (see core/runner.py, which composes the mixins).
Methods here run with MacroRunner's full self: shared state and helpers
(_log, _checkpoint, _click_found_image, _wait_for_teleport_result,
_handle_disconnect, ...) resolve normally.
"""
import threading
import time

from . import vision
from .runner_constants import *  # noqa: F401,F403 -- the shared constants namespace


class PortalOps:
    def _reach_portal_selected(self, hwnd, stop_event: threading.Event, task: dict) -> bool:
        """Main screen -> Items tab -> the Tier 5 portal card -> Activate
        Portal, as one restartable unit. Leaves Start itself to the same
        _click_start_and_wait_teleport every other solo mode already uses
        (see _enter_selected_stage's mode != "portal" check, which skips the
        Select Stage confirm click Portal has no equivalent of) -- Portal's
        Start button is the same nav_start, no special handling needed.
        """
        self._set_status(action="Opening Items...")
        if self._click_found_image(hwnd, "item_portals", PORTAL_STEP_TIMEOUT, stop_event) is None:
            self._spam_back_until_gone(hwnd, stop_event)
            return False
        if self._checkpoint(stop_event):
            return False
        time.sleep(SETTLE_DELAY)

        self._set_status(action="Selecting the Tier 5 portal...")
        if self._click_found_image(hwnd, "tier5_portal", PORTAL_STEP_TIMEOUT, stop_event) is None:
            self._spam_back_until_gone(hwnd, stop_event)
            return False
        if self._checkpoint(stop_event):
            return False
        time.sleep(SETTLE_DELAY)

        self._set_status(action="Activating the portal...")
        if self._click_found_image(hwnd, "activate_select_portal", PORTAL_STEP_TIMEOUT, stop_event) is None:
            self._spam_back_until_gone(hwnd, stop_event)
            return False
        if self._checkpoint(stop_event):
            return False
        time.sleep(SETTLE_DELAY)
        return not self._checkpoint(stop_event)

    def _reselect_portal_and_reenter(self, hwnd, stop_event: threading.Event, task: dict,
                                       webhook: dict = None) -> bool:
        """The repeat path after a Tier 5 result: dismiss the portal-drop
        notice if one showed (win only -- a loss drops nothing, so this is
        best-effort and never fails the run on its own), click the result
        screen's own Select Portal button (which replaces Repeat Stage
        here), pick the card again on the portal-selection screen that
        opens, and confirm with Select -- which drops straight back into
        the next match with no separate Activate Portal or Start needed.
        """
        self._set_status(action="Dismissing the portal drop...")
        if self._click_found_image(hwnd, "tier5_portal_win", PORTAL_DROP_TIMEOUT, stop_event) is None:
            self._log('[Macro] No portal-drop notice seen (expected on a loss -- Tier 5 only '
                       'drops one on a win) -- continuing to Select Portal regardless.')
        if self._checkpoint(stop_event):
            return False
        time.sleep(SETTLE_DELAY)

        self._set_status(action="Clicking Select Portal...")
        if self._click_found_image(hwnd, "select_portal", PORTAL_STEP_TIMEOUT, stop_event) is None:
            return False
        if self._checkpoint(stop_event):
            return False
        time.sleep(SETTLE_DELAY)

        self._set_status(action="Reselecting the Tier 5 portal...")
        if self._click_found_image(hwnd, "tier5_portal", PORTAL_STEP_TIMEOUT, stop_event) is None:
            return False
        if self._checkpoint(stop_event):
            return False
        time.sleep(SETTLE_DELAY)

        self._set_status(action="Confirming portal selection...")
        if self._click_found_image(hwnd, "final_select_portal", PORTAL_STEP_TIMEOUT, stop_event) is None:
            return False
        if self._checkpoint(stop_event):
            return False

        # No Start click here -- Select drops straight back into the match,
        # so this only needs the same teleport-confirm wait every solo
        # Start click ends with, not another Start attempt of its own.
        self._log('[Macro] Waiting to teleport in-game (watching for "nav_unitmanager", up to '
                   f'{SOLO_TELEPORT_PER_ATTEMPT_TIMEOUT:.0f}s)...')
        self._set_status(action='Waiting to teleport in-game ("nav_unitmanager")...')
        result = self._wait_for_teleport_result(hwnd, stop_event, SOLO_TELEPORT_PER_ATTEMPT_TIMEOUT)
        if result == "ok":
            self._log("[Macro] Back in the next Tier 5 portal.")
            return True
        if result == "disconnected":
            self._handle_disconnect(hwnd, stop_event, webhook, task)
            return False
        self._log('[Macro] Never made it back into a match after reselecting the portal -- stopping.')
        return False
