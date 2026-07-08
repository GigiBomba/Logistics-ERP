"""Chart-loading overlay widget.

Renders a translucent dark layer with a CSS-animated spinner and a
"n / total charts ready" progress label.  Sits on top of a parent
chart area while Plotly is rendering the SVG pixmaps, and
auto-hides when the expected number of renders is reached (or after
a safety timeout).

The overlay is intentionally lightweight: no external assets, no
QPropertyAnimation, no QGraphicsEffect.  The spinner is a single
``QLabel`` whose stylesheet rotates a unicode arrow.  This keeps the
import-time cost zero and avoids pulling in modules that the host
view does not otherwise need.

The widget is designed to be dropped into any ``QWidget`` parent via
``setParent()`` followed by ``setGeometry(parent.rect())`` — the
overlay covers the full parent area.  The owning view
(``QtAnalyticsView``) is responsible for keeping the overlay
positioned as the parent resizes (it does so via a
``QTimer.singleShot`` resize hook in ``_install_overlay``).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t as _t
from ui.design_tokens import (
    BORDER_DEFAULT,
    FONT_FAMILY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

_log = logging.getLogger(__name__)


# Safety timeout: even if the renders never complete (e.g. a network
# timeout during data loading), the overlay must not block the user
# forever.  Once this expires, the overlay hides itself.
DEFAULT_TIMEOUT_MS = 30_000


class ChartLoadingOverlay(QFrame):
    """Translucent overlay with a spinner and progress label.

    The overlay is intentionally a ``QFrame`` (not a ``QWidget``) so
    the dark background can be set via stylesheet and the inner
    labels can be styled without composing with the parent's
    stylesheet.  ``WA_TransparentForMouseEvents`` is set so clicks
    pass through to the underlying chart area.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chart-loading-overlay")
        # Disable hit-testing: clicks pass through to the underlying
        # chart widgets.  Without this the overlay would swallow
        # the user's click on whatever card sits beneath it.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Stretch across the full parent.
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Internal state.
        self._expected: int = 0
        self._received: int = 0
        self._active: bool = False
        self._tab_index: int = -1  # which tab is this overlay tracking
        self._timeout_timer: QTimer | None = None

        self._build_ui()
        self.hide()

    # ── Layout ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Spinner: a single label rotating a unicode arc via a
        # ``QTimer`` that swaps a stylesheet background-position.  No
        # external dependencies; works in any theme.
        self._spinner = QLabel("\u21bb")
        self._spinner.setObjectName("chart-loading-spinner")
        self._spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner_font = QFont(FONT_FAMILY, 28)
        spinner_font.setBold(True)
        self._spinner.setFont(spinner_font)
        self._spinner.setStyleSheet(
            "color: #6366f1; background: transparent;"
            " border: none;"
        )
        outer.addWidget(self._spinner, 0, Qt.AlignmentFlag.AlignCenter)

        # Title.
        self._title = QLabel(_t("analytics.loading_title", default="Rendering charts\u2026"))
        self._title.setObjectName("chart-loading-title")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-family: '{FONT_FAMILY}';"
            " font-size: 14px; font-weight: 600; background: transparent;"
            " border: none;"
        )
        outer.addWidget(self._title, 0, Qt.AlignmentFlag.AlignCenter)

        # Progress label.
        self._progress = QLabel("")
        self._progress.setObjectName("chart-loading-progress")
        self._progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-family: '{FONT_FAMILY}';"
            " font-size: 12px; background: transparent; border: none;"
        )
        outer.addWidget(self._progress, 0, Qt.AlignmentFlag.AlignCenter)

        # ── Skeleton bars (animated pulsing placeholders) ────────
        self._skeleton_bars: list[QFrame] = []
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        for i in range(3):
            bar = QFrame(self)
            bar.setFixedHeight(12)
            bar.setFixedWidth(260)
            effect = QGraphicsOpacityEffect(bar)
            effect.setOpacity(0.5)
            bar.setGraphicsEffect(effect)
            bar.setStyleSheet(
                f"background: {TEXT_PRIMARY}44;"
                f" border-radius: 6px;"
            )
            outer.addWidget(bar, 0, Qt.AlignmentFlag.AlignCenter)
            self._skeleton_bars.append(bar)
            setattr(self, f"_skel_effect_{i}", effect)

        # Pulse skeletons via timer
        self._skel_phase = 0.0
        self._skel_timer = QTimer(self)
        self._skel_timer.setInterval(50)
        self._skel_timer.timeout.connect(self._tick_skeletons)

        # Translucent background + 1px border so the overlay reads
        # as a discrete card.  Using ``rgba(0,0,0,170)`` gives a
        # ~67 % opacity dark layer.
        self.setStyleSheet(
            "#chart-loading-overlay {"
            " background: rgba(10, 10, 15, 170);"
            f" border: 1px solid {BORDER_DEFAULT};"
            " border-radius: 12px;"
            "}"
        )

        # Continuous rotation: re-style the spinner every 80 ms to
        # produce a 12-frame spin animation.  The label text is a
        # rotating sequence of unicode arrows so the eye perceives
        # motion without any GIF / movie asset.
        self._spin_frames = ["\u21bb", "\u21ba", "\u21b2", "\u21b3"]
        self._spin_index = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(80)
        self._spin_timer.timeout.connect(self._tick_spinner)

    def _tick_spinner(self) -> None:
        self._spin_index = (self._spin_index + 1) % len(self._spin_frames)
        self._spinner.setText(self._spin_frames[self._spin_index])

    def _tick_skeletons(self) -> None:
        """Pulse skeleton bar opacity 0.3 → 0.7 → 0.3 in a sine wave."""
        import math
        self._skel_phase += 0.08
        for i in range(len(self._skeleton_bars)):
            effect = getattr(self, f"_skel_effect_{i}", None)
            if effect is not None:
                offset = 0.5 + 0.2 * math.sin(self._skel_phase + i * 1.2)
                effect.setOpacity(offset)

    # ── Public API ──────────────────────────────────────────────────

    def start(
        self,
        expected: int,
        tab_index: int = 0,
        title: str | None = None,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        """Show the overlay and start counting renders.

        ``expected`` is the number of pixmap deliveries we expect
        before the overlay hides itself.  ``tab_index`` is purely
        diagnostic (recorded for logs / future per-tab overlays).
        ``title`` overrides the default title for special cases
        (e.g. "Refreshing data\u2026").  ``timeout_ms`` is the
        safety net; the overlay hides itself after this many
        milliseconds even if not all renders have completed.
        """
        self._expected = max(1, int(expected))
        self._received = 0
        self._active = True
        self._tab_index = int(tab_index)
        if title is not None:
            self._title.setText(title)
        else:
            self._title.setText(
                _t("analytics.loading_title", default="Rendering charts\u2026")
            )
        self._refresh_progress()
        self.show()
        self.raise_()
        # Start the spin animation.
        self._spin_timer.start()
        # Start the skeleton pulse animation.
        if hasattr(self, "_skel_timer"):
            self._skel_timer.start()
        # Schedule the safety timeout.
        if self._timeout_timer is not None:
            self._timeout_timer.stop()
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_timeout)
        self._timeout_timer.start(int(timeout_ms))

    def stop(self) -> None:
        """Hide the overlay immediately and cancel timers.

        Called by ``_on_render_delivered`` when the render count
        reaches ``_expected``, and by ``QtAnalyticsView.shutdown``
        when the view is torn down.
        """
        self._active = False
        self._spin_timer.stop()
        if hasattr(self, "_skel_timer"):
            self._skel_timer.stop()
        if self._timeout_timer is not None:
            self._timeout_timer.stop()
            self._timeout_timer = None
        self.hide()

    def on_render_delivered(self, _tag: object, _pixmap) -> None:
        """Slot for ``RenderManager.signals.delivered``.

        Increments the progress counter and hides the overlay when
        the count reaches ``_expected``.  Stale signals (for
        renders on other tabs, or renders that the manager has
        already accounted for) are ignored: we just count every
        delivery as +1.

        The overlay is a shared process-wide singleton rendered into
        each tab's overlay area; counting every delivery is
        therefore too coarse.  To stay accurate, the analytics
        view installs a *per-overlay* delivery counter via
        ``_delivery_filter`` (a small lambda) when the overlay is
        shown, and that filter calls ``on_render_delivered`` only
        for renders targeting the active tab.  See
        ``QtAnalyticsView._install_overlay``.
        """
        if not self._active:
            return
        self._received += 1
        self._refresh_progress()
        if self._received >= self._expected:
            self.stop()

    # ── Qt overrides ──────────────────────────────────────────────

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        # Belt-and-braces: also stop the spin timer when hidden
        # by the layout system (e.g. parent collapsed).
        if self._spin_timer.isActive():
            self._spin_timer.stop()

    # ── Internal ───────────────────────────────────────────────────

    def _refresh_progress(self) -> None:
        # Cap the displayed count at ``_expected`` so we never show
        # "5 / 3" if a stray late delivery arrives after stop().
        shown_received = min(self._received, self._expected)
        if self._expected <= 0:
            self._progress.setText("")
            return
        template = _t(
            "analytics.loading_progress",
            default="{received} / {total} charts ready",
        )
        try:
            self._progress.setText(
                template.format(received=shown_received, total=self._expected)
            )
        except (KeyError, IndexError):
            # Defensive: if the translation file has a different
            # template, fall back to a plain text label.
            self._progress.setText(f"{shown_received} / {self._expected} charts ready")

    def _on_timeout(self) -> None:
        """Safety net: hide the overlay after ``timeout_ms``.

        This should never fire in practice — the overlay hides
        itself on the last render — but it prevents the user from
        being stuck with a frozen overlay if a render hangs (e.g.
        a data query times out and the chart never sends a
        pixmap).
        """
        if not self._active:
            return
        _log.warning(
            "ChartLoadingOverlay timeout reached "
            "(tab=%d, received=%d/%d); hiding",
            self._tab_index, self._received, self._expected,
        )
        self.stop()
