#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${COCKTAILBOT_REPO_URL:-https://github.com/saschawenning/cocktailbotapp.git}"
REPO_BRANCH="${COCKTAILBOT_REPO_BRANCH:-main}"
INSTALL_ROOT="${COCKTAILBOT_INSTALL_ROOT:-/opt/cocktailbot}"
SOURCE_DIR="$INSTALL_ROOT/source"
WEB_DIR="$INSTALL_ROOT/web"
RUNTIME_DIR="$INSTALL_ROOT/raspberry"
VENV_DIR="$INSTALL_ROOT/venv"
FLUTTER_DIR="${COCKTAILBOT_FLUTTER_DIR:-/opt/flutter}"
ACTIVE_HIGH="${COCKTAILBOT_ACTIVE_HIGH:-0}"
KIOSK_DELAY="${COCKTAILBOT_KIOSK_DELAY_SECONDS:-30}"
BUILD_MODE="${COCKTAILBOT_BUILD_MODE:-auto}"
SKIP_APT="${COCKTAILBOT_SKIP_APT:-0}"
REBOOT_AFTER=0
USE_LOCAL_SOURCE=0
INSTALL_LCD="${COCKTAILBOT_INSTALL_LCD:-1}"
BOOT_OPTIMIZE="${COCKTAILBOT_BOOT_OPTIMIZE:-1}"
PICO_PORT="${COCKTAILBOT_PICO_PORT:-auto}"
PICO_BAUD="${COCKTAILBOT_PICO_BAUD:-115200}"
LCD_REPO_URL="${COCKTAILBOT_LCD_REPO_URL:-https://github.com/goodtft/LCD-show.git}"

usage() {
  cat <<USAGE
CocktailBot Installer

Verwendung:
  sudo ./install.sh [Optionen]

Optionen:
  --reboot                  Raspberry Pi nach der Installation neu starten
  --local-source            den aktuellen Repository-Ordner statt GitHub verwenden
  --active-high 0|1         Relaislogik; Standard: 0 (LOW = EIN, HIGH = AUS)
  --kiosk-delay SEKUNDEN    Wartezeit bis Chromium startet; Standard: 30
  --build-mode auto|release|source
                            auto: web-release bevorzugen, sonst lokal bauen
                            release: nur GitHub-Branch web-release verwenden
                            source: Flutter-App auf dem Raspberry bauen
  --user BENUTZER           Desktop-/Kioskbenutzer festlegen
  --repo URL                GitHub-Repository ändern
  --branch NAME             Git-Branch ändern; Standard: main
  --skip-lcd                GoodTFT LCD7C-Treiber nicht installieren
  --skip-boot-opt           Plymouth/cmdline/Display-Bootoptimierung überspringen
  --pico-port PORT          Pico-USB-Port; Standard: auto
  -h, --help                Hilfe anzeigen
USAGE
}

TARGET_USER="${COCKTAILBOT_USER:-${SUDO_USER:-}}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reboot) REBOOT_AFTER=1; shift ;;
    --local-source) USE_LOCAL_SOURCE=1; shift ;;
    --active-high) ACTIVE_HIGH="${2:?Wert fehlt}"; shift 2 ;;
    --kiosk-delay) KIOSK_DELAY="${2:?Wert fehlt}"; shift 2 ;;
    --build-mode) BUILD_MODE="${2:?Wert fehlt}"; shift 2 ;;
    --user) TARGET_USER="${2:?Benutzer fehlt}"; shift 2 ;;
    --repo) REPO_URL="${2:?URL fehlt}"; shift 2 ;;
    --branch) REPO_BRANCH="${2:?Branch fehlt}"; shift 2 ;;
    --skip-lcd) INSTALL_LCD=0; shift ;;
    --skip-boot-opt) BOOT_OPTIMIZE=0; shift ;;
    --pico-port) PICO_PORT="${2:?Port fehlt}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unbekannte Option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

