from typing import Callable, List, Tuple
from services.i18n import t, register_listener, unregister_listener

class I18nMixin:
    """Mixin to handle widget translation registration and automatic cleanup."""
    
    def __init__(self):
        self._i18n_widgets: List[Tuple[object, str, str]] = []
        self._i18n_callback: Callable[[str], None] = self._on_language_changed_mixin
        register_listener(self._i18n_callback)

    def i18n_tag(self, widget: object, key: str, prefix: str = ""):
        """Register a widget for automatic translation updates."""
        self._i18n_widgets.append((widget, key, prefix))
        # Initial translation
        self._update_widget_text(widget, key, prefix)

    def _on_language_changed_mixin(self, lang: str):
        """Internal callback for language changes."""
        self.refresh_translations_mixin()
        if hasattr(self, "refresh_translations"):
            self.refresh_translations()

    def refresh_translations_mixin(self):
        """Update all tagged widgets with current translations."""
        for widget, key, prefix in self._i18n_widgets:
            self._update_widget_text(widget, key, prefix)

    def _update_widget_text(self, widget, key, prefix):
        try:
            # CustomTkinter widgets use configure(text=...), standard tk use config(text=...)
            if hasattr(widget, "configure"):
                widget.configure(text=f"{prefix}{t(key)}")
            elif hasattr(widget, "config"):
                widget.config(text=f"{prefix}{t(key)}")
        except Exception:
            pass

    def i18n_cleanup(self):
        """Unregister the listener to prevent memory leaks."""
        unregister_listener(self._i18n_callback)
