import re

SEPARATOR = "-----------------------------------------------"
START_RE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2}) (\d{1,2}):(\d{2})(am|pm)\s*$", re.IGNORECASE)
DURATION_VALUES = {"short", "normal", "long"}
