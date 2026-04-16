from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from email.utils import formatdate
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DB_PATH = BASE_DIR / "data" / "laundry.db"

PRICE_CATALOG = {
    "Shirt": Decimal("50.00"),
    "Pants": Decimal("80.00"),
    "Saree": Decimal("120.00"),
    "Blazer": Decimal("220.00"),
    "Dress": Decimal("150.00"),
    "Bedsheet": Decimal("130.00"),
}

ORDER_STATUSES = ("RECEIVED", "PROCESSING", "READY", "DELIVERED")


class ValidationError(Exception):
    """Raised when request payloads fail validation."""


def get_db_path() -> Path:
    db_path = Path(os.environ.get("LAUNDRY_DB_PATH", DEFAULT_DB_PATH))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(get_db_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                status TEXT NOT NULL,
                total_amount REAL NOT NULL,
                estimated_delivery TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                garment_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
            );
            """
        )


def money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def default_estimated_delivery() -> str:
    return (datetime.now() + timedelta(days=2)).date().isoformat()


def generate_order_id() -> str:
    return f"ORD-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def validate_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise ValidationError("At least one garment item is required.")

    sanitized_items: list[dict[str, Any]] = []

    for raw_item in items:
        if not isinstance(raw_item, dict):
            raise ValidationError("Each garment item must be an object.")

        garment_type = str(raw_item.get("garment_type", "")).strip()
        if not garment_type:
            raise ValidationError("Garment type is required for every item.")

        try:
            quantity = int(raw_item.get("quantity", 0))
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid quantity for {garment_type}.") from exc

        if quantity <= 0:
            raise ValidationError(f"Quantity must be greater than zero for {garment_type}.")

        catalog_price = PRICE_CATALOG.get(garment_type)
        if catalog_price is not None:
            unit_price = catalog_price
        else:
            raw_price = raw_item.get("unit_price")
            if raw_price in (None, ""):
                raise ValidationError(
                    f"Unit price is required for unsupported garment type '{garment_type}'."
                )
            try:
                unit_price = money(raw_price)
            except Exception as exc:  # noqa: BLE001
                raise ValidationError(f"Invalid unit price for {garment_type}.") from exc

        if unit_price <= 0:
            raise ValidationError(f"Unit price must be greater than zero for {garment_type}.")

        line_total = money(unit_price * quantity)
        sanitized_items.append(
            {
                "garment_type": garment_type,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    return sanitized_items


def validate_order_payload(payload: dict[str, Any]) -> dict[str, Any]:
    customer_name = str(payload.get("customer_name", "")).strip()
    phone = str(payload.get("phone", "")).strip()

    if not customer_name:
        raise ValidationError("Customer name is required.")
    if not phone:
        raise ValidationError("Phone number is required.")
    if not re.fullmatch(r"\d{10}", phone):
        raise ValidationError("Phone number must be exactly 10 digits.")

    estimated_delivery = str(
        payload.get("estimated_delivery") or default_estimated_delivery()
    ).strip()

    try:
        datetime.fromisoformat(estimated_delivery)
    except ValueError as exc:
        raise ValidationError("Estimated delivery must be a valid ISO date.") from exc

    items = validate_items(payload.get("items"))
    total_amount = money(sum(item["line_total"] for item in items))

    return {
        "customer_name": customer_name,
        "phone": phone,
        "estimated_delivery": estimated_delivery,
        "items": items,
        "total_amount": total_amount,
    }


def serialize_order(order_row: sqlite3.Row, item_rows: list[sqlite3.Row]) -> dict[str, Any]:
    return {
        "order_id": order_row["id"],
        "customer_name": order_row["customer_name"],
        "phone": order_row["phone"],
        "status": order_row["status"],
        "total_amount": round(float(order_row["total_amount"]), 2),
        "total_items": sum(item["quantity"] for item in item_rows),
        "estimated_delivery": order_row["estimated_delivery"],
        "created_at": order_row["created_at"],
        "updated_at": order_row["updated_at"],
        "items": [
            {
                "garment_type": item["garment_type"],
                "quantity": item["quantity"],
                "unit_price": round(float(item["unit_price"]), 2),
                "line_total": round(float(item["line_total"]), 2),
            }
            for item in item_rows
        ],
    }


def get_order(order_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        order = connection.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if order is None:
            return None

        items = connection.execute(
            """
            SELECT garment_type, quantity, unit_price, line_total
            FROM order_items
            WHERE order_id = ?
            ORDER BY id ASC
            """,
            (order_id,),
        ).fetchall()

    return serialize_order(order, items)


def create_order(payload: dict[str, Any]) -> dict[str, Any]:
    validated = validate_order_payload(payload)
    order_id = generate_order_id()
    created_at = now_iso()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO orders (
                id, customer_name, phone, status, total_amount,
                estimated_delivery, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                validated["customer_name"],
                validated["phone"],
                ORDER_STATUSES[0],
                float(validated["total_amount"]),
                validated["estimated_delivery"],
                created_at,
                created_at,
            ),
        )

        connection.executemany(
            """
            INSERT INTO order_items (
                order_id, garment_type, quantity, unit_price, line_total
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    order_id,
                    item["garment_type"],
                    item["quantity"],
                    float(item["unit_price"]),
                    float(item["line_total"]),
                )
                for item in validated["items"]
            ],
        )

    order = get_order(order_id)
    if order is None:
        raise RuntimeError("Order was created but could not be loaded.")
    return order