log() { printf '\n\033[1;36m[CocktailBot]\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m[CocktailBot WARNUNG]\033[0m %s\n' "$*" >&2; }
die() { printf '\n\033[1;31m[CocktailBot FEHLER]\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Bitte mit sudo ausführen."
[[ "$ACTIVE_HIGH" =~ ^[01]$ ]] || die "--active-high muss 0 oder 1 sein."
[[ "$KIOSK_DELAY" =~ ^[0-9]+$ ]] || die "--kiosk-delay muss eine ganze Zahl sein."
(( KIOSK_DELAY <= 3600 )) || die "Die Kiosk-Verzögerung darf höchstens 3600 Sekunden betragen."
[[ "$BUILD_MODE" =~ ^(auto|release|source)$ ]] || die "--build-mode muss auto, release oder source sein."
[[ "$INSTALL_LCD" =~ ^[01]$ ]] || die "COCKTAILBOT_INSTALL_LCD muss 0 oder 1 sein."
[[ "$BOOT_OPTIMIZE" =~ ^[01]$ ]] || die "COCKTAILBOT_BOOT_OPTIMIZE muss 0 oder 1 sein."
[[ "$PICO_BAUD" =~ ^[0-9]+$ ]] || die "COCKTAILBOT_PICO_BAUD muss eine ganze Zahl sein."

if [[ -z "$TARGET_USER" || "$TARGET_USER" == "root" ]]; then
  TARGET_USER="$(getent passwd | awk -F: '$3 >= 1000 && $3 < 60000 && $6 ~ /^\/home\// {print $1; exit}')"
fi
[[ -n "$TARGET_USER" ]] || die "Kein Desktopbenutzer gefunden. Nutze --user BENUTZER."
id "$TARGET_USER" >/dev/null 2>&1 || die "Benutzer '$TARGET_USER' existiert nicht."
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
TARGET_GROUP="$(id -gn "$TARGET_USER")"
[[ -d "$TARGET_HOME" ]] || die "Home-Verzeichnis fehlt: $TARGET_HOME"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

run_as_user() {
  runuser -u "$TARGET_USER" -- env \
    HOME="$TARGET_HOME" \
    USER="$TARGET_USER" \
    LOGNAME="$TARGET_USER" \
    PUB_CACHE="$TARGET_HOME/.pub-cache" \
    PATH="$FLUTTER_DIR/bin:/usr/local/bin:/usr/bin:/bin" \
    "$@"
}

install_packages() {
  [[ "$SKIP_APT" == "1" ]] && return 0
  log "Installiere Systempakete"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y \
    ca-certificates curl git rsync unzip xz-utils zip libglu1-mesa \
    python3 python3-venv python3-pip python3-gpiozero python3-serial python3-cryptography \
    x11-xserver-utils unclutter util-linux onboard dbus-x11 dconf-cli

  if apt-cache show python3-lgpio >/dev/null 2>&1; then
    apt-get install -y python3-lgpio
  fi

  if apt-cache show chromium >/dev/null 2>&1; then
    apt-get install -y chromium
  elif apt-cache show chromium-browser >/dev/null 2>&1; then
    apt-get install -y chromium-browser
  else
    die "Weder chromium noch chromium-browser ist in den Paketquellen verfügbar."
  fi
}

sync_source() {
  log "Hole Repository $REPO_URL ($REPO_BRANCH)"
  install -d -m 0755 "$INSTALL_ROOT"

  if [[ "$USE_LOCAL_SOURCE" == "1" ]]; then
    [[ -f "$SCRIPT_DIR/app/pubspec.yaml" ]] || die "Im aktuellen Ordner fehlt app/pubspec.yaml."
    rm -rf "$SOURCE_DIR"
    install -d -m 0755 "$SOURCE_DIR"
    rsync -a --delete \
      --exclude '.dart_tool' --exclude 'build' --exclude '__pycache__' \
      "$SCRIPT_DIR/" "$SOURCE_DIR/"
  elif [[ -d "$SOURCE_DIR/.git" ]]; then
    git -C "$SOURCE_DIR" remote set-url origin "$REPO_URL"
    git -C "$SOURCE_DIR" fetch --depth 1 origin "$REPO_BRANCH"
    git -C "$SOURCE_DIR" checkout -B "$REPO_BRANCH" "origin/$REPO_BRANCH"
    git -C "$SOURCE_DIR" reset --hard "origin/$REPO_BRANCH"
    git -C "$SOURCE_DIR" clean -fdx
  else
    rm -rf "$SOURCE_DIR"
    git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$SOURCE_DIR"
  fi

  [[ -f "$SOURCE_DIR/app/pubspec.yaml" ]] || die "Repository enthält kein app/pubspec.yaml."
}

install_prebuilt_web() {
  local temp_release
  temp_release="$(mktemp -d)"
  if git clone --quiet --depth 1 --branch web-release "$REPO_URL" "$temp_release" 2>/dev/null \
      && [[ -f "$temp_release/index.html" ]]; then
    log "Installiere vorgebautes Flutter-Web-Release aus Branch web-release"
    rm -rf "$WEB_DIR"
    install -d -m 0755 "$WEB_DIR"
    rsync -a --delete --exclude '.git' "$temp_release/" "$WEB_DIR/"
    rm -rf "$temp_release"
    return 0
  fi
  rm -rf "$temp_release"
  return 1
}

install_flutter() {
  log "Installiere bzw. aktualisiere Flutter Stable unter $FLUTTER_DIR"
  install -d -o "$TARGET_USER" -g "$TARGET_GROUP" -m 0755 "$TARGET_HOME/.pub-cache"
  if [[ -d "$FLUTTER_DIR/.git" ]]; then
    run_as_user git -C "$FLUTTER_DIR" fetch --depth 1 origin stable
    run_as_user git -C "$FLUTTER_DIR" checkout -B stable origin/stable
    run_as_user git -C "$FLUTTER_DIR" reset --hard origin/stable
  else
    rm -rf "$FLUTTER_DIR"
    git clone --depth 1 --branch stable https://github.com/flutter/flutter.git "$FLUTTER_DIR"
    chown -R "$TARGET_USER:$TARGET_GROUP" "$FLUTTER_DIR"
  fi
}

build_web() {
  install_flutter
  log "Baue Flutter-Web-App auf dem Raspberry Pi"
  chown -R "$TARGET_USER:$TARGET_GROUP" "$SOURCE_DIR/app"
  run_as_user "$FLUTTER_DIR/bin/flutter" config --no-analytics --enable-web
  run_as_user "$FLUTTER_DIR/bin/flutter" precache --web
  if [[ ! -f "$SOURCE_DIR/app/web/index.html" ]]; then
    run_as_user bash -lc "cd '$SOURCE_DIR/app' && '$FLUTTER_DIR/bin/flutter' create . --platforms web"
  fi
  run_as_user bash -lc "cd '$SOURCE_DIR/app' && '$FLUTTER_DIR/bin/flutter' pub get"
  run_as_user bash -lc "cd '$SOURCE_DIR/app' && '$FLUTTER_DIR/bin/flutter' build web --release"
  [[ -f "$SOURCE_DIR/app/build/web/index.html" ]] || die "Flutter-Build wurde nicht erzeugt."
  rm -rf "$WEB_DIR"
  install -d -m 0755 "$WEB_DIR"
  rsync -a --delete "$SOURCE_DIR/app/build/web/" "$WEB_DIR/"
}

fix_web_permissions() {
  log "Setze sichere Leserechte für den Flutter-Web-Build"
  [[ -d "$WEB_DIR" ]] || die "Web-Verzeichnis fehlt: $WEB_DIR"
  chmod 0755 "$INSTALL_ROOT" "$WEB_DIR"
  find "$WEB_DIR" -type d -exec chmod 0755 {} +
  find "$WEB_DIR" -type f -exec chmod 0644 {} +
  chown -R root:root "$WEB_DIR"
  [[ -r "$WEB_DIR/index.html" ]] || die "index.html ist für den Webdienst nicht lesbar."
}

install_runtime() {
  log "Installiere GPIO-/Webdienst"
  install -d -m 0755 "$RUNTIME_DIR"
  getent group gpio >/dev/null 2>&1 || groupadd --system gpio
  getent group dialout >/dev/null 2>&1 || groupadd --system dialout
  usermod -aG dialout "$TARGET_USER" || true
  install -m 0755 "$SOURCE_DIR/raspberry/cocktailbot_server.py" "$RUNTIME_DIR/cocktailbot_server.py"
  install -m 0755 "$SOURCE_DIR/raspberry/start-kiosk.sh" "$RUNTIME_DIR/start-kiosk.sh"
  install -m 0755 "$SOURCE_DIR/raspberry/start-onboard.sh" "$RUNTIME_DIR/start-onboard.sh"
  install -m 0644 "$SOURCE_DIR/raspberry/requirements.txt" "$RUNTIME_DIR/requirements.txt"
  [[ -f "$SOURCE_DIR/raspberry/license_public_key.pem" ]] || die "Lizenz-Public-Key fehlt im Repository."

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    rm -rf "$VENV_DIR"
    python3 -m venv --system-site-packages "$VENV_DIR"
  fi
  "$VENV_DIR/bin/pip" install --disable-pip-version-check -r "$RUNTIME_DIR/requirements.txt"

  install -d -m 0755 /etc/cocktailbot
  install -o root -g root -m 0644 \
    "$SOURCE_DIR/raspberry/license_public_key.pem" \
    /etc/cocktailbot/license_public_key.pem
  cat > /etc/cocktailbot/cocktailbot.env <<ENV
COCKTAILBOT_ACTIVE_HIGH=$ACTIVE_HIGH
COCKTAILBOT_STATE_FILE=/var/lib/cocktailbot/machine_state.json
COCKTAILBOT_PICO_PORT=$PICO_PORT
COCKTAILBOT_PICO_BAUD=$PICO_BAUD
COCKTAILBOT_LICENSE_FILE=/var/lib/cocktailbot/license.json
COCKTAILBOT_LICENSE_PUBLIC_KEY=/etc/cocktailbot/license_public_key.pem
ENV
  chmod 0644 /etc/cocktailbot/cocktailbot.env

  cat > /etc/cocktailbot/kiosk.env <<ENV
COCKTAILBOT_KIOSK_URL=http://127.0.0.1:8080
COCKTAILBOT_KIOSK_DELAY_SECONDS=$KIOSK_DELAY
COCKTAILBOT_CHROMIUM_PROFILE=$TARGET_HOME/.config/cocktailbot-chromium
COCKTAILBOT_KIOSK_STOP_FILE=/var/lib/cocktailbot/kiosk.stop
ENV
  chmod 0644 /etc/cocktailbot/kiosk.env

  sed \
    -e "s/__USER__/$TARGET_USER/g" \
    -e "s/__GROUP__/$TARGET_GROUP/g" \
    "$SOURCE_DIR/raspberry/systemd/cocktailbot.service.in" \
    > /etc/systemd/system/cocktailbot.service
  chmod 0644 /etc/systemd/system/cocktailbot.service

  chown root:root /etc/systemd/system/cocktailbot.service "$RUNTIME_DIR/cocktailbot_server.py"
  chown "$TARGET_USER:$TARGET_GROUP" "$RUNTIME_DIR/start-kiosk.sh"
  chmod 0755 "$RUNTIME_DIR/start-kiosk.sh"
}

install_lcd_driver() {
  [[ "$INSTALL_LCD" == "1" ]] || { log "LCD-Installation übersprungen"; return 0; }

  log "Installiere GoodTFT LCD7C-Treiber für 7-Zoll 1024x600"
  local lcd_dir="$TARGET_HOME/LCD-show"
  rm -rf "$lcd_dir"
  run_as_user git clone --depth 1 "$LCD_REPO_URL" "$lcd_dir"

  [[ -f "$lcd_dir/LCD7C-show" ]] || die "LCD7C-show wurde im GoodTFT-Repository nicht gefunden."
  chmod +x "$lcd_dir/LCD7C-show"

  # Das Originalskript rebootet am Ende. Der zentrale Installer entscheidet
  # selbst, ob und wann neu gestartet wird.
  sed -i -E \
    's/^[[:space:]]*(sudo[[:space:]]+)?reboot([[:space:]]*)$/# reboot durch CocktailBot-Installer unterdrueckt/' \
    "$lcd_dir/LCD7C-show"

  (
    cd "$lcd_dir"
    ./LCD7C-show
  )
  chown -R "$TARGET_USER:$TARGET_GROUP" "$lcd_dir" || true
  log "LCD7C-Treiber installiert"
}

configure_display_and_boot() {
  [[ "$BOOT_OPTIMIZE" == "1" ]] || { log "Bootoptimierung übersprungen"; return 0; }

  local cmdline_file=""
  local config_file=""
  if [[ -f /boot/firmware/cmdline.txt ]]; then
    cmdline_file=/boot/firmware/cmdline.txt
  elif [[ -f /boot/cmdline.txt ]]; then
    cmdline_file=/boot/cmdline.txt
  fi
  if [[ -f /boot/firmware/config.txt ]]; then
    config_file=/boot/firmware/config.txt
  elif [[ -f /boot/config.txt ]]; then
    config_file=/boot/config.txt
  fi

  if [[ -n "$config_file" ]]; then
    log "Aktiviere KMS und entferne alte 1920x1080-/Framebuffer-Zwangseinstellungen"
    cp -a "$config_file" "${config_file}.cocktailbot.bak" || true
    sed -i -E \
      -e '/^[[:space:]]*#?[[:space:]]*dtoverlay=vc4-fkms-v3d/d' \
      -e '/^[[:space:]]*#?[[:space:]]*dtoverlay=vc4-kms-v3d/d' \
      -e '/^[[:space:]]*hdmi_force_hotplug=/d' \
      -e '/^[[:space:]]*hdmi_group=/d' \
      -e '/^[[:space:]]*hdmi_mode=/d' \
      -e '/^[[:space:]]*hdmi_cvt([=[:space:]])/d' \
      -e '/^[[:space:]]*framebuffer_width=/d' \
      -e '/^[[:space:]]*framebuffer_height=/d' \
      -e '/^[[:space:]]*disable_fw_kms_setup=/d' \
      "$config_file"
    printf '\n# CocktailBot Display\ndtoverlay=vc4-kms-v3d\n' >> "$config_file"
  else
    warn "Keine config.txt unter /boot/firmware oder /boot gefunden."
  fi

  if [[ -n "$cmdline_file" ]]; then
    log "Setze KMS-Ausgabe auf 1024x600@60"
    cp -a "$cmdline_file" "${cmdline_file}.cocktailbot.bak" || true
    sed -i -E \
      -e 's/(^|[[:space:]])quiet([[:space:]]|$)/ /g' \
      -e 's/(^|[[:space:]])splash([[:space:]]|$)/ /g' \
      -e 's/(^|[[:space:]])video=[^[:space:]]+([[:space:]]|$)/ /g' \
      -e 's/[[:space:]]+/ /g' \
      -e 's/^ //' \
      -e 's/ $//' \
      "$cmdline_file"
    sed -i 's/$/ video=HDMI-A-1:1024x600M@60/' "$cmdline_file"
  else
    warn "Keine cmdline.txt unter /boot/firmware oder /boot gefunden."
  fi

  systemctl unmask dev-dri-card0.device >/dev/null 2>&1 || true
  systemctl unmask dev-dri-renderD128.device >/dev/null 2>&1 || true
  systemctl disable NetworkManager-wait-online.service >/dev/null 2>&1 || true

  log "Erzwinge grafischen Desktopstart und Autologin"
  systemctl set-default graphical.target >/dev/null 2>&1 || true
  if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_boot_behaviour B4 || warn "Desktop-Autologin konnte nicht gesetzt werden."
    raspi-config nonint do_blanking 1 || warn "Bildschirmabschaltung konnte nicht deaktiviert werden."
  fi
}

configure_pump_boot_safety() {
  # CocktailBot uses these BCM GPIOs exclusively for pumps.  The installed
  # relay boards are LOW-active by default, so HIGH is the safe/off level.
  # Keep this separate from display boot optimisation: pump safety must also
  # be applied during updates that use --skip-boot-opt.
  local config_file=""
  local cmdline_file=""
  local safe_drive="dh"
  local pins="17,18,27,22,23,24,25,4,5,6,13,19,26,16,20,21,12,15"

  if [[ "$ACTIVE_HIGH" == "1" ]]; then
    # HIGH-active relays are off at LOW.
    safe_drive="dl"
  fi

  if [[ -f /boot/firmware/config.txt ]]; then
    config_file=/boot/firmware/config.txt
  elif [[ -f /boot/config.txt ]]; then
    config_file=/boot/config.txt
  fi
  if [[ -f /boot/firmware/cmdline.txt ]]; then
    cmdline_file=/boot/firmware/cmdline.txt
  elif [[ -f /boot/cmdline.txt ]]; then
    cmdline_file=/boot/cmdline.txt
  fi

  if [[ -n "$config_file" ]]; then
    log "Setze alle Pumpen-GPIOs bereits im Bootloader auf AUS"
    cp -a "$config_file" "${config_file}.cocktailbot-pumps.bak" || true

    # Remove an older CocktailBot safety block and legacy exact pump line so
    # reinstallations stay idempotent. The block is appended at the end,
    # because gpio= directives are applied in order and the last one wins.
    sed -i \
      '/^# BEGIN COCKTAILBOT PUMP SAFETY$/,/^# END COCKTAILBOT PUMP SAFETY$/d' \
      "$config_file"
    sed -i -E \
      "/^[[:space:]]*gpio=${pins//,/\\,}=op,d[hl][[:space:]]*$/d; \
       /^[[:space:]]*enable_uart=/d" \
      "$config_file"

    cat >> "$config_file" <<EOF

# BEGIN COCKTAILBOT PUMP SAFETY
# These BCM pins drive the 18 pump relays. Keep them at the relay OFF level
# from the earliest firmware/boot stage. GPIO15 is reserved for pump 18, so
# the on-board UART is disabled; the Pico LED controller uses USB serial.
[all]
enable_uart=0
gpio=$pins=op,$safe_drive
# END COCKTAILBOT PUMP SAFETY
EOF
  else
    warn "Keine config.txt gefunden; Pumpen-GPIOs konnten nicht frueh auf AUS gesetzt werden."
  fi

  if [[ -n "$cmdline_file" ]]; then
    # GPIO15 is pump 18. A serial console would claim GPIO14/15 again when
    # Linux starts, so remove only UART console entries (keep console=tty1).
    cp -a "$cmdline_file" "${cmdline_file}.cocktailbot-pumps.bak" || true
    sed -i -E \
      's/(^|[[:space:]])console=(serial0|ttyAMA[0-9]*|ttyS[0-9]*),[^[:space:]]+([[:space:]]|$)/ /g; \
       s/[[:space:]]+/ /g; s/^ //; s/ $//' \
      "$cmdline_file"
  fi

  # Do not allow a previously enabled serial getty to reclaim pump GPIO15.
  systemctl disable --now serial-getty@serial0.service >/dev/null 2>&1 || true
  systemctl disable --now serial-getty@ttyAMA0.service >/dev/null 2>&1 || true
  systemctl disable --now serial-getty@ttyS0.service >/dev/null 2>&1 || true
}

configure_kiosk() {
  log "Konfiguriere Desktop-Autostart und Kioskstart nach ${KIOSK_DELAY} Sekunden"
  install -d -o "$TARGET_USER" -g "$TARGET_GROUP" -m 0755 \
    "$TARGET_HOME/.config/autostart" "$TARGET_HOME/.config/labwc" "$TARGET_HOME/.local/state"

  install -o "$TARGET_USER" -g "$TARGET_GROUP" -m 0644 \
    "$SOURCE_DIR/raspberry/autostart/cocktailbot-kiosk.desktop" \
    "$TARGET_HOME/.config/autostart/cocktailbot-kiosk.desktop"

  # Die aktuelle Flutter-App besitzt eine eigene Touch-Tastatur als Popup.
  # Ein automatisch gestartetes Onboard würde darüber liegen und wird daher
  # für CocktailBot nicht mehr autogestartet. Das Skript bleibt als manuelle
  # Fallback-Option installiert.
  chown "$TARGET_USER:$TARGET_GROUP" "$RUNTIME_DIR/start-onboard.sh"
  chmod 0755 "$RUNTIME_DIR/start-onboard.sh"
  rm -f "$TARGET_HOME/.config/autostart/cocktailbot-onboard.desktop"
  pkill -u "$TARGET_USER" -x onboard >/dev/null 2>&1 || true

  install -d -o "$TARGET_USER" -g "$TARGET_GROUP" -m 0755 "$TARGET_HOME/Desktop"
  cat > "$TARGET_HOME/Desktop/CocktailBot starten.desktop" <<EOF_DESKTOP
[Desktop Entry]
Type=Application
Name=CocktailBot starten
Comment=CocktailBot Kiosk starten
Exec=$RUNTIME_DIR/start-kiosk.sh
Icon=applications-system
Terminal=false
EOF_DESKTOP
  chown "$TARGET_USER:$TARGET_GROUP" "$TARGET_HOME/Desktop/CocktailBot starten.desktop"
  chmod 0755 "$TARGET_HOME/Desktop/CocktailBot starten.desktop"

  local labwc_file="$TARGET_HOME/.config/labwc/autostart"
  touch "$labwc_file"
  sed -i '/# BEGIN COCKTAILBOT/,/# END COCKTAILBOT/d' "$labwc_file"
  cat >> "$labwc_file" <<LABWC

# BEGIN COCKTAILBOT
/opt/cocktailbot/raspberry/start-kiosk.sh >> $TARGET_HOME/.local/state/cocktailbot-kiosk.log 2>&1 &
# END COCKTAILBOT
LABWC
  chown "$TARGET_USER:$TARGET_GROUP" "$labwc_file"
  chmod 0644 "$labwc_file"

  if command -v raspi-config >/dev/null 2>&1; then
    # B4 = Desktop mit automatischer Anmeldung. 1 = Bildschirmabschaltung aus.
    raspi-config nonint do_boot_behaviour B4 || warn "Desktop-Autologin konnte nicht automatisch gesetzt werden."
    raspi-config nonint do_blanking 1 || warn "Bildschirmabschaltung konnte nicht automatisch deaktiviert werden."
  else
    warn "raspi-config fehlt; Desktop-Autologin und Bildschirmabschaltung bitte manuell prüfen."
  fi
  systemctl set-default graphical.target >/dev/null 2>&1 || true
}

start_services() {
  log "Aktiviere CocktailBot-Dienst"
  systemctl daemon-reload
  systemctl enable cocktailbot.service
  systemctl restart cocktailbot.service

  for _ in $(seq 1 30); do
    local api_status
    if api_status="$(curl -fsS --max-time 2 http://127.0.0.1:8080/api/status 2>/dev/null)"; then
      log "CocktailBot-API ist erreichbar"
      if grep -q '"picoConnected":true' <<<"$api_status"; then
        log "Pico-2-LED-Controller ist über USB-Serial verbunden"
      else
        warn "Pico-2-LED-Controller wurde noch nicht erkannt. Pumpensteuerung bleibt verfügbar; prüfe USB-Kabel und /dev/ttyACM*."
      fi
      return 0
    fi
    sleep 1
  done

  systemctl --no-pager --full status cocktailbot.service || true
  journalctl -u cocktailbot.service -n 80 --no-pager || true
  die "CocktailBot-Dienst ist nicht erreichbar."
}

install_packages
sync_source

if [[ "$BUILD_MODE" == "release" ]]; then
  install_prebuilt_web || die "Branch web-release fehlt. Warte auf die GitHub-Action oder nutze --build-mode source."
elif [[ "$BUILD_MODE" == "auto" ]]; then
  if ! install_prebuilt_web; then
    warn "Kein web-release vorhanden; die App wird jetzt auf dem Raspberry Pi gebaut."
    build_web
  fi
else
  build_web
fi

fix_web_permissions
install_runtime
install_lcd_driver
configure_display_and_boot
configure_pump_boot_safety
configure_kiosk
start_services

cat <<SUMMARY

============================================================
CocktailBot wurde installiert.

Repository:       $REPO_URL
Installationsort: $INSTALL_ROOT
Kioskbenutzer:    $TARGET_USER
Kioskstart:       nach $KIOSK_DELAY Sekunden
Web/API:          http://127.0.0.1:8080
Relaislogik:      COCKTAILBOT_ACTIVE_HIGH=$ACTIVE_HIGH
Pumpen-Bootschutz: aktiv (GPIOs frueh auf AUS)
LCD7C/GoodTFT:    $INSTALL_LCD
Bootoptimierung:  $BOOT_OPTIMIZE
Pico LED-Port:     $PICO_PORT
Pico Baudrate:     $PICO_BAUD
Displayziel:      1024x600

Status prüfen:
  systemctl status cocktailbot.service
  curl http://127.0.0.1:8080/api/status
  ls -l /dev/serial/by-id/ 2>/dev/null || true

Aktualisieren:
  sudo /opt/cocktailbot/source/tools/update.sh

WICHTIG: Vor dem Anschluss von Flüssigkeiten jede Pumpe kurz testen.
============================================================
SUMMARY

if [[ "$REBOOT_AFTER" == "1" ]]; then
  log "Starte Raspberry Pi neu"
  systemctl reboot
else
  echo "Zum Aktivieren des automatischen Kioskstarts jetzt neu starten:"
  echo "  sudo reboot"
fi
