# === Pico 2 LED Controller für Cocktailmaschine ===
# Unterstützt: COLOR, OFF, BUSY, READY, ERROR, RAINBOW, PULSE, BLINK
# 240 WS2812B LEDs über GPIO0

import machine
import neopixel
import time
import select
import sys

# === Konfiguration ===
LED_PIN = 0
NUM_LEDS = 240
BRIGHTNESS = 0.5  # 0.0 bis 1.0

# LED Strip initialisieren
np = neopixel.NeoPixel(machine.Pin(LED_PIN), NUM_LEDS)

# Globale Variablen
current_mode = "OFF"
current_color = (0, 0, 0)
running = True

def apply_brightness(color):
    """Wendet globale Helligkeit auf eine Farbe an"""
    return tuple(int(c * BRIGHTNESS) for c in color)

def set_all(color):
    """Setzt alle LEDs auf eine Farbe"""
    adjusted = apply_brightness(color)
    np.fill(adjusted)
    np.write()

def rainbow_cycle(wait=10):
    """Regenbogen-Animation"""
    for j in range(256):
        if current_mode != "RAINBOW":
            break
        for i in range(NUM_LEDS):
            pixel_index = (i * 256 // NUM_LEDS) + j
            np[i] = wheel(pixel_index & 255)
        np.write()
        time.sleep_ms(wait)

def wheel(pos):
    """Erzeugt Regenbogenfarben (0-255)"""
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

def pulse_effect(color):
    """Pulsiert zwischen dunkel und hell"""
    # Aufwärts von 0% bis 100%
    for i in range(51):
        if current_mode != "PULSE":
            return
        factor = i / 50.0
        pulsed = tuple(int(c * factor * BRIGHTNESS) for c in color)
        np.fill(pulsed)
        np.write()
        time.sleep_ms(20)
    
    # Abwärts von 100% bis 0%
    for i in range(50, -1, -1):
        if current_mode != "PULSE":
            return
        factor = i / 50.0
        pulsed = tuple(int(c * factor * BRIGHTNESS) for c in color)
        np.fill(pulsed)
        np.write()
        time.sleep_ms(20)

def blink_effect(color, speed=300):
    """Blinkt mit angegebener Geschwindigkeit"""
    # An
    set_all(color)
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < speed:
        if current_mode != "BLINK":
            return
        time.sleep_ms(10)
    
    # Aus
    np.fill((0, 0, 0))
    np.write()
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < speed:
        if current_mode != "BLINK":
            return
        time.sleep_ms(10)

def handle_command(cmd):
    """Verarbeitet empfangene Befehle"""
    global current_mode, current_color, BRIGHTNESS
    
    parts = cmd.strip().split()
    if not parts:
        return
    
    action = parts[0].upper()
    
    if action == "COLOR" and len(parts) >= 4:
        current_mode = "COLOR"
        current_color = (int(parts[1]), int(parts[2]), int(parts[3]))
        set_all(current_color)
        print(f"OK: COLOR {current_color}")
        
    elif action == "OFF":
        current_mode = "OFF"
        np.fill((0, 0, 0))
        np.write()
        print("OK: OFF")
        
    elif action == "READY":
        current_mode = "COLOR"
        current_color = (0, 255, 0)
        set_all(current_color)
        print("OK: READY")
        
    elif action == "BUSY":
        current_mode = "BUSY"
        current_color = (255, 255, 0)
        print("OK: BUSY")
        
    elif action == "ERROR":
        current_mode = "ERROR"
        current_color = (255, 0, 0)
        print("OK: ERROR")
        
    elif action == "RAINBOW":
        current_mode = "RAINBOW"
        print("OK: RAINBOW")
        
    elif action == "PULSE" and len(parts) >= 4:
        current_mode = "PULSE"
        current_color = (int(parts[1]), int(parts[2]), int(parts[3]))
        print(f"OK: PULSE {current_color}")
        
    elif action == "BLINK" and len(parts) >= 4:
        current_mode = "BLINK"
        current_color = (int(parts[1]), int(parts[2]), int(parts[3]))
        print(f"OK: BLINK {current_color}")
        
    elif action == "BRIGHT" and len(parts) >= 2:
        val = max(0, min(255, int(parts[1])))
        BRIGHTNESS = val / 255.0
        print(f"OK: BRIGHTNESS {BRIGHTNESS}")
        
    else:
        print(f"ERROR: Unknown command '{cmd}'")

# === Hauptloop ===
print("Pico LED Controller ready")
print("Supported: COLOR, OFF, READY, BUSY, ERROR, RAINBOW, PULSE, BLINK, BRIGHT")

# USB Serial Setup
poll = select.poll()
poll.register(sys.stdin, select.POLLIN)

while running:
    try:
        # Führe aktuellen Effekt aus
        if current_mode == "RAINBOW":
            # Prüfe auf neue Befehle während Rainbow
            events = poll.poll(0)
            if events:
                line = sys.stdin.readline()
                if line:
                    handle_command(line.strip())
            else:
                rainbow_cycle(10)
                
        elif current_mode == "PULSE":
            # Prüfe auf neue Befehle vor jedem Puls
            events = poll.poll(0)
            if events:
                line = sys.stdin.readline()
                if line:
                    handle_command(line.strip())
            else:
                pulse_effect(current_color)
                
        elif current_mode == "BLINK":
            # Prüfe auf neue Befehle vor jedem Blink
            events = poll.poll(0)
            if events:
                line = sys.stdin.readline()
                if line:
                    handle_command(line.strip())
            else:
                blink_effect(current_color, 300)
                
        elif current_mode == "BUSY":
            # BUSY = Gelb blinkend
            events = poll.poll(0)
            if events:
                line = sys.stdin.readline()
                if line:
                    handle_command(line.strip())
            else:
                blink_effect(current_color, 300)
                
        elif current_mode == "ERROR":
            # ERROR = Rot blinkend
            events = poll.poll(0)
            if events:
                line = sys.stdin.readline()
                if line:
                    handle_command(line.strip())
            else:
                blink_effect(current_color, 300)
                
        else:
            # OFF oder COLOR: Warte auf Befehle
            events = poll.poll(100)
            if events:
                line = sys.stdin.readline()
                if line:
                    handle_command(line.strip())
                    
    except KeyboardInterrupt:
        np.fill((0, 0, 0))
        np.write()
        running = False
        print("Shutdown")
        
    except Exception as e:
        print(f"ERROR: {e}")
        time.sleep(1)