def update_order_status(order_id: str, status: str) -> dict[str, Any]:
    normalized_status = str(status).strip().upper()
    if normalized_status not in ORDER_STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(ORDER_STATUSES)}.")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE orders
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (normalized_status, now_iso(), order_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(order_id)

    order = get_order(order_id)
    if order is None:
        raise KeyError(order_id)
    return order


def list_orders(filters: dict[str, str]) -> list[dict[str, Any]]:
    where_clauses: list[str] = []
    params: list[Any] = []

    status = filters.get("status", "").strip().upper()
    if status:
        where_clauses.append("o.status = ?")
        params.append(status)

    query = filters.get("query", "").strip()
    if query:
        where_clauses.append("(LOWER(o.customer_name) LIKE ? OR o.phone LIKE ?)")
        params.extend([f"%{query.lower()}%", f"%{query}%"])

    garment_type = filters.get("garment_type", "").strip()
    if garment_type:
        where_clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM order_items oi
                WHERE oi.order_id = o.id
                AND LOWER(oi.garment_type) LIKE ?
            )
            """
        )
        params.append(f"%{garment_type.lower()}%")

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with get_connection() as connection:
        orders = connection.execute(
            f"""
            SELECT o.*
            FROM orders o
            {where_sql}
            ORDER BY datetime(o.created_at) DESC, o.id DESC
            """,
            params,
        ).fetchall()

        order_ids = [order["id"] for order in orders]
        item_rows_by_order: dict[str, list[sqlite3.Row]] = {order_id: [] for order_id in order_ids}

        if order_ids:
            placeholders = ", ".join("?" for _ in order_ids)
            item_rows = connection.execute(
                f"""
                SELECT order_id, garment_type, quantity, unit_price, line_total
                FROM order_items
                WHERE order_id IN ({placeholders})
                ORDER BY id ASC
                """,
                order_ids,
            ).fetchall()
            for item in item_rows:
                item_rows_by_order[item["order_id"]].append(item)

    return [serialize_order(order, item_rows_by_order.get(order["id"], [])) for order in orders]


def get_dashboard() -> dict[str, Any]:
    with get_connection() as connection:
        totals = connection.execute(
            """
            SELECT COUNT(*) AS total_orders, COALESCE(SUM(total_amount), 0) AS total_revenue
            FROM orders
            """
        ).fetchone()

        status_rows = connection.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM orders
            GROUP BY status
            """
        ).fetchall()

    orders_per_status = {status: 0 for status in ORDER_STATUSES}
    for row in status_rows:
        orders_per_status[row["status"]] = row["count"]

    return {
        "total_orders": totals["total_orders"],
        "total_revenue": round(float(totals["total_revenue"]), 2),
        "orders_per_status": orders_per_status,
    }


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0"))
    raw_body = handler.rfile.read(content_length) if content_length else b"{}"
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError("Request body must be valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")
    return payload


class LaundryRequestHandler(BaseHTTPRequestHandler):
    server_version = "MiniLaundry/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/api/health":
            self.respond_json(HTTPStatus.OK, {"status": "ok"})
            return

        if path == "/api/config":
            self.respond_json(
                HTTPStatus.OK,
                {
                    "price_catalog": {name: float(price) for name, price in PRICE_CATALOG.items()},
                    "statuses": list(ORDER_STATUSES),
                },
            )
            return

        if path == "/api/orders":
            filters = {key: values[0] for key, values in parse_qs(parsed_url.query).items()}
            self.respond_json(HTTPStatus.OK, {"orders": list_orders(filters)})
            return

        if path == "/api/dashboard":
            self.respond_json(HTTPStatus.OK, get_dashboard())
            return

        if path.startswith("/api/orders/"):
            order_id = path.removeprefix("/api/orders/").strip("/")
            order = get_order(order_id)
            if order is None:
                self.respond_json(HTTPStatus.NOT_FOUND, {"error": "Order not found."})
                return
            self.respond_json(HTTPStatus.OK, order)
            return

        self.serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/orders":
            self.respond_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})
            return

        try:
            payload = read_json_body(self)
            order = create_order(payload)
        except ValidationError as exc:
            self.respond_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self.respond_json(HTTPStatus.CREATED, order)

    def do_PATCH(self) -> None:  # noqa: N802
        if not self.path.startswith("/api/orders/") or not self.path.endswith("/status"):
            self.respond_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})
            return

        order_id = self.path.removeprefix("/api/orders/").removesuffix("/status").strip("/")

        try:
            payload = read_json_body(self)
            order = update_order_status(order_id, payload.get("status", ""))
        except ValidationError as exc:
            self.respond_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except KeyError:
            self.respond_json(HTTPStatus.NOT_FOUND, {"error": "Order not found."})
            return

        self.respond_json(HTTPStatus.OK, order)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def respond_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Date", formatdate(usegmt=True))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path: str) -> None:
        requested = "index.html" if path in ("", "/") else path.lstrip("/")
        candidate = (STATIC_DIR / requested).resolve()

        if STATIC_DIR not in candidate.parents and candidate != STATIC_DIR / "index.html":
            self.respond_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})
            return

        if not candidate.exists() or not candidate.is_file():
            self.respond_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})
            return

        content_type = guess_type(candidate.name)[0] or "application/octet-stream"
        content = candidate.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Date", formatdate(usegmt=True))
        self.end_headers()
        self.wfile.write(content)


def run() -> None:
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), LaundryRequestHandler)
    print(f"Mini Laundry app running on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
