"""Native Expedition encounter handling (_handle_expedition_encounter).

Walk-to-NPC handling has been removed on purpose: the handler now only ever
tries the encounter's own Continue button. If Continue isn't offered, the
encounter is left alone -- there is no teleport-to-spawn/walk/dialogue
fallback anymore, so none of that is exercised here.
"""
import threading
import time
from unittest.mock import MagicMock

from core.runner_expedition import ExpeditionOps


class _Runner(ExpeditionOps):
    def __init__(self, task=None):
        self._current_task = task
        self._mouse = MagicMock()
        self._keyboard = MagicMock()
        self.logs = []

    def _log(self, m):
        self.logs.append(m)

    def _set_status(self, **kw):
        pass

    def _checkpoint(self, stop_event):
        return False

    def _interruptible_sleep(self, seconds, stop_event=None):
        pass


def _settled():
    """State as it stands once the pre-menu settle has already elapsed -- the
    handler defers on first sighting, so tests of the ACTIONS start here."""
    return {"handled_at": 0.0, "seen_at": 1.0}


def _wire(monkeypatch, *, marker=True, continue_offered=True):
    """Wires vision.find_image/find_color_run for a single encounter check.

    continue_offered controls the only branch _handle_expedition_encounter
    has left: whether the encounter's own Continue button is found.
    """
    from core import runner_expedition as rx

    def find_image(h, n, **k):
        if n == "expedition_encounter":
            return {"cx": 430, "cy": 80, "score": 0.96} if marker else None
        return None

    monkeypatch.setattr(rx.vision, "find_image", find_image)
    monkeypatch.setattr(
        rx.vision, "find_color_run",
        lambda *_a, **_k: {"cx": 575, "cy": 588} if continue_offered else None,
    )
    monkeypatch.setattr(rx.vision, "click_match", lambda m, h, match, **k: None)
    monkeypatch.setattr(rx.wm, "get_window_rect_screen", lambda h: (10, 20, 1152, 756))

    now = {"t": 1000.0}
    monkeypatch.setattr(rx.time, "sleep", lambda s: now.__setitem__("t", now["t"] + max(s, 0.05)))
    monkeypatch.setattr(rx.time, "time", lambda: now["t"])


def test_a_continue_ends_the_encounter_without_walking(monkeypatch):
    """The only path left: Continue is found, clicked, done -- no Settings,
    no teleport, no route, no dialogue."""
    _wire(monkeypatch, continue_offered=True)
    r = _Runner(task={"map": "Rose Kingdom"})

    out = r._handle_expedition_encounter(1, threading.Event(), _settled())

    assert r._mouse.click.called, "Continue must actually be clicked"
    assert not r._keyboard.tap.called, "no dialogue -- E should never be pressed"
    assert out["handled_at"] > 0.0, "the encounter must still be marked handled"
    assert any("no walk needed" in m for m in r.logs)


def test_without_a_continue_the_encounter_is_left_alone(monkeypatch):
    """No walk fallback anymore -- if Continue never shows up, there is
    genuinely nothing left to do."""
    _wire(monkeypatch, continue_offered=False)
    r = _Runner(task={"map": "Rose Kingdom"})

    out = r._handle_expedition_encounter(1, threading.Event(), _settled())

    r._mouse.click.assert_not_called()
    r._keyboard.tap.assert_not_called()
    assert out["handled_at"] > 0.0, "still marked handled so it is not retried forever"
    assert any("no Continue offered" in m for m in r.logs)


def test_an_unmapped_map_is_still_handled_by_its_continue(monkeypatch):
    """The Continue path never depended on a bundled route, so an unmapped
    map works exactly the same as a mapped one."""
    _wire(monkeypatch, continue_offered=True)
    r = _Runner(task={"map": "Somewhere Unmapped"})

    out = r._handle_expedition_encounter(1, threading.Event(), _settled())

    assert out["handled_at"] > 0.0
    assert any("no walk needed" in m for m in r.logs)


def test_no_marker_means_no_action(monkeypatch):
    _wire(monkeypatch, marker=False)
    r = _Runner(task={"map": "Rose Kingdom"})
    r._handle_expedition_encounter(1, threading.Event(), _settled())
    r._mouse.click.assert_not_called()


def test_cooldown_prevents_re_entry_while_the_marker_fades(monkeypatch):
    _wire(monkeypatch)
    r = _Runner(task={"map": "Rose Kingdom"})
    just_now = time.time()

    state = r._handle_expedition_encounter(1, threading.Event(),
                                            {"handled_at": just_now, "seen_at": 0.0})
    assert state["handled_at"] == just_now
    r._mouse.click.assert_not_called()


