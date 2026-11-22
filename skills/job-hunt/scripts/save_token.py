"""SessionStart hook: copy the optional Apify token from the plugin settings into the plugin's data folder.
Bash commands don't receive plugin options, so the daily scripts read this file (mode 0600, outside the user's data)."""
import os
import sys

data = os.environ.get("CLAUDE_PLUGIN_DATA")
if data:
    path = os.path.join(data, "apify_token")
    tok = os.environ.get("CLAUDE_PLUGIN_OPTION_APIFY_TOKEN", "").strip()
    try:
        if tok:
            os.makedirs(data, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(tok)
        elif os.path.exists(path):
            os.remove(path)
    except OSError as e:
        sys.stderr.write("job-hunt: could not save the Apify token: %s\n" % e)
sys.exit(0)
