import threading

from core import runner
from core import vision
from core.runner import MacroRunner


class PortalProbe:
    def __init__(self):
        self.clicked = []
        self.logs = []
        self.statuses = []
        self.spam_back_calls = 0

    def _log(self, message):
        self.logs.append(message)

    def _set_status(self, **kwargs):
        self.statuses.append(kwargs)

    def _checkpoint(self, _stop):
        return False

    def _spam_back_until_gone(self, *_args):
        self.spam_back_calls += 1
        return True

    def _click_found_image(self, _hwnd, name, timeout, _stop, *args, **kwargs):
        self.clicked.append((name, timeout))
        return {"score": 0.99}


def test_reach_portal_selected_clicks_items_card_then_activate(monkeypatch):
    probe = PortalProbe()
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)

    assert MacroRunner._reach_portal_selected(
        probe, 123, threading.Event(), {"mode": "portal"}
    ) is True

    assert [name for name, _timeout in probe.clicked] == [
        "item_portals", "tier5_portal", "activate_select_portal",
    ]
    assert probe.spam_back_calls == 0


class PortalMissingProbe(PortalProbe):
    """Same as PortalProbe, but a chosen step never shows up."""
    def __init__(self, fail_on):
        super().__init__()
        self.fail_on = fail_on

    def _click_found_image(self, _hwnd, name, timeout, _stop, *args, **kwargs):
        self.clicked.append((name, timeout))
        if name == self.fail_on:
            return None
        return {"score": 0.99}


def test_reach_portal_selected_backs_out_when_a_step_is_missing(monkeypatch):
    probe = PortalMissingProbe(fail_on="tier5_portal")
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)

    assert MacroRunner._reach_portal_selected(
        probe, 123, threading.Event(), {"mode": "portal"}
    ) is False

    assert probe.spam_back_calls == 1
    # Activate Portal never attempted -- the card wasn't there to click.
    assert "activate_select_portal" not in [name for name, _t in probe.clicked]


class ReselectProbe:
    def __init__(self, drop_notice_found=True, teleport_result="ok"):
        self.clicked = []
        self.logs = []
        self.statuses = []
        self._drop_notice_found = drop_notice_found
        self._teleport_result = teleport_result
        self.teleport_waits = []
        self.disconnect_calls = 0

    def _log(self, message):
        self.logs.append(message)

    def _set_status(self, **kwargs):
        self.statuses.append(kwargs)

    def _checkpoint(self, _stop):
        return False

    def _click_found_image(self, _hwnd, name, timeout, _stop, *args, **kwargs):
        self.clicked.append((name, timeout))
        if name == "tier5_portal_win" and not self._drop_notice_found:
            return None
        return {"score": 0.99}

    def _wait_for_teleport_result(self, _hwnd, _stop, timeout):
        self.teleport_waits.append(timeout)
        return self._teleport_result

    def _handle_disconnect(self, *_args):
        self.disconnect_calls += 1


def test_reselect_portal_full_sequence_on_a_win(monkeypatch):
    probe = ReselectProbe(drop_notice_found=True, teleport_result="ok")
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)

    assert MacroRunner._reselect_portal_and_reenter(
        probe, 123, threading.Event(), {"mode": "portal"}, {}
    ) is True

    assert [name for name, _t in probe.clicked] == [
        "tier5_portal_win", "select_portal", "tier5_portal", "final_select_portal",
    ]
    assert probe.teleport_waits == [runner.SOLO_TELEPORT_PER_ATTEMPT_TIMEOUT]
    assert any("Back in the next Tier 5 portal" in m for m in probe.logs)


def test_reselect_portal_continues_without_a_drop_notice(monkeypatch):
    """A loss drops nothing -- the notice search comes up empty, but Select
    Portal is still tried regardless (best-effort, not a hard failure)."""
    probe = ReselectProbe(drop_notice_found=False, teleport_result="ok")
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)

    assert MacroRunner._reselect_portal_and_reenter(
        probe, 123, threading.Event(), {"mode": "portal"}, {}
    ) is True

    assert "select_portal" in [name for name, _t in probe.clicked]
    assert any("No portal-drop notice seen" in m for m in probe.logs)


def test_reselect_portal_handles_a_disconnect(monkeypatch):
    probe = ReselectProbe(drop_notice_found=True, teleport_result="disconnected")
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)

    assert MacroRunner._reselect_portal_and_reenter(
        probe, 123, threading.Event(), {"mode": "portal"}, {}
    ) is False
    assert probe.disconnect_calls == 1


class MouseProbe:
    def __init__(self):
        self.moves = []

    def move_to(self, x, y):
        self.moves.append((x, y))


class MatchResultProbe:
    """Mirrors test_runner_tower.py's MatchResultProbe -- same shared
    _handle_match_result path, just asserting the Portal branch is taken
    instead of Repeat Stage / Next_Floor / Repeat_Floor."""
    def __init__(self):
        self.logs = []
        self.statuses = []
        self.reselect_calls = []
        self._mouse = MouseProbe()
        self._coords = {"unit_info_reset_x": 11, "unit_info_reset_y": 22}
        self._act4_wants_in = False

    def _log(self, message):
        self.logs.append(message)

    def _note_win_for_crafting(self, *_args):
        return None

    def _release_quick_place_shift(self):
        return None

    def _set_status(self, **kwargs):
        self.statuses.append(kwargs)

    def _capture_result_screenshot(self, _hwnd):
        return None

    def _finish_match_result_background(self, *_args):
        return None

    def _dismiss_reward_card_if_found(self, _hwnd):
        return False

    def _clear_result_obtainment_modal(self, *_args):
        return True

    def _reselect_portal_and_reenter(self, _hwnd, _stop, task, webhook):
        self.reselect_calls.append((task.get("mode"), webhook))
        return True

    def _relic_dropped(self, _hwnd):
        return False


class ImmediateThread:
    def __init__(self, target, args=(), daemon=None, **_kwargs):
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self):
        self.target(*self.args)


def test_handle_match_result_uses_select_portal_not_repeat_stage(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(runner.wm, "get_window_rect_screen", lambda _hwnd: (100, 200, 300, 400))
    monkeypatch.setattr(runner.threading, "Thread", ImmediateThread)

    win_probe = MatchResultProbe()
    assert MacroRunner._handle_match_result(
        win_probe, 123, threading.Event(), {"mode": "portal", "map": "Tier 5"},
        "win", "1m 2s", {}, repeat=True
    ) is True
    assert win_probe.reselect_calls == [("portal", {})]

    loss_probe = MatchResultProbe()
    assert MacroRunner._handle_match_result(
        loss_probe, 123, threading.Event(), {"mode": "portal", "map": "Tier 5"},
        "loss", "1m 2s", {}, repeat=True
    ) is True
    assert loss_probe.reselect_calls == [("portal", {})]
