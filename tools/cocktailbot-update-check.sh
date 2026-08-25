#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE="/opt/cocktailbot/source"

[[ $EUID -eq 0 ]] || {
  echo "Update-Check muss als root laufen." >&2
  exit 1
}

if [[ ! -d "$SOURCE/.git" ]]; then
  echo "FEHLER: Git-Repository fehlt: $SOURCE" >&2
  exit 1
fi

sanitize_version() {
  local value="${1:-}"
  value="${value//$'\r'/}"
  value="${value//$'\n'/}"
  if [[ "$value" =~ ^[0-9]+([.][0-9]+){1,3}([+-][0-9A-Za-z._-]+)?$ ]]; then
    printf '%s' "$value"
  else
    printf 'unbekannt'
  fi
}

current_version="unbekannt"
if [[ -f "$SOURCE/VERSION" ]]; then
  current_version="$(sanitize_version "$(head -n1 "$SOURCE/VERSION")")"
fi

current_sha="$(
  git -c safe.directory=/opt/cocktailbot/source \
    -C /opt/cocktailbot/source rev-parse HEAD 2>/dev/null || true
)"
[[ "$current_sha" =~ ^[0-9a-fA-F]{40}$ ]] || current_sha="unbekannt"

# Nur Remote-Information aktualisieren. Keine lokale Datei wird überschrieben.
git -c safe.directory=/opt/cocktailbot/source \
  -C /opt/cocktailbot/source fetch origin main

remote_sha="$(
  git -c safe.directory=/opt/cocktailbot/source \
    -C /opt/cocktailbot/source rev-parse origin/main 2>/dev/null || true
)"
[[ "$remote_sha" =~ ^[0-9a-fA-F]{40}$ ]] || {
  echo "FEHLER: origin/main konnte nach fetch nicht ermittelt werden." >&2
  exit 1
}

remote_version_raw="$(
  git -c safe.directory=/opt/cocktailbot/source \
    -C /opt/cocktailbot/source show origin/main:VERSION 2>/dev/null \
    | head -n1 || true
)"
remote_version="$(sanitize_version "$remote_version_raw")"

update_available="0"
same_version_new_build="0"

if [[ "$current_sha" != "$remote_sha" ]]; then
  update_available="1"
  if [[ "$current_version" == "$remote_version" && "$current_version" != "unbekannt" ]]; then
    same_version_new_build="1"
  fi
fi

printf 'current_version=%s\n' "$current_version"
printf 'remote_version=%s\n' "$remote_version"
printf 'current_sha=%s\n' "$current_sha"
printf 'remote_sha=%s\n' "$remote_sha"
printf 'update_available=%s\n' "$update_available"
printf 'same_version_new_build=%s\n' "$same_version_new_build"
