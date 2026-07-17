#!/usr/bin/env bash
# Install a scheduled "did you forget to log a day?" reminder for work-buddy.
#
# It runs `wb.py notify` on a schedule. The notify command is SILENT unless
# there are actually unresolved past workdays — so this is a smart nudge, not
# a daily nag.
#
# macOS: installs a launchd LaunchAgent (survives logout/login, fires on a
#        weekday schedule). Linux/other: prints a crontab line to add yourself.
#
# Usage:
#   ./install-reminders.sh [--time HH:MM] [--channel stdout|macos|slack|auto]
#                          [--days 1-5] [--uninstall]
#
# Defaults: --time 17:30  --channel macos  --days 1-5 (Mon-Fri)
#
# For Slack delivery, add an incoming-webhook URL to config.json first:
#   "slack_webhook": "https://hooks.slack.com/services/XXX/YYY/ZZZ"
# then pass --channel slack (or auto, which does macOS + Slack).

set -euo pipefail

TIME="17:30"
CHANNEL="macos"
DAYS="1-5"
UNINSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --time)      TIME="$2"; shift 2 ;;
    --channel)   CHANNEL="$2"; shift 2 ;;
    --days)      DAYS="$2"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

HOUR="${TIME%%:*}"
MINUTE="${TIME##*:}"
WB="$HOME/.claude/skills/work-buddy/helpers/wb.py"
CONFIG="$HOME/.claude/skills/work-buddy/config.json"
LABEL="com.workbuddy.reminder"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

uninstall_macos() {
  if [[ -f "$PLIST" ]]; then
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "✓ Removed reminder LaunchAgent ($PLIST)"
  else
    echo "No reminder LaunchAgent installed."
  fi
}

if [[ "$UNINSTALL" == "1" ]]; then
  case "$(uname -s)" in
    Darwin) uninstall_macos ;;
    *) echo "On non-macOS, remove the work-buddy crontab line manually (crontab -e)." ;;
  esac
  exit 0
fi

if [[ ! -f "$WB" ]]; then
  echo "wb.py not found at $WB — run ./install.sh first." >&2
  exit 1
fi

case "$(uname -s)" in
  Darwin)
    # launchd StartCalendarInterval: one <dict> per weekday so we can schedule
    # Mon-Fri (Weekday: Sun=0..Sat=6; Mon=1..Fri=5).
    IFS='-' read -r DAY_START DAY_END <<< "$DAYS"
    DAY_START="${DAY_START:-1}"; DAY_END="${DAY_END:-5}"

    INTERVALS=""
    for wd in $(seq "$DAY_START" "$DAY_END"); do
      INTERVALS+="    <dict>
      <key>Weekday</key><integer>$wd</integer>
      <key>Hour</key><integer>$((10#$HOUR))</integer>
      <key>Minute</key><integer>$((10#$MINUTE))</integer>
    </dict>
"
    done

    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>$WB</string>
    <string>--config</string>
    <string>$CONFIG</string>
    <string>notify</string>
    <string>--channel</string>
    <string>$CHANNEL</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
$INTERVALS  </array>
  <key>StandardErrorPath</key><string>$HOME/.claude/skills/work-buddy/reminder.log</string>
  <key>StandardOutPath</key><string>$HOME/.claude/skills/work-buddy/reminder.log</string>
</dict>
</plist>
PLIST_EOF

    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    echo "✓ Installed work-buddy reminder"
    echo "  Schedule: ${TIME} on weekdays ${DAY_START}-${DAY_END}, channel=${CHANNEL}"
    echo "  Plist:    $PLIST"
    echo "  Log:      ~/.claude/skills/work-buddy/reminder.log"
    echo
    echo "Test it now (fires even if nothing is outstanding):"
    echo "  python3 $WB --config $CONFIG notify --channel $CHANNEL --force"
    echo
    echo "Uninstall: ./install-reminders.sh --uninstall"
    ;;
  *)
    # Linux / other: emit a crontab line. cron day-of-week: 0-7 (Sun=0/7).
    echo "Non-macOS detected. Add this line to your crontab (crontab -e):"
    echo
    echo "  $MINUTE $HOUR * * $DAYS /usr/bin/python3 $WB --config $CONFIG notify --channel $CHANNEL"
    echo
    echo "(notify is silent unless you have unresolved workdays.)"
    ;;
esac
