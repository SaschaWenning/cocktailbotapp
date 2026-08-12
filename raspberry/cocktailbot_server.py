#!/usr/bin/env python3
"""CocktailBot Raspberry Pi GPIO controller and Flutter-Web host.

The REST API exposes the local contract used by the Flutter app:
  GET  /api/status
  POST /api/command
  GET  /api/payment/status
  POST /api/payment/config
  POST /api/payment/create-order
  GET  /api/payment/order-status
  POST /api/payment/mark-used

GPIO numbering is BCM. All pumps are forced off at startup, on stop, and on exit.
"""

from __future__ import annotations

import argparse
import atexit
import glob
import json
import os
import signal
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import requests

from flask import Flask, jsonify, request, send_from_directory

try:
    import serial
except ImportError:  # LED controller is optional; pumps must remain usable
    serial = None  # type: ignore[assignment]

try:
    from gpiozero import Device, OutputDevice
    from gpiozero.pins.mock import MockFactory
except ImportError as exc:  # pragma: no cover - production dependency check
    raise SystemExit(
        "gpiozero fehlt. Installiere es mit: sudo apt install python3-gpiozero"
    ) from exc


PUMP_PINS: tuple[int, ...] = (
    17, 18, 27, 22, 23, 24, 25, 4, 5,
    6, 13, 19, 26, 16, 20, 21, 12, 15,
)
PUMP_COUNT = len(PUMP_PINS)
MAX_PUMP_DURATION_MS = 120_000
MAX_JOB_DURATION_MS = 600_000
DEFAULT_START_SPACING_MS = 100
MAX_START_SPACING_MS = 2_000

ACTIVE_HIGH = os.getenv("COCKTAILBOT_ACTIVE_HIGH", "1") not in {"0", "false", "False"}
MOCK_GPIO = os.getenv("COCKTAILBOT_GPIO_MOCK", "0") in {"1", "true", "True"}
STATE_FILE = Path(
    os.getenv("COCKTAILBOT_STATE_FILE", "/var/lib/cocktailbot/machine_state.json")
)
PICO_PORT = os.getenv("COCKTAILBOT_PICO_PORT", "auto").strip() or "auto"
PICO_BAUD = int(os.getenv("COCKTAILBOT_PICO_BAUD", "115200"))
PAYPAL_MODE = os.getenv("COCKTAILBOT_PAYPAL_MODE", "sandbox").strip().lower() or "sandbox"
PAYPAL_CLIENT_ID = os.getenv("COCKTAILBOT_PAYPAL_CLIENT_ID", "").strip()
PAYPAL_CLIENT_SECRET = os.getenv("COCKTAILBOT_PAYPAL_CLIENT_SECRET", "").strip()
PAYPAL_DB_FILE = Path(
    os.getenv("COCKTAILBOT_PAYMENT_DB", "/var/lib/cocktailbot/payments.db")
)
PAYPAL_BRAND_NAME = os.getenv("COCKTAILBOT_PAYPAL_BRAND_NAME", "CocktailBot").strip() or "CocktailBot"
PAYPAL_RETURN_URL = os.getenv("COCKTAILBOT_PAYPAL_RETURN_URL", "").strip()
PAYPAL_CANCEL_URL = os.getenv("COCKTAILBOT_PAYPAL_CANCEL_URL", "").strip()
PAYPAL_TIMEOUT_SECONDS = float(os.getenv("COCKTAILBOT_PAYPAL_TIMEOUT_SECONDS", "15"))

if MOCK_GPIO:
    Device.pin_factory = MockFactory()


@dataclass(frozen=True)
class PumpStep:
    pump: int
    start_offset_ms: int
    duration_ms: int


@dataclass(frozen=True)
class PumpJob:
    action: str
    mode: str
    steps: tuple[PumpStep, ...]
    total_duration_ms: int


class ValidationError(ValueError):
    pass


class PaymentError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat()


