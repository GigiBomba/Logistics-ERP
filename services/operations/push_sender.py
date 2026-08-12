"""FCM push sender — delivers alert/approval notifications to mobile devices.

Design notes (Gate-31)
----------------------
Event subscription
    The sender registers with the ``NotificationCenter`` in-process subscriber
    list via ``notification_center.subscribe(cb)`` — the same mechanism the
    email path and other in-process subscribers use.  ``NotificationCenter``
    invokes every subscriber as ``cb(event_type, alert_data)`` where
    ``event_type`` is ``'alert_created'`` / ``'alert_resolved'`` and
    ``alert_data`` is ``Alert.to_dict()`` (see
    ``services/operations/notification_center.py``).

Payload contract
    Data-only messages (no FCM ``notification`` wrapper) so the mobile router
    can render rich inline actions.  Shape per the mobile router contract:
    ``{type: 'alert'|'approval', alert_id, title, message, message_id}``.
    ``message_id`` is unique per send (``f'{alert_id}-{uuid}'``) — the iOS-18
    notification-deduplication layer keys on it, so a re-fired alert does not
    stack duplicate banners.

Platform mapping
    ``firebase_admin.messaging`` transparently routes one token namespace to
    both transports: Android tokens via FCM, iOS (APNs) tokens via the APNs
    configuration stored on the Firebase project (p8 key / team id / key id /
    topic).  firebase-admin handles the translation; only data payloads are
    sent and APNs presentation fields (sound/badge/content-available) are
    intentionally left to the client app.

Token cleanup / retry
    Per-message ``UnregisteredError`` / ``InvalidArgumentError`` responses
    deactivate the failing device token (``UPDATE mobile_devices
    SET is_active = 0``) so dead tokens stop churning the send loop.
    Transient transport failures (``UnavailableError`` / ``InternalError``)
    are retried at most 3 times with a bounded 1s / 4s / 16s backoff.

firebase-admin is imported lazily (only inside the enabled path), so this
module stays importable — and a graceful no-op — in environments without the
package installed.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger("operations.push_sender")

# FCM multicast batch size (the FCM API limit for one batch).
BATCH_SIZE = 500
# Seconds to sleep between retries — bounded (3 retries max, ~21s worst case).
RETRY_DELAYS = (1, 4, 16)
# firebase_admin app name — lets multiple PushSender instances coexist.
_APP_NAME = "operion_fcm_push"


class PushSender:
    """Deliver alert/approval notifications to company mobile devices via FCM.

    ``firebase_admin`` is initialised only when ``OPERION_FIREBASE_CREDENTIALS``
    points to an existing service-account JSON file; otherwise the sender stays
    disabled (warning logged) and every call is a graceful no-op.

    Args:
        notification_center: optional ``NotificationCenter`` to subscribe to
            (the alert-created/alert-resolved in-process subscriber list).
        credentials_path: explicit path to the Firebase service-account JSON;
            defaults to the ``OPERION_FIREBASE_CREDENTIALS`` env var.
        db: optional ``DatabaseManager`` used to query ``mobile_devices`` and
            deactivate dead tokens.  Falls back to ``notification_center._db``
            when only the center is provided.
    """

    def __init__(
        self,
        notification_center=None,
        credentials_path: Optional[str] = None,
        db=None,
    ):
        self._notification_center = notification_center
        # An explicit db wins; otherwise reuse the center's shared handle.
        self._db = db
        if self._db is None and notification_center is not None:
            self._db = getattr(notification_center, "_db", None)
        self._enabled = False
        self._subscribed = False
        self._batch_size = BATCH_SIZE
        self._retry_delays = list(RETRY_DELAYS)

        path = credentials_path or os.environ.get("OPERION_FIREBASE_CREDENTIALS", "")
        if not path or not os.path.isfile(path):
            logger.warning(
                "FCM push sender disabled — OPERION_FIREBASE_CREDENTIALS not set "
                "or file missing (%s).",
                path or "<unset>",
            )
            return

        try:
            import firebase_admin
            from firebase_admin import credentials as _fb_credentials
        except Exception as exc:  # pragma: no cover — env-specific
            logger.warning("FCM push sender disabled — firebase-admin unavailable: %s", exc)
            return

        try:
            try:
                self._app = firebase_admin.get_app(_APP_NAME)
            except ValueError:
                self._app = firebase_admin.initialize_app(
                    credential=_fb_credentials.Certificate(path), name=_APP_NAME
                )
            self._enabled = True
            logger.info("FCM push sender initialised from %s", path)
        except Exception as exc:
            logger.warning("FCM push sender initialisation failed: %s", exc)
            return

        if notification_center is not None:
            notification_center.subscribe(self._on_alert_event)
            self._subscribed = True

    # ── Public surface ──────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    def shutdown(self) -> None:
        """Unsubscribe from the NotificationCenter (idempotent)."""
        if self._subscribed and self._notification_center is not None:
            try:
                self._notification_center.unsubscribe(self._on_alert_event)
            except Exception:
                pass
            self._subscribed = False

    # ── Event subscription ──────────────────────────────────────────────

    def _on_alert_event(self, event_type: str, alert_data: Dict[str, Any]) -> None:
        """NotificationCenter in-process subscriber callback.

        ``event_type`` is ``'alert_created'`` or ``'alert_resolved'`` — the
        strings ``NotificationCenter._notify_all`` passes to its subscribers
        (the email path precedent).
        """
        if not self._enabled:
            return
        try:
            self._dispatch_alert(event_type, alert_data)
        except Exception as exc:
            logger.exception("FCM push dispatch failed: %s", exc)

    # ── Dispatch pipeline ───────────────────────────────────────────────

    def _dispatch_alert(self, event_type: str, alert_data: Dict[str, Any]) -> None:
        alert_id = alert_data.get("id") or alert_data.get("alert_id") or ""
        if not alert_id:
            logger.debug("Alert event without id — skipping FCM push")
            return

        tokens = self._active_tokens(self._company_id(alert_data))
        if not tokens:
            return

        payload = self._build_payload(event_type, alert_data, str(alert_id))
        for batch in self._batches(tokens):
            response = self._send_batch_with_retry(payload, batch)
            if response is not None:
                self._process_response(response, batch)

    @staticmethod
    def _company_id(alert_data: Dict[str, Any]) -> Optional[int]:
        """Company id for tenant scoping, from the event's own data.

        Prefer a top-level ``company_id``; fall back to the alert's
        ``metadata`` (where tenant-aware producers stamp it).  ``None`` when
        the event carries no tenant, in which case all active devices are
        targeted (legacy producers that do not stamp company_id).
        """
        cid = alert_data.get("company_id")
        if cid is None:
            meta = alert_data.get("metadata")
            if isinstance(meta, dict):
                cid = meta.get("company_id")
        return int(cid) if cid is not None else None

    def _active_tokens(self, company_id: Optional[int]) -> List[str]:
        db = self._db
        if db is None:
            logger.debug("PushSender has no DB handle — cannot query mobile_devices")
            return []
        try:
            if company_id is not None:
                rows = db.execute(
                    "SELECT token FROM mobile_devices "
                    "WHERE is_active = 1 AND company_id = ?",
                    (company_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT token FROM mobile_devices WHERE is_active = 1",
                ).fetchall()
            return [str(r["token"]) for r in rows]
        except Exception as exc:
            logger.warning("Failed to query mobile_devices: %s", exc)
            return []

    def _build_payload(self, event_type: str, alert_data: Dict[str, Any],
                       alert_id: str) -> Dict[str, str]:
        """Build the data-only payload per the mobile router contract."""
        alert_type = str(alert_data.get("type") or "")
        push_type = "approval" if alert_type == "approval" else "alert"
        return {
            "type": push_type,
            "alert_id": alert_id,
            "title": str(alert_data.get("title") or "Alert"),
            "message": str(alert_data.get("message") or ""),
            "message_id": self._new_message_id(alert_id),
        }

    def _new_message_id(self, alert_id: str) -> str:
        """Unique per-send id the iOS-18 dedupe layer keys on."""
        return f"{alert_id}-{uuid.uuid4().hex}"

    def _batches(self, tokens: List[str]) -> Iterator[List[str]]:
        for i in range(0, len(tokens), self._batch_size):
            yield tokens[i:i + self._batch_size]

    # ── FCM send (with bounded retry) ───────────────────────────────────

    def _send_batch_with_retry(self, payload: Dict[str, str],
                               tokens: List[str]) -> Any:
        """Send one multicast batch; retry transient failures 3× (1s/4s/16s).

        Returns the ``BatchResponse`` on success, or ``None`` after a permanent
        failure / exhausted retries.
        """
        import firebase_admin.messaging as _messaging

        attempts = 0
        while True:
            attempts += 1
            try:
                message = _messaging.MulticastMessage(data=payload, tokens=tokens)
                return _messaging.send_each_for_multicast(message, app=self._app)
            except (_messaging.UnavailableError, _messaging.InternalError) as exc:
                if attempts > len(self._retry_delays):
                    logger.error(
                        "FCM transient failure after %d attempts — giving up: %s",
                        attempts, exc,
                    )
                    return None
                delay = self._retry_delays[attempts - 1]
                logger.warning(
                    "FCM transient failure (attempt %d/%d) — retrying in %ss: %s",
                    attempts, len(self._retry_delays) + 1, delay, exc,
                )
                time.sleep(delay)
            except _messaging.UnregisteredError as exc:
                # Whole-batch UNREGISTERED → every token in this batch is dead.
                logger.warning(
                    "FCM batch UNREGISTERED — deactivating %d token(s): %s",
                    len(tokens), exc,
                )
                self._deactivate_tokens(tokens)
                return None
            except Exception as exc:
                # InvalidArgument / other permanent errors: log and drop.  Token
                # cleanup for those happens per-response (see _process_response).
                logger.error("FCM send failed (permanent): %s", exc)
                return None

    def _process_response(self, response: Any, tokens: List[str]) -> None:
        """Deactivate tokens whose per-message response is Unregistered/InvalidArgument."""
        import firebase_admin.messaging as _messaging

        try:
            responses = list(response.responses)
        except Exception as exc:
            logger.warning("FCM batch response unreadable: %s", exc)
            return
        if len(responses) != len(tokens):
            logger.warning(
                "FCM batch response count %d != tokens %d — skipping cleanup",
                len(responses), len(tokens),
            )
            return

        failing = []
        for token, send_response in zip(tokens, responses):
            try:
                if send_response.success:
                    continue
                exc = send_response.exception
                if exc is None:
                    continue
                if isinstance(exc, (_messaging.UnregisteredError,
                                    _messaging.InvalidArgumentError)):
                    failing.append(token)
            except Exception:
                continue
        if failing:
            self._deactivate_tokens(failing)

    def _deactivate_tokens(self, tokens: List[str]) -> None:
        """Deactivate the failing tokens so dead devices stop being targeted."""
        db = self._db
        if db is None or not tokens:
            return
        try:
            placeholders = ", ".join("?" for _ in tokens)
            db.execute(
                f"UPDATE mobile_devices SET is_active = 0 "
                f"WHERE token IN ({placeholders})",
                tuple(tokens),
            )
            db.commit()
            logger.info("Deactivated %d device token(s)", len(tokens))
        except Exception as exc:
            logger.warning("Failed to deactivate device tokens: %s", exc)
