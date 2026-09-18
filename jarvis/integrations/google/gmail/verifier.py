"""Post-execution verification and reconciliation for Gmail operations."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from jarvis.tools.base import VerificationResult, VerificationStatus

logger = logging.getLogger(__name__)


class GmailVerifier:
    """Verifies Gmail side-effects and reconciles uncertain external states."""

    def __init__(self, client: Any) -> None:
        self.client = client

    async def verify_send(
        self,
        provider_message_id: Optional[str],
        recipient: str,
        subject: str,
        account_id: Optional[str] = None,
    ) -> VerificationResult:
        """Verify that an email send action completed successfully."""
        if not provider_message_id:
            # Attempt reconciliation
            return await self.reconcile_uncertain_send(recipient, subject, account_id)

        try:
            exists = await self.client.verify_message_exists(provider_message_id, account_id=account_id)
            if exists:
                return VerificationResult(
                    verified=True,
                    status=VerificationStatus.VERIFIED,
                    confidence=1.0,
                    evidence={"provider_message_id": provider_message_id, "recipient": recipient},
                )
            else:
                return VerificationResult(
                    verified=False,
                    status=VerificationStatus.FAILED,
                    error=f"Message ID {provider_message_id} not found on provider after send.",
                )
        except Exception as exc:
            logger.warning("Verification error for message %s: %s", provider_message_id, exc)
            return VerificationResult(
                verified=False,
                status=VerificationStatus.UNCERTAIN,
                error=f"Provider verification call failed: {exc}",
            )

    async def reconcile_uncertain_send(
        self,
        recipient: str,
        subject: str,
        account_id: Optional[str] = None,
    ) -> VerificationResult:
        """Reconcile whether an email was sent during a network timeout/drop."""
        logger.info("Reconciling uncertain send to %s with subject %r", recipient, subject)
        try:
            # Query sent folder for recent message matching recipient and subject
            query = f"to:{recipient} subject:{subject}"
            paginated = await self.client.search_messages(query=query, account_id=account_id, limit=3)

            if paginated.items:
                matched_id = paginated.items[0].message_id
                logger.info("Reconciliation SUCCESS: matched sent message ID %s", matched_id)
                return VerificationResult(
                    verified=True,
                    status=VerificationStatus.VERIFIED,
                    confidence=0.95,
                    evidence={"reconciled": True, "provider_message_id": matched_id},
                )

            return VerificationResult(
                verified=False,
                status=VerificationStatus.UNCERTAIN,
                error="Could not verify whether email was delivered. Do not resend blindly.",
            )
        except Exception as exc:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.UNCERTAIN,
                error=f"Reconciliation query failed: {exc}. Resend suppressed.",
            )
