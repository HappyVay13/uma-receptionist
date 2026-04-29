def usage_context_is_non_billable(channel: str, source: str = "runtime") -> bool:
    ch = str(channel or "").strip().lower()
    src = str(source or "runtime").strip().lower()
    if ch in {"dev", "test", "debug"}:
        return True
    if src in {"dev", "dev_ui", "test", "debug"}:
        return True
    return False


def usage_event_is_billable(channel: str, source: str = "runtime") -> bool:
    return not usage_context_is_non_billable(channel, source)