def parse_money(value: Any, field: str = "price", *, allow_zero: bool = False) -> int:
    try:
        amount = Decimal(str(value).replace(",", ".")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError(f"Ungültiger Geldbetrag: {field}") from exc
    minimum = Decimal("0.00") if allow_zero else Decimal("0.01")
    if amount < minimum or amount > Decimal("9999.00"):
        raise ValidationError(f"Ungültiger Geldbetrag: {field}")
    return int(amount * 100)


def cents_text(cents: int) -> str:
    return f"{Decimal(cents) / Decimal(100):.2f}"


class PaypalPaymentBackend:
    """Local PayPal Orders-v2 backend with SQLite one-time-use protection."""

    def __init__(self) -> None:
        if PAYPAL_MODE not in {"sandbox", "live"}:
            raise SystemExit("COCKTAILBOT_PAYPAL_MODE muss sandbox oder live sein")
        self.mode = PAYPAL_MODE
        self.client_id = PAYPAL_CLIENT_ID
        self.client_secret = PAYPAL_CLIENT_SECRET
        self.api_base = (
            "https://api-m.paypal.com"
            if self.mode == "live"
            else "https://api-m.sandbox.paypal.com"
        )
        default_return = (
            "https://www.paypal.com/" if self.mode == "live"
            else "https://www.sandbox.paypal.com/"
        )
        self.return_url = PAYPAL_RETURN_URL or default_return
        self.cancel_url = PAYPAL_CANCEL_URL or self.return_url
        self.brand_name = PAYPAL_BRAND_NAME[:127]
        self.timeout = max(3.0, min(60.0, PAYPAL_TIMEOUT_SECONDS))
        self.db_file = PAYPAL_DB_FILE
        self._token_lock = threading.RLock()
        self._access_token = ""
        self._access_token_until = 0.0
        self._init_db()

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _db(self) -> sqlite3.Connection:
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_file, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_db(self) -> None:
        with self._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS payment_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    machine_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    cocktail_cents INTEGER NOT NULL,
                    mocktail_cents INTEGER NOT NULL,
                    shot_cents INTEGER NOT NULL,
                    recipe_prices_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS payment_orders (
                    order_id TEXT PRIMARY KEY,
                    machine_id TEXT NOT NULL,
                    recipe_id TEXT NOT NULL,
                    recipe_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    size_ml INTEGER NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    approval_url TEXT NOT NULL,
                    paypal_status TEXT NOT NULL,
                    paid INTEGER NOT NULL DEFAULT 0,
                    used INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    paid_at TEXT,
                    used_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_payment_orders_created
                    ON payment_orders(created_at);
                """
            )

    def save_price_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        machine_id = str(payload.get("machineId", "")).strip()
        if not machine_id or len(machine_id) > 80:
            raise ValidationError("Ungültige Maschinen-ID")
        currency = str(payload.get("currency", "EUR")).strip().upper()
        if currency != "EUR":
            raise ValidationError("Aktuell wird nur EUR unterstützt")

        defaults = payload.get("defaultPrices")
        if not isinstance(defaults, dict):
            raise ValidationError("Standardpreise fehlen")
        cocktail_cents = parse_money(defaults.get("cocktail"), "cocktail", allow_zero=True)
        mocktail_cents = parse_money(defaults.get("mocktail"), "mocktail", allow_zero=True)
        shot_cents = parse_money(defaults.get("shot"), "shot", allow_zero=True)

        recipe_prices_raw = payload.get("recipePrices", {})
        if not isinstance(recipe_prices_raw, dict):
            raise ValidationError("Rezeptpreise sind ungültig")
        recipe_prices: dict[str, int] = {}
        for recipe_id, value in recipe_prices_raw.items():
            key = str(recipe_id).strip()
            if not key or len(key) > 120:
                raise ValidationError("Ungültige Rezept-ID in den Preisen")
            recipe_prices[key] = parse_money(value, f"recipe:{key}", allow_zero=True)

        with self._db() as db:
            db.execute(
                """
                INSERT INTO payment_config (
                    id, machine_id, currency, cocktail_cents, mocktail_cents,
                    shot_cents, recipe_prices_json, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    machine_id=excluded.machine_id,
                    currency=excluded.currency,
                    cocktail_cents=excluded.cocktail_cents,
                    mocktail_cents=excluded.mocktail_cents,
                    shot_cents=excluded.shot_cents,
                    recipe_prices_json=excluded.recipe_prices_json,
                    updated_at=excluded.updated_at
                """,
                (
                    machine_id,
                    currency,
                    cocktail_cents,
                    mocktail_cents,
                    shot_cents,
                    json.dumps(recipe_prices, separators=(",", ":")),
                    utc_iso(),
                ),
            )
        return {
            "ok": True,
            "machineId": machine_id,
            "currency": currency,
            "recipePriceCount": len(recipe_prices),
        }

    def _price_config(self) -> sqlite3.Row:
        with self._db() as db:
            row = db.execute("SELECT * FROM payment_config WHERE id=1").fetchone()
        if row is None:
            raise PaymentError(
                "Zahlungspreise sind noch nicht mit dem Raspberry synchronisiert",
                409,
            )
        return row

    def _server_price(self, machine_id: str, recipe_id: str, category: str) -> tuple[int, str]:
        config = self._price_config()
        if machine_id != config["machine_id"]:
            raise PaymentError("Maschinen-ID stimmt nicht mit der lokalen Konfiguration überein", 409)
        try:
            recipe_prices = json.loads(config["recipe_prices_json"] or "{}")
        except json.JSONDecodeError:
            recipe_prices = {}
        custom = recipe_prices.get(recipe_id)
        if custom is not None:
            return int(custom), str(config["currency"])
        column = {
            "cocktail": "cocktail_cents",
            "mocktail": "mocktail_cents",
            "shot": "shot_cents",
        }.get(category)
        if column is None:
            raise ValidationError("Unbekannte Getränkekategorie")
        return int(config[column]), str(config["currency"])

    def _access_token_value(self) -> str:
        if not self.configured:
            raise PaymentError(
                "PayPal ist auf dem Raspberry noch nicht konfiguriert. "
                "Führe 'sudo cocktailbot-paypal-config' aus.",
                503,
            )
        with self._token_lock:
            now = time.monotonic()
            if self._access_token and now < self._access_token_until:
                return self._access_token
            try:
                response = requests.post(
                    f"{self.api_base}/v1/oauth2/token",
                    auth=(self.client_id, self.client_secret),
                    data={"grant_type": "client_credentials"},
                    headers={"Accept": "application/json"},
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                raise PaymentError(f"PayPal OAuth nicht erreichbar: {exc}") from exc
            if response.status_code < 200 or response.status_code >= 300:
                raise PaymentError(
                    f"PayPal OAuth HTTP {response.status_code}: {response.text[:500]}",
                    502,
                )
            try:
                data = response.json()
            except ValueError as exc:
                raise PaymentError("PayPal OAuth lieferte ungültiges JSON") from exc
            token = str(data.get("access_token", ""))
            expires_in = int(data.get("expires_in", 300))
            if not token:
                raise PaymentError("PayPal OAuth lieferte keinen Access-Token")
            self._access_token = token
            self._access_token_until = now + max(30, expires_in - 60)
            return token

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._access_token_value()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        if request_id:
            headers["PayPal-Request-Id"] = request_id[:108]
        try:
            response = requests.request(
                method,
                f"{self.api_base}{path}",
                headers=headers,
                json=body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise PaymentError(f"PayPal API nicht erreichbar: {exc}") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise PaymentError(
                f"PayPal HTTP {response.status_code}: {response.text[:1000]}",
                502,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise PaymentError("PayPal API lieferte ungültiges JSON") from exc
        if not isinstance(data, dict):
            raise PaymentError("PayPal API lieferte eine ungültige Antwort")
        return data

    @staticmethod
    def _approval_url(data: dict[str, Any]) -> str:
        for link in data.get("links", []):
            if not isinstance(link, dict):
                continue
            if link.get("rel") in {"payer-action", "approve"}:
                return str(link.get("href", ""))
        return ""

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        machine_id = str(payload.get("machineId", "")).strip()
        recipe_id = str(payload.get("recipeId", "")).strip()
        recipe_name = str(payload.get("recipeName", "")).strip()
        category = str(payload.get("category", "")).strip()
        try:
            size_ml = int(payload.get("sizeMl", 0))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Ungültige Cocktailgröße") from exc
        if not machine_id or not recipe_id or not recipe_name:
            raise ValidationError("Bestelldaten sind unvollständig")
        if size_ml < 1 or size_ml > 5000:
            raise ValidationError("Ungültige Cocktailgröße")

        amount_cents, currency = self._server_price(machine_id, recipe_id, category)
        if amount_cents < 1:
            raise PaymentError("Für diesen Cocktail ist kein Verkaufspreis gesetzt", 409)
        local_request_id = uuid.uuid4().hex
        description = f"{recipe_name} {size_ml} ml"[:127]
        custom_id = f"{machine_id}:{recipe_id}:{size_ml}"[:127]
        order_payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": local_request_id[:64],
                    "custom_id": custom_id,
                    "description": description,
                    "amount": {
                        "currency_code": currency,
                        "value": cents_text(amount_cents),
                    },
                }
            ],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "brand_name": self.brand_name,
                        "shipping_preference": "NO_SHIPPING",
                        "user_action": "PAY_NOW",
                        "return_url": self.return_url,
                        "cancel_url": self.cancel_url,
                    }
                }
            },
        }
        data = self._request_json(
            "POST",
            "/v2/checkout/orders",
            body=order_payload,
            request_id=f"create-{local_request_id}",
        )
        order_id = str(data.get("id", ""))
        approval_url = self._approval_url(data)
        if not order_id or not approval_url:
            raise PaymentError("PayPal hat keine gültige Freigabe-URL geliefert")
        expires_at = utc_now() + timedelta(hours=6)
        paypal_status = str(data.get("status", "CREATED"))

        with self._db() as db:
            db.execute(
                """
                INSERT INTO payment_orders (
                    order_id, machine_id, recipe_id, recipe_name, category,
                    size_ml, amount_cents, currency, approval_url, paypal_status,
                    created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    machine_id,
                    recipe_id,
                    recipe_name,
                    category,
                    size_ml,
                    amount_cents,
                    currency,
                    approval_url,
                    paypal_status,
                    utc_iso(),
                    utc_iso(expires_at),
                ),
            )
        return {
            "ok": True,
            "orderId": order_id,
            "approvalUrl": approval_url,
            "expiresAt": utc_iso(expires_at),
            "amount": cents_text(amount_cents),
            "currency": currency,
            "status": paypal_status,
        }

    def _local_order(self, order_id: str) -> sqlite3.Row:
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM payment_orders WHERE order_id=?", (order_id,)
            ).fetchone()
        if row is None:
            raise PaymentError("Unbekannte PayPal-Order", 404)
        return row

    @staticmethod
    def _remote_amount(data: dict[str, Any]) -> tuple[str, str] | None:
        units = data.get("purchase_units")
        if not isinstance(units, list) or not units or not isinstance(units[0], dict):
            return None
        amount = units[0].get("amount")
        if not isinstance(amount, dict):
            return None
        return str(amount.get("value", "")), str(amount.get("currency_code", ""))

    def _validate_remote_amount(self, local: sqlite3.Row, data: dict[str, Any]) -> None:
        remote = self._remote_amount(data)
        if remote is None:
            raise PaymentError("PayPal-Antwort enthält keinen prüfbaren Betrag")
        value, currency = remote
        if value != cents_text(int(local["amount_cents"])) or currency != local["currency"]:
            raise PaymentError("PayPal-Betrag stimmt nicht mit der lokalen Bestellung überein")

    def order_status(self, order_id: str) -> dict[str, Any]:
        order_id = order_id.strip()
        if not order_id or len(order_id) > 80:
            raise ValidationError("Ungültige Order-ID")
        local = self._local_order(order_id)
        if bool(local["paid"]):
            return {
                "ok": True,
                "orderId": order_id,
                "paid": True,
                "used": bool(local["used"]),
                "status": local["paypal_status"],
            }

        remote = self._request_json("GET", f"/v2/checkout/orders/{order_id}")
        self._validate_remote_amount(local, remote)
        status = str(remote.get("status", "UNKNOWN"))

        if status == "APPROVED":
            try:
                remote = self._request_json(
                    "POST",
                    f"/v2/checkout/orders/{order_id}/capture",
                    body={},
                    request_id=f"capture-{order_id}",
                )
            except PaymentError:
                # Ein unterbrochener Capture-Request kann serverseitig trotzdem
                # erfolgreich gewesen sein. Ein erneutes GET ist idempotent und
                # verhindert Doppel-Captures.
                remote = self._request_json("GET", f"/v2/checkout/orders/{order_id}")
            self._validate_remote_amount(local, remote)
            status = str(remote.get("status", "UNKNOWN"))

        paid = status == "COMPLETED"
        now = utc_iso()
        with self._db() as db:
            db.execute(
                """
                UPDATE payment_orders
                SET paypal_status=?, paid=?, paid_at=CASE WHEN ?=1 THEN COALESCE(paid_at, ?) ELSE paid_at END
                WHERE order_id=?
                """,
                (status, 1 if paid else 0, 1 if paid else 0, now, order_id),
            )
            updated = db.execute(
                "SELECT used FROM payment_orders WHERE order_id=?", (order_id,)
            ).fetchone()
        return {
            "ok": True,
            "orderId": order_id,
            "paid": paid,
            "used": bool(updated["used"]) if updated is not None else False,
            "status": status,
        }

    def mark_used(self, order_id: str, machine_id: str) -> dict[str, Any]:
        order_id = order_id.strip()
        machine_id = machine_id.strip()
        if not order_id or not machine_id:
            raise ValidationError("Order-ID oder Maschinen-ID fehlt")
        now = utc_iso()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT paid, used, machine_id FROM payment_orders WHERE order_id=?",
                (order_id,),
            ).fetchone()
            if row is None:
                raise PaymentError("Unbekannte PayPal-Order", 404)
            if row["machine_id"] != machine_id:
                raise PaymentError("Maschinen-ID stimmt nicht", 409)
            if not bool(row["paid"]):
                raise PaymentError("Zahlung ist noch nicht abgeschlossen", 409)
            if bool(row["used"]):
                raise PaymentError("Diese Zahlung wurde bereits verwendet", 409)
            db.execute(
                "UPDATE payment_orders SET used=1, used_at=? WHERE order_id=?",
                (now, order_id),
            )
        return {"ok": True, "orderId": order_id, "used": True, "usedAt": now}

    def test_connection(self) -> dict[str, Any]:
        self._access_token_value()
        return {
            "ok": True,
            "configured": self.configured,
            "connected": True,
            "mode": self.mode,
        }

    def status(self) -> dict[str, Any]:
        with self._db() as db:
            config = db.execute("SELECT machine_id, updated_at FROM payment_config WHERE id=1").fetchone()
            counts = db.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN paid=1 THEN 1 ELSE 0 END) AS paid,
                    SUM(CASE WHEN used=1 THEN 1 ELSE 0 END) AS used
                FROM payment_orders
                """
            ).fetchone()
        return {
            "ok": True,
            "backend": "raspberry-local",
            "configured": self.configured,
            "mode": self.mode,
            "priceConfigured": config is not None,
            "machineId": config["machine_id"] if config is not None else None,
            "priceUpdatedAt": config["updated_at"] if config is not None else None,
            "orders": {
                "total": int(counts["total"] or 0),
                "paid": int(counts["paid"] or 0),
                "used": int(counts["used"] or 0),
            },
        }

class PicoLedController:
    """USB-Serial bridge to the Pico 2 MicroPython LED controller.

    The Pico is deliberately optional: a disconnected LED controller must never
    prevent pump operation. The connection is reopened automatically whenever a
    later command is sent.
    """

    def __init__(self, configured_port: str = PICO_PORT, baud: int = PICO_BAUD) -> None:
        self.configured_port = configured_port
        self.baud = baud
        self._lock = threading.RLock()
        self._serial: Any | None = None
        self.port: str | None = None
        self.last_command = ""
        self.last_response = ""
        self.last_error = ""

    def _candidates(self) -> list[str]:
        if self.configured_port.lower() != "auto":
            return [self.configured_port]
        candidates: list[str] = []
        for pattern in (
            "/dev/serial/by-id/*MicroPython*",
            "/dev/serial/by-id/*Pico*",
            "/dev/ttyACM*",
        ):
            for candidate in sorted(glob.glob(pattern)):
                if candidate not in candidates:
                    candidates.append(candidate)
        return candidates

    def _close_locked(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self.port = None

    def _connect_locked(self) -> bool:
        if self._serial is not None and getattr(self._serial, "is_open", False):
            return True
        self._close_locked()
        if serial is None:
            self.last_error = "pyserial ist nicht installiert"
            return False

        for candidate in self._candidates():
            try:
                connection = serial.Serial(
                    candidate,
                    self.baud,
                    timeout=0.15,
                    write_timeout=0.5,
                )
                # Give MicroPython USB-CDC a brief moment after opening.
                time.sleep(0.15)
                self._serial = connection
                self.port = candidate
                self.last_error = ""
                return True
            except Exception as exc:
                self.last_error = f"{candidate}: {exc}"
        return False

    def send(self, command: str) -> bool:
        command = command.strip()
        if not command:
            return False
        with self._lock:
            if not self._connect_locked():
                return False
            assert self._serial is not None
            try:
                self._serial.write((command + "\n").encode("utf-8"))
                self._serial.flush()
                self.last_command = command
                # Firmware responses are diagnostic only; do not block on them.
                time.sleep(0.02)
                response = b""
                while getattr(self._serial, "in_waiting", 0):
                    response = self._serial.readline().strip() or response
                if response:
                    self.last_response = response.decode("utf-8", errors="replace")
                self.last_error = ""
                return True
            except Exception as exc:
                self.last_error = str(exc)
                self._close_locked()
                return False

    def apply_idle(self, settings: dict[str, Any]) -> bool:
        brightness = max(0, min(255, int(settings.get("brightness", 89))))
        r = max(0, min(255, int(settings.get("r", 22))))
        g = max(0, min(255, int(settings.get("g", 217))))
        b = max(0, min(255, int(settings.get("b", 204))))
        mode = str(settings.get("mode", "solid"))
        bright_ok = self.send(f"BRIGHT {brightness}")
        command = {
            "solid": f"COLOR {r} {g} {b}",
            "rainbow": "RAINBOW",
            "breathe": f"PULSE {r} {g} {b}",
            "blink": f"BLINK {r} {g} {b}",
            # Backward compatibility for installations that saved the former
            # app value 'chase'. The current Pico firmware has no CHASE command.
            "chase": f"BLINK {r} {g} {b}",
            "off": "OFF",
        }.get(mode, f"COLOR {r} {g} {b}")
        return self.send(command) and bright_ok

    @property
    def connected(self) -> bool:
        with self._lock:
            return bool(self._serial is not None and getattr(self._serial, "is_open", False))

    def close(self) -> None:
        with self._lock:
            try:
                if self._serial is not None and getattr(self._serial, "is_open", False):
                    self._serial.write(b"OFF\n")
                    self._serial.flush()
            except Exception:
                pass
            self._close_locked()


class PumpController:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._devices = {
            number: OutputDevice(
                pin,
                active_high=ACTIVE_HIGH,
                initial_value=False,
            )
            for number, pin in enumerate(PUMP_PINS, start=1)
        }
        self._active_pumps: set[int] = set()
        self._job: PumpJob | None = None
        self._job_started_at = 0.0
        self._completed_steps = 0
        self._generation = 0
        self._closed = False
        self.machine_state: dict[str, Any] = self._load_machine_state()
        self.led_settings: dict[str, Any] = {
            "mode": "solid",
            "r": 22,
            "g": 217,
            "b": 204,
            "brightness": 89,
        }
        self.pico = PicoLedController()
        self.all_off()
        self.pico.apply_idle(self.led_settings)

    @staticmethod
    def pin_for_pump(pump: int) -> int:
        if pump < 1 or pump > PUMP_COUNT:
            raise ValidationError("Ungültige Pumpennummer")
        return PUMP_PINS[pump - 1]

    def _load_machine_state(self) -> dict[str, Any]:
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def save_machine_state(self, state: dict[str, Any]) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE_FILE.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(STATE_FILE)
        with self._lock:
            self.machine_state = state

    def _set_pump_locked(self, pump: int, enabled: bool) -> None:
        device = self._devices[pump]
        if enabled:
            device.on()
            self._active_pumps.add(pump)
        else:
            device.off()
            self._active_pumps.discard(pump)

    def all_off(self) -> None:
        with self._lock:
            for pump in self._devices:
                self._set_pump_locked(pump, False)

    def stop(self, reason: str = "Not-Aus") -> None:
        del reason
        with self._lock:
            self._generation += 1
            self.all_off()
            self._job = None
            self._job_started_at = 0.0
            self._completed_steps = 0
            closed = self._closed
        if not closed:
            self.pico.apply_idle(self.led_settings)

    def apply_led_settings(self, settings: dict[str, Any]) -> bool:
        with self._lock:
            self.led_settings = dict(settings)
            idle_now = self._job is None
        if idle_now:
            return self.pico.apply_idle(self.led_settings)
        return True

    def _restore_idle_after(self, generation: int, delay_seconds: float) -> None:
        def worker() -> None:
            time.sleep(delay_seconds)
            with self._lock:
                if self._closed or generation != self._generation or self._job is not None:
                    return
                settings = dict(self.led_settings)
            self.pico.apply_idle(settings)

        threading.Thread(
            target=worker,
            name="cocktailbot-led-restore",
            daemon=True,
        ).start()

    def _show_ready_then_idle(self, generation: int) -> None:
        self.pico.send("READY")
        self._restore_idle_after(generation, 5.0)

    def _show_error_then_idle(self, generation: int) -> None:
        self.pico.send("ERROR")
        self._restore_idle_after(generation, 5.0)

    def start(self, job: PumpJob) -> bool:
        with self._lock:
            if self._job is not None or self._closed:
                return False
            self._generation += 1
            generation = self._generation
            self.all_off()
            self._job = job
            self._job_started_at = time.monotonic()
            self._completed_steps = 0

        # Die App beschreibt den Zubereitungszustand als rot blinkend.
        self.pico.send("BLINK 255 0 0")

        thread = threading.Thread(
            target=self._run_job,
            args=(job, generation),
            name=f"cocktailbot-{job.action}",
            daemon=True,
        )
        thread.start()
        return True

    def _run_job(self, job: PumpJob, generation: int) -> None:
        started: set[int] = set()
        finished: set[int] = set()
        success = False
        failed = False

        try:
            while True:
                with self._lock:
                    if self._closed or generation != self._generation:
                        return
                    elapsed_ms = int((time.monotonic() - self._job_started_at) * 1000)

                    for index, step in enumerate(job.steps):
                        if index not in started and elapsed_ms >= step.start_offset_ms:
                            self._set_pump_locked(step.pump, True)
                            started.add(index)

                        if (
                            index in started
                            and index not in finished
                            and elapsed_ms >= step.start_offset_ms + step.duration_ms
                        ):
                            self._set_pump_locked(step.pump, False)
                            finished.add(index)
                            self._completed_steps = len(finished)

                    if len(finished) >= len(job.steps):
                        self.all_off()
                        self._job = None
                        self._job_started_at = 0.0
                        self._completed_steps = 0
                        success = True
                        break

                time.sleep(0.01)
        except Exception:
            failed = True
            raise
        finally:
            with self._lock:
                # A superseded thread must never leave an output active.
                if generation == self._generation:
                    self.all_off()
                    self._job = None
                    self._job_started_at = 0.0
                    self._completed_steps = 0

            if success:
                self._show_ready_then_idle(generation)
            elif failed and generation == self._generation:
                self._show_error_then_idle(generation)

    def status(self) -> dict[str, Any]:
        with self._lock:
            job = self._job
            active = sorted(self._active_pumps)
            if job is None or job.total_duration_ms <= 0:
                progress = 0.0
            else:
                elapsed_ms = int((time.monotonic() - self._job_started_at) * 1000)
                progress = min(1.0, elapsed_ms / job.total_duration_ms)

            return {
                "ok": True,
                "device": "CocktailBot-RaspberryPi",
                "gpioNumbering": "BCM",
                "busy": job is not None,
                "action": job.action if job else "idle",
                "currentPump": active[0] if active else 0,
                "runningPumpCount": len(active),
                "completedSteps": self._completed_steps if job else 0,
                "stepCount": len(job.steps) if job else 0,
                "progress": progress,
                "activePumps": active,
                "pumpPins": {
                    str(number): pin
                    for number, pin in enumerate(PUMP_PINS, start=1)
                },
                "machineState": self.machine_state,
                "ledState": "idle" if job is None else "preparing",
                "ledIdleMode": self.led_settings["mode"],
                "ledBrightness": self.led_settings["brightness"],
                "ledColor": {
                    "r": self.led_settings["r"],
                    "g": self.led_settings["g"],
                    "b": self.led_settings["b"],
                },
                "ledController": "Pico2-USB-Serial",
                "picoConnected": self.pico.connected,
                "picoPort": self.pico.port,
                "picoLastCommand": self.pico.last_command,
                "picoLastResponse": self.pico.last_response,
                "picoLastError": self.pico.last_error,
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._generation += 1
            self.all_off()
            for device in self._devices.values():
                device.close()
        self.pico.close()


def as_int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Ungültiges Feld: {field}") from exc


def validate_step(pump: Any, duration_ms: Any, start_offset_ms: int) -> PumpStep:
    pump_number = as_int(pump, "pump")
    duration = as_int(duration_ms, "durationMs")
    if pump_number < 1 or pump_number > PUMP_COUNT:
        raise ValidationError("Ungültige Pumpennummer")
    if duration < 1 or duration > MAX_PUMP_DURATION_MS:
        raise ValidationError("Ungültige Pumpenlaufzeit")
    if start_offset_ms + duration > MAX_JOB_DURATION_MS:
        raise ValidationError("Gesamtlaufzeit zu lang")
    return PumpStep(pump_number, start_offset_ms, duration)


def reject_duplicate_pumps(steps: list[PumpStep]) -> None:
    pumps = [step.pump for step in steps]
    if len(pumps) != len(set(pumps)):
        raise ValidationError("Eine Pumpe darf pro Auftrag nur einmal vorkommen")


def build_sequential_job(payload: dict[str, Any], action: str) -> PumpJob:
    items = payload.get("pumps")
    if not isinstance(items, list) or not items:
        raise ValidationError("Pumpenliste fehlt oder ist leer")

    steps: list[PumpStep] = []
    offset = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError("Ungültiger Pumpeneintrag")
        step = validate_step(item.get("pump"), item.get("durationMs"), offset)
        steps.append(step)
        offset += step.duration_ms

    reject_duplicate_pumps(steps)
    return PumpJob(action, "sequential", tuple(steps), offset)


def build_recipe_job(payload: dict[str, Any]) -> PumpJob:
    items = payload.get("pumps")
    if not isinstance(items, list) or not items:
        raise ValidationError("Pumpenliste fehlt oder ist leer")

    spacing = as_int(payload.get("startSpacingMs", DEFAULT_START_SPACING_MS), "startSpacingMs")
    if spacing < 0 or spacing > MAX_START_SPACING_MS:
        raise ValidationError("Ungültiger Startabstand")

    normal_items = [item for item in items if isinstance(item, dict) and not bool(item.get("delayed", False))]
    delayed_items = [item for item in items if isinstance(item, dict) and bool(item.get("delayed", False))]
    if len(normal_items) + len(delayed_items) != len(items):
        raise ValidationError("Ungültiger Pumpeneintrag")

    steps: list[PumpStep] = []
    normal_end = 0
    for index, item in enumerate(normal_items):
        offset = index * spacing
        step = validate_step(item.get("pump"), item.get("durationMs"), offset)
        steps.append(step)
        normal_end = max(normal_end, offset + step.duration_ms)

    for index, item in enumerate(delayed_items):
        offset = normal_end + index * spacing
        steps.append(validate_step(item.get("pump"), item.get("durationMs"), offset))

    reject_duplicate_pumps(steps)
    total = max(step.start_offset_ms + step.duration_ms for step in steps)
    return PumpJob("prepare_recipe", "overlapping", tuple(steps), total)


def create_app(controller: PumpController, web_root: Path) -> Flask:
    app = Flask(__name__, static_folder=None)
    payment = PaypalPaymentBackend()

    @app.after_request
    def add_cors_headers(response):  # type: ignore[no-untyped-def]
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") else "public, max-age=3600"
        return response

    @app.get("/api/status")
    def api_status():
        return jsonify(controller.status())

    @app.route("/api/command", methods=["POST", "OPTIONS"])
    def api_command():
        if request.method == "OPTIONS":
            return ("", 204)

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(ok=False, error="Ungültiges JSON"), 400

        action = str(payload.get("action", "")).strip()
        if not action:
            return jsonify(ok=False, error="Feld action fehlt"), 400

        try:
            if action == "set_led":
                mode = str(payload.get("mode", "solid"))
                if mode not in {"solid", "rainbow", "breathe", "blink", "chase", "off"}:
                    raise ValidationError("Unbekannter LED-Modus")
                values = {
                    key: as_int(payload.get(key, controller.led_settings[key]), key)
                    for key in ("r", "g", "b", "brightness")
                }
                if any(value < 0 or value > 255 for value in values.values()):
                    raise ValidationError("Ungültige LED-Farbwerte")
                settings = {"mode": mode, **values}
                transmitted = controller.apply_led_settings(settings)
                return jsonify(
                    ok=True,
                    action=action,
                    mode=mode,
                    picoConnected=controller.pico.connected,
                    transmitted=transmitted,
                )

            if action == "save_machine_state":
                state = payload.get("machineState")
                if not isinstance(state, dict):
                    raise ValidationError("machineState fehlt oder ist ungültig")
                controller.save_machine_state(state)
                return jsonify(ok=True, action=action, bytes=len(json.dumps(state)))

            if action in {"stop", "all_off"}:
                controller.stop("Not-Aus")
                return jsonify(ok=True, action="stop", message="Alle Pumpen ausgeschaltet")

            if controller.status()["busy"]:
                return jsonify(ok=False, error="Maschine ist bereits beschäftigt"), 409

            if action == "run_pump":
                step = validate_step(payload.get("pump"), payload.get("durationMs"), 0)
                job = PumpJob("run_pump", "sequential", (step,), step.duration_ms)
            elif action == "prepare_recipe":
                job = build_recipe_job(payload)
            elif action in {"prime", "clean"}:
                job = build_sequential_job(payload, action)
            else:
                raise ValidationError(f"Unbekannte action: {action}")

            if not controller.start(job):
                return jsonify(ok=False, error="Auftrag konnte nicht gestartet werden"), 409

            return (
                jsonify(
                    ok=True,
                    accepted=True,
                    action=job.action,
                    stepCount=len(job.steps),
                    totalDurationMs=job.total_duration_ms,
                    mode=job.mode,
                ),
                202,
            )
        except ValidationError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except OSError as exc:
            controller.stop("GPIO-Fehler")
            return jsonify(ok=False, error=f"GPIO-/Dateifehler: {exc}"), 500

    @app.get("/api/payment/status")
    def api_payment_status():
        return jsonify(payment.status())

    @app.route("/api/payment/test", methods=["POST", "OPTIONS"])
    def api_payment_test():
        if request.method == "OPTIONS":
            return ("", 204)
        try:
            return jsonify(payment.test_connection())
        except PaymentError as exc:
            return jsonify(ok=False, error=str(exc)), exc.status_code

    @app.route("/api/payment/config", methods=["POST", "OPTIONS"])
    def api_payment_config():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(ok=False, error="Ungültiges JSON"), 400
        try:
            return jsonify(payment.save_price_config(payload))
        except ValidationError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except PaymentError as exc:
            return jsonify(ok=False, error=str(exc)), exc.status_code

    @app.route("/api/payment/create-order", methods=["POST", "OPTIONS"])
    def api_payment_create_order():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(ok=False, error="Ungültiges JSON"), 400
        try:
            return jsonify(payment.create_order(payload)), 201
        except ValidationError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except PaymentError as exc:
            return jsonify(ok=False, error=str(exc)), exc.status_code

    @app.get("/api/payment/order-status")
    def api_payment_order_status():
        try:
            return jsonify(payment.order_status(request.args.get("orderId", "")))
        except ValidationError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except PaymentError as exc:
            return jsonify(ok=False, error=str(exc)), exc.status_code

    @app.route("/api/payment/mark-used", methods=["POST", "OPTIONS"])
    def api_payment_mark_used():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(ok=False, error="Ungültiges JSON"), 400
        try:
            return jsonify(
                payment.mark_used(
                    str(payload.get("orderId", "")),
                    str(payload.get("machineId", "")),
                )
            )
        except ValidationError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except PaymentError as exc:
            return jsonify(ok=False, error=str(exc)), exc.status_code

    @app.get("/payment/return")
    def payment_return_page():
        return (
            "<!doctype html><meta name='viewport' content='width=device-width'>"
            "<title>CocktailBot</title><body style='font-family:sans-serif;text-align:center;padding:3rem'>"
            "<h1>Zahlung freigegeben</h1><p>Du kannst dieses Fenster schließen. "
            "Die Cocktailmaschine prüft die Zahlung automatisch.</p></body>"
        )

    @app.get("/payment/cancel")
    def payment_cancel_page():
        return (
            "<!doctype html><meta name='viewport' content='width=device-width'>"
            "<title>CocktailBot</title><body style='font-family:sans-serif;text-align:center;padding:3rem'>"
            "<h1>Zahlung abgebrochen</h1><p>Es wurde kein Cocktail freigegeben.</p></body>"
        )

    @app.get("/")
    def root():
        index = web_root / "index.html"
        if index.is_file():
            return send_from_directory(web_root, "index.html")
        return jsonify(
            device="CocktailBot-RaspberryPi",
            statusEndpoint="/api/status",
            commandEndpoint="/api/command",
            paymentEndpoint="/api/payment/status",
            message="Flutter-Web-Build fehlt im konfigurierten web-root",
        )

    @app.get("/<path:resource>")
    def static_or_spa(resource: str):
        candidate = web_root / resource
        if candidate.is_file():
            return send_from_directory(web_root, resource)
        index = web_root / "index.html"
        if index.is_file():
            return send_from_directory(web_root, "index.html")
        return jsonify(ok=False, error="Datei nicht gefunden"), 404

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--web-root", type=Path, default=Path("/opt/cocktailbot/web"))
    args = parser.parse_args()

    controller = PumpController()
    atexit.register(controller.close)

    def shutdown_handler(signum: int, _frame: Any) -> None:
        controller.stop(f"Signal {signum}")
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    print("CocktailBot Raspberry Pi")
    print(f"GPIO-Modus: BCM | active_high={ACTIVE_HIGH} | mock={MOCK_GPIO}")
    print("Pumpen:", ", ".join(f"{i}=GPIO{pin}" for i, pin in enumerate(PUMP_PINS, 1)))
    print(f"Web/API: http://{args.host}:{args.port}")
    print(f"PayPal: mode={PAYPAL_MODE} | configured={bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)}")

    app = create_app(controller, args.web_root.resolve())
    app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
