from enum import StrEnum


class ScrollBehavior(StrEnum):
    PASS = "pass"
    PAUSE_1SEC = "pause_1sec"
    PAUSE_3SEC = "pause_3sec"
    STOP_AND_READ = "stop_and_read"


class ActionTaken(StrEnum):
    IGNORE = "ignore"
    SCREENSHOT = "screenshot"
    CLICK = "click"
    SHARE = "share"