def test_missing_reference_image_leaves_the_feature_inert(monkeypatch):
    """No expedition_encounter.png -> behaves exactly as before this existed."""
    from core import runner_expedition as rx

    def raise_missing(h, n, **k):
        raise rx.vision.TemplateNotFound(n)

    _wire(monkeypatch)
    monkeypatch.setattr(rx.vision, "find_image", raise_missing)
    r = _Runner(task={"map": "Rose Kingdom"})

    r._handle_expedition_encounter(1, threading.Event(), _settled())
    r._mouse.click.assert_not_called()


# ---------------------------------------------------------------------------
# Lobby overlay: a modal over Play makes every Play click land on the modal
# (unrelated to encounter handling above -- kept as-is)
# ---------------------------------------------------------------------------

class _LobbyRunner:
    def __init__(self, overlay=None, missing=False):
        self._overlay, self._missing = overlay, missing
        self._mouse = MagicMock()
        self.logs = []

    def _log(self, m):
        self.logs.append(m)


def _lobby(monkeypatch, overlay=None, missing=False):
    from core import runner as rm
    from core.runner import MacroRunner

    r = _LobbyRunner(overlay, missing)
    r._dismiss_lobby_overlay = MacroRunner._dismiss_lobby_overlay.__get__(r, _LobbyRunner)

    def find_image_any(hwnd, names, **kw):
        if r._missing:
            raise rm.vision.TemplateNotFound(names[0])
        return (r._overlay, "update_log_close") if r._overlay else (None, None)

    monkeypatch.setattr(rm.vision, "find_image_any", find_image_any)
    monkeypatch.setattr(rm.vision, "click_match", lambda m, h, match, **k: r._mouse.click(match))
    monkeypatch.setattr(rm.time, "sleep", lambda s: None)
    return r


def test_lobby_overlay_is_closed_so_play_is_clickable(monkeypatch):
    r = _lobby(monkeypatch, overlay={"cx": 700, "cy": 160, "score": 0.97})
    assert r._dismiss_lobby_overlay(1) is True
    assert r._mouse.click.called
    assert any("covering Play" in m for m in r.logs)


def test_no_lobby_overlay_means_no_click(monkeypatch):
    r = _lobby(monkeypatch, overlay=None)
    assert r._dismiss_lobby_overlay(1) is False
    r._mouse.click.assert_not_called()


def test_lobby_overlay_check_is_optional(monkeypatch):
    """No update_log_close.png -> the check is inert, never an error."""
    r = _lobby(monkeypatch, missing=True)
    assert r._dismiss_lobby_overlay(1) is False
    r._mouse.click.assert_not_called()


# ---------------------------------------------------------------------------
# Teleport wait: sitting on the lobby is not "still loading"
# (unrelated to encounter handling above -- kept as-is)
# ---------------------------------------------------------------------------

class _TeleportRunner:
    def __init__(self):
        self.logs = []

    def _log(self, m):
        self.logs.append(m)

    def _set_status(self, **kw):
        pass


def _teleport(monkeypatch, screen):
    """screen: what each poll sees -- 'lobby', 'loading', or 'in_game'."""
    from core import runner as rm
    from core.runner import MacroRunner

    r = _TeleportRunner()
    r._wait_for_teleport_result = MacroRunner._wait_for_teleport_result.__get__(r, _TeleportRunner)
    state = {"poll": -1}

    def find_image(hwnd, name, **kw):
        if name == "nav_unitmanager":
            state["poll"] += 1
        i = min(state["poll"], len(screen) - 1)
        now = screen[i] if i >= 0 else "loading"
        if name == "nav_unitmanager":
            return {"score": 1.0} if now == "in_game" else None
        if name == "nav_play":
            return {"score": 0.95} if now == "lobby" else None
        return None

    monkeypatch.setattr(rm.vision, "find_image", find_image)
    monkeypatch.setattr(rm.time, "sleep", lambda s: None)
    return r


def test_sitting_on_the_lobby_stops_waiting_for_a_teleport(monkeypatch):
    """Matchmaking left, cancelled, or never took. No teleport is coming, and
    the matchmaking timeout is five minutes -- waiting it out achieves
    nothing."""
    r = _teleport(monkeypatch, ["lobby"] * 40)
    assert r._wait_for_teleport_result(1, threading.Event(), 60.0) == "lobby"


def test_the_lobby_still_drawn_as_a_teleport_begins_is_not_a_failure(monkeypatch):
    """The lobby lingers for a frame while the teleport starts, so one sighting
    must not abandon a teleport that is actually happening."""
    r = _teleport(monkeypatch, ["lobby"] * 6 + ["loading"] * 6 + ["in_game"])
    assert r._wait_for_teleport_result(1, threading.Event(), 60.0) == "ok"


def test_a_normal_slow_teleport_is_still_given_its_full_time(monkeypatch):
    r = _teleport(monkeypatch, ["loading"] * 8 + ["in_game"])
    assert r._wait_for_teleport_result(1, threading.Event(), 60.0) == "ok"
