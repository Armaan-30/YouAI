"""A bounded command router: tasks execute from explicit input, never model guesses."""
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo(os.getenv("YOUAI_TIMEZONE", "Asia/Kolkata"))
NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
           "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
           "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "sixty": 60}
DURATION = r"(\d+(?:\.\d+)?|" + "|".join(NUMBERS) + r")\s+(seconds?|minutes?|hours?|days?)"

def seconds(amount, unit):
    value = NUMBERS.get(amount.lower())
    value = float(amount) if value is None else value
    result = value * {"second":1, "minute":60, "hour":3600, "day":86400}[unit.lower().rstrip("s")]
    if not 1 <= result <= 365 * 86400:
        raise ValueError("Choose a duration between one second and 365 days.")
    return result

def describe(rows, label):
    if not rows:
        return f"You have no {label}."
    return " ".join(f"{label.rstrip('s').capitalize()} {r['id']}: {r['content']}." for r in rows[:5])

def execute(prompt, key, store, now=None):
    now = now or datetime.now(ZONE)
    text = prompt.strip()
    clean = text.rstrip(".!?").strip()
    note = re.fullmatch(r"(?:save|take|make|create) (?:a )?note\s*[:,-]?\s+(.+)", text, re.I | re.S)
    if note:
        content = note[1].strip()
        def save(db):
            ident = db.execute("INSERT INTO notes(content) VALUES (?)", (content,)).lastrowid
            return f"Saved note {ident}: {content}"
        return store.perform(key, prompt, save)
    if re.fullmatch(r"(?:read|show|list)(?: me)? (?:my |the )?notes", clean, re.I):
        return describe(store.notes(), "notes")
    search = re.fullmatch(r"(?:find|search)(?: my)? notes (?:about|for|containing) (.+)", clean, re.I)
    if search:
        return describe(store.search_notes(search[1]), "matching notes")
    if re.fullmatch(r"(?:read|show|list)(?: me)? (?:my |the )?(?:reminders|timers)", clean, re.I):
        items = store.reminders()
        if not items:
            return "You have no pending reminders or timers."
        return " ".join(
            f"Reminder {r['id']}: {r['content']}, {datetime.fromtimestamp(r['due_at'], ZONE).strftime('%d %b at %I:%M %p')}."
            for r in items[:5])
    cancel = re.fullmatch(r"cancel (?:reminder|timer) (\d+)", clean, re.I)
    if cancel:
        def stop(db):
            changed = db.execute("UPDATE reminders SET status='cancelled' WHERE id=? AND status='pending'", (int(cancel[1]),)).rowcount
            return f"Cancelled reminder {cancel[1]}." if changed else "That reminder is not pending."
        return store.perform(key, prompt, stop)

    due = None
    title = None
    timer = re.fullmatch(r"(?:set|start)(?: a)? timer (?:for )?" + DURATION, clean, re.I)
    before = re.fullmatch(r"remind me in " + DURATION + r" to (.+)", clean, re.I | re.S)
    after = re.fullmatch(r"remind me to (.+) in " + DURATION, clean, re.I | re.S)
    dated = re.fullmatch(r"remind me (today|tomorrow) at (\d{1,2})(?::(\d{2}))?\s*(am|pm)? to (.+)", clean, re.I | re.S)
    try:
        if timer:
            due = now + timedelta(seconds=seconds(timer[1], timer[2]))
            title = f"Your {timer[1]} {timer[2]} timer is finished"
        elif before:
            due = now + timedelta(seconds=seconds(before[1], before[2]))
            title = before[3]
        elif after:
            due = now + timedelta(seconds=seconds(after[2], after[3]))
            title = after[1]
        elif dated:
            hour, minute = int(dated[2]), int(dated[3] or 0)
            if minute > 59 or hour > 23 or (dated[4] and not 1 <= hour <= 12):
                return "That time is invalid. Try tomorrow at 9 AM."
            if not dated[4] and not dated[3]:
                return "Please specify AM or PM, for example: remind me tomorrow at 9 AM to call Sam."
            if dated[4]:
                hour = hour % 12 + (12 if dated[4].lower() == "pm" else 0)
            due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if dated[1].lower() == "tomorrow":
                due += timedelta(days=1)
            if due <= now:
                return "That time has already passed. Please choose a future time."
            title = dated[5]
    except ValueError as error:
        return str(error)
    if due:
        title = title.strip()
        def schedule(db):
            ident = db.execute("INSERT INTO reminders(content,due_at) VALUES (?,?)", (title, due.timestamp())).lastrowid
            return (f"Saved reminder {ident} for {due.strftime('%d %b at %I:%M:%S %p')} ({ZONE.key}): {title}. "
                    "Keep YouAI open for the alert; overdue reminders appear when you return.")
        return store.perform(key, prompt, schedule)
    if re.match(r"(?:remind me\b|(?:set|start)(?: a)? (?:timer|reminder)\b|cancel (?:reminder|timer)\b)", clean, re.I):
        return "Please give an exact time: 'remind me in 10 minutes to drink water', 'remind me tomorrow at 9 AM to call Sam', or 'set a timer for 5 minutes'."
    return None
