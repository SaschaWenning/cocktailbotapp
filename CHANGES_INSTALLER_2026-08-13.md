# Installer-Fixes 2026-08-13

- GoodTFT `LCD7C-show` darf den Raspberry nicht dauerhaft auf Legacy-`fbdev` umstellen.
- `vc4-kms-v3d` wird nach der LCD-Treiberinstallation automatisch reaktiviert.
- Legacy-HDMI-/Framebuffer-Modi werden entfernt.
- `/boot/firmware/cmdline.txt` (bzw. `/boot/cmdline.txt`) erhält `video=HDMI-A-1:1024x600M@60`.
- Frühere Maskierungen von `dev-dri-card0.device` und `dev-dri-renderD128.device` werden aufgehoben.
- Flutter-Webdateien werden auf Verzeichnisse `0755` / Dateien `0644` normalisiert, damit der lokale Flask-Dienst `index.html` lesen kann.
- Der CocktailBot-systemd-Dienst verwendet `WorkingDirectory=/var/lib/cocktailbot` und `GPIOZERO_PIN_FACTORY=lgpio`.
- PayPal bleibt vollständig mitinstalliert, Zugangsdaten werden weiterhin erst optional später über `sudo cocktailbot-paypal-config` eingetragen.
