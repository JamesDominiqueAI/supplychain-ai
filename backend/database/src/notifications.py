from __future__ import annotations

import json
import logging
import os
import smtplib
from email.message import EmailMessage
from urllib import error, request as urllib_request

from schemas import Business, InventoryHealthItem, Product


logger = logging.getLogger(__name__)


def _public_actor_label(*, placed_by_type: str, placed_by_label: str | None) -> str:
    if placed_by_type == "llm":
        return placed_by_label or "LLM automation"
    if placed_by_type == "system":
        return placed_by_label or "System"
    if placed_by_label and "user_" not in placed_by_label:
        return placed_by_label
    return "You"


class EmailAlertService:
    """Sends operational email notifications when configured."""

    def __init__(self) -> None:
        self.resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
        self.resend_from_email = os.getenv("RESEND_FROM_EMAIL", "").strip()
        self.smtp_host = os.getenv("SMTP_HOST", "").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "").strip()
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() != "false"
        self.from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()
        self.from_name = os.getenv("SMTP_FROM_NAME", "SupplyChain AI").strip() or "SupplyChain AI"

    def send_critical_stock_alert(
        self,
        *,
        business: Business,
        product: Product,
        health_item: InventoryHealthItem,
        recipient_email: str | None,
        trigger_source: str,
    ) -> tuple[bool, str]:
        if not recipient_email:
            return False, "No notification email is configured for this workspace."
        subject = f"[Critical SKU Alert] {product.sku} needs attention"
        body = "\n".join(
            [
                f"{product.name} ({product.sku}) is now critical in {business.name}.",
                "",
                f"Current stock: {health_item.current_stock} {product.unit}",
                f"Reorder point: {health_item.reorder_point} {product.unit}",
                f"Days of cover: {health_item.days_of_cover}",
                f"Lead time: {health_item.lead_time_days} day(s)",
                f"Trigger source: {trigger_source}",
                "",
                "Recommended next step: review replenishment options and place or expedite a purchase order.",
            ]
        )

        if self.resend_api_key and self.resend_from_email:
            return self._send_resend_email(
                to_email=recipient_email,
                subject=subject,
                text_body=body,
            )
        if not self.smtp_host or not self.from_email:
            return False, "Neither Resend nor SMTP is configured. Set RESEND_API_KEY/RESEND_FROM_EMAIL or SMTP_HOST/SMTP_FROM_EMAIL."

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = recipient_email
        message.set_content(body)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20) as smtp:
                smtp.ehlo()
                if self.smtp_use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                if self.smtp_username:
                    smtp.login(self.smtp_username, self.smtp_password)
                smtp.send_message(message)
            return True, f"Critical alert email sent to {recipient_email}."
        except Exception as exc:
            logger.warning("Failed to send critical alert email for %s: %s", product.sku, exc)
            return False, str(exc)

    def send_order_placed_alert(
        self,
        *,
        business: Business,
        recipient_email: str | None,
        sku: str,
        product_name: str,
        product_category: str,
        quantity: int,
        estimated_cost: float,
        supplier_name: str | None,
        placed_by_type: str,
        placed_by_label: str | None,
    ) -> tuple[bool, str]:
        if not recipient_email:
            return False, "No notification email is configured for this workspace."

        actor_label = _public_actor_label(placed_by_type=placed_by_type, placed_by_label=placed_by_label)
        subject = f"[Order Placed] {sku} purchase order created"
        body = "\n".join(
            [
                f"A purchase order has been placed in {business.name}.",
                "",
                f"Product: {product_name} ({sku})",
                f"Category: {product_category}",
                f"Quantity: {quantity}",
                f"Estimated cost: {estimated_cost} {business.currency}",
                f"Supplier: {supplier_name or 'Not assigned'}",
                f"Placed by: {actor_label}",
                f"Origin: {'LLM automation' if placed_by_type == 'llm' else 'User action' if placed_by_type == 'user' else 'System seed'}",
            ]
        )

        if self.resend_api_key and self.resend_from_email:
            return self._send_resend_email(
                to_email=recipient_email,
                subject=subject,
                text_body=body,
            )
        if not self.smtp_host or not self.from_email:
            return False, "Neither Resend nor SMTP is configured. Set RESEND_API_KEY/RESEND_FROM_EMAIL or SMTP_HOST/SMTP_FROM_EMAIL."

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = recipient_email
        message.set_content(body)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20) as smtp:
                smtp.ehlo()
                if self.smtp_use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                if self.smtp_username:
                    smtp.login(self.smtp_username, self.smtp_password)
                smtp.send_message(message)
            return True, f"Order placement email sent to {recipient_email}."
        except Exception as exc:
            logger.warning("Failed to send order placement email for %s: %s", sku, exc)
            return False, str(exc)

    def _send_resend_email(
        self,
        *,
        to_email: str | None,
        subject: str,
        text_body: str,
    ) -> tuple[bool, str]:
        if not to_email:
            return False, "No recipient email is configured for this action."
        if not self.resend_api_key or not self.resend_from_email:
            return False, "Resend is not configured."

        payload = json.dumps(
            {
                "from": self.resend_from_email,
                "to": [to_email],
                "subject": subject,
                "text": text_body,
            }
        ).encode("utf-8")
        req = urllib_request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "supplychain-ai/0.1.0",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=20) as response:
                response_body = response.read().decode("utf-8", errors="replace")
            return True, response_body[:240] or f"Resend email sent to {to_email}."
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.warning("Resend email failed: %s %s", exc.code, detail)
            return False, detail[:240] or f"HTTP {exc.code}"
        except Exception as exc:
            logger.warning("Resend email failed: %s", exc)
            return False, str(exc)
