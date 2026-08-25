"""Concurrency tests: i18n under concurrent access — t() from multiple threads, set_language during active t() calls, load_translations during active t() calls.

Verifies that the translation system is thread-safe and does not
corrupt state under concurrent access.
"""

from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

import services.i18n as i18n

pytestmark = pytest.mark.concurrency


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(autouse=True)
def reset_i18n():
    """Reset i18n globals before and after each test."""
    old_translations = i18n._translations
    old_lang = i18n._current_lang
    old_listeners = list(i18n._listeners)
    i18n._translations = {}
    i18n._current_lang = "en"
    i18n._listeners = []
    yield
    i18n._translations = old_translations
    i18n._current_lang = old_lang
    i18n._listeners = old_listeners


@pytest.fixture
def multi_lang_translations():
    """Seed multiple languages for concurrency testing."""
    i18n._translations = {
        "en": {
            "common.hello": "Hello",
            "common.goodbye": "Goodbye",
            "common.thanks": "Thank you",
            "nav.home": "Home",
            "nav.settings": "Settings",
            "nav.trips": "Trips",
            "nav.clients": "Clients",
            "nav.fleet": "Fleet",
            "nav.analytics": "Analytics",
            "nav.documents": "Documents",
            "button.save": "Save",
            "button.cancel": "Cancel",
            "button.delete": "Delete",
            "button.edit": "Edit",
            "form.name": "Name",
            "form.email": "Email",
            "form.phone": "Phone",
            "form.address": "Address",
            "error.not_found": "Not found",
            "error.timeout": "Request timed out",
            "error.generic": "An error occurred",
            "status.loading": "Loading...",
            "status.empty": "No data",
            "status.complete": "Complete",
        },
        "ro": {
            "common.hello": "Salut",
            "common.goodbye": "La revedere",
            "common.thanks": "Mulțumesc",
            "nav.home": "Acasă",
            "button.save": "Salvează",
            "button.cancel": "Anulează",
            "error.not_found": "Nu a fost găsit",
            "status.loading": "Se încarcă...",
        },
        "fr": {
            "common.hello": "Bonjour",
            "common.goodbye": "Au revoir",
            "common.thanks": "Merci",
            "nav.home": "Accueil",
            "button.save": "Enregistrer",
            "button.cancel": "Annuler",
            "error.not_found": "Non trouvé",
            "status.loading": "Chargement...",
        },
        "de": {
            "common.hello": "Hallo",
            "common.goodbye": "Tschüss",
            "common.thanks": "Danke",
            "nav.home": "Startseite",
            "button.save": "Speichern",
            "button.cancel": "Abbrechen",
            "error.not_found": "Nicht gefunden",
            "status.loading": "Lädt...",
        },
    }
    i18n._current_lang = "en"


# ======================================================================
# t() called from 10 threads simultaneously
# ======================================================================


class TestConcurrencyI18nTranslate:
    """t() called from 10 threads simultaneously — no corruption."""

    def test_t_from_10_threads_no_corruption(self, multi_lang_translations):
        """10 threads calling t() concurrently produce correct results."""
        errors = []
        results: dict[int, dict[str, str]] = {}
        lock = threading.Lock()
        n_threads = 10
        keys = [
            "common.hello", "common.goodbye", "nav.home", "button.save",
            "error.not_found", "status.loading", "nonexistent.key",
        ]

        def translate(thread_id: int):
            thread_results = {}
            try:
                for key in keys:
                    value = i18n.t(key)
                    thread_results[key] = value
                with lock:
                    results[thread_id] = thread_results
            except Exception as e:
                with lock:
                    errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=translate, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Translation errors: {errors}"
        assert len(results) == n_threads, (
            f"Expected {n_threads} result sets, got {len(results)}"
        )

        # All threads should see the same English translations
        expected_en = {
            "common.hello": "Hello",
            "common.goodbye": "Goodbye",
            "nav.home": "Home",
            "button.save": "Save",
            "error.not_found": "Not found",
            "status.loading": "Loading...",
            "nonexistent.key": "nonexistent.key",
        }
        for tid, thread_results in results.items():
            for key, expected in expected_en.items():
                assert thread_results.get(key) == expected, (
                    f"Thread {tid}: key {key!r} expected {expected!r}, got {thread_results.get(key)!r}"
                )

    def test_t_with_placeholders_from_multiple_threads(self, multi_lang_translations):
        """t() with format placeholders called concurrently works correctly."""
        i18n._translations["en"]["welcome"] = "Welcome, {name}!"
        i18n._translations["en"]["items"] = "You have {count} items"
        i18n._translations["en"]["price"] = "Price: {amount:.2f} {currency}"

        errors = []
        lock = threading.Lock()

        def translate_with_args():
            try:
                w = i18n.t("welcome", name="World")
                assert w == "Welcome, World!", f"Got {w!r}"
                c = i18n.t("items", count=42)
                assert c == "You have 42 items", f"Got {c!r}"
                p = i18n.t("price", amount=99.99, currency="EUR")
                assert p == "Price: 99.99 EUR", f"Got {p!r}"
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=translate_with_args) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Placeholder errors: {errors}"

    def test_t_returns_same_value_across_all_threads(self, multi_lang_translations):
        """All threads see the same translation value for a given key at the same moment."""
        n_threads = 20
        results: list[str] = []
        lock = threading.Lock()
        barrier = threading.Barrier(n_threads, timeout=15)

        def read_translation():
            try:
                barrier.wait()
                val = i18n.t("common.hello")
                with lock:
                    results.append(val)
            except Exception as e:
                with lock:
                    results.append(f"ERROR:{e}")

        threads = [threading.Thread(target=read_translation) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # All non-error results should be the same
        non_errors = [r for r in results if not r.startswith("ERROR:")]
        assert len(non_errors) == n_threads, (
            f"Expected {n_threads} successful reads, got {len(non_errors)}"
        )
        assert all(v == "Hello" for v in non_errors), (
            f"Not all threads saw the same value: {set(non_errors)}"
        )


# ======================================================================
# set_language() during active t() calls
# ======================================================================


class TestConcurrencyI18nSetLanguage:
    """set_language() during active t() calls — listeners notified correctly."""

    def test_set_language_during_active_t_calls(self, multi_lang_translations):
        """Changing language while t() is called from other threads works correctly."""
        errors = []
        lock = threading.Lock()
        stop_event = threading.Event()
        translations_seen: list[str] = []

        def busy_translator():
            """Continuously translate while language changes happen."""
            while not stop_event.is_set():
                try:
                    val = i18n.t("common.hello")
                    with lock:
                        translations_seen.append(val)
                except Exception as e:
                    with lock:
                        errors.append(("translator", str(e)))
                    break

        def language_changer():
            """Switch between languages rapidly."""
            langs = ["en", "ro", "fr", "de"]
            while not stop_event.is_set():
                for lang in langs:
                    if stop_event.is_set():
                        break
                    try:
                        i18n.set_language(lang)
                    except Exception as e:
                        with lock:
                            errors.append(("set_language", lang, str(e)))
                    time.sleep(0.005)

        translator_threads = [threading.Thread(target=busy_translator) for _ in range(5)]
        changer_threads = [threading.Thread(target=language_changer) for _ in range(2)]

        for t in translator_threads + changer_threads:
            t.daemon = True
            t.start()

        time.sleep(1.0)
        stop_event.set()

        for t in translator_threads + changer_threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Concurrent set_language errors: {errors[:5]}"

        # All translations seen should be valid (one of the available languages)
        valid_greetings = {"Hello", "Salut", "Bonjour", "Hallo"}
        seen_set = set(translations_seen)
        assert seen_set.issubset(valid_greetings), (
            f"Invalid translations seen: {seen_set - valid_greetings}"
        )

    def test_set_language_listeners_notified_concurrently(self, multi_lang_translations):
        """Listeners are correctly notified when set_language is called concurrently."""
        notified_languages: list[str] = []
        lock = threading.Lock()

        def listener(lang: str):
            with lock:
                notified_languages.append(lang)

        i18n.register_listener(listener)

        def switch_and_notify(lang: str):
            try:
                i18n.set_language(lang)
            except Exception:
                pass

        # Switch through all languages rapidly
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = []
            for _ in range(5):  # 5 cycles
                for lang in ["en", "ro", "fr", "de"]:
                    futs.append(pool.submit(switch_and_notify, lang))
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception:
                    pass

        # Listener should have been called for each distinct language switch
        assert len(notified_languages) > 0, "Listener was never notified"

        # The final language must be one of the valid languages.  Under
        # concurrent set_language calls the last *notified* language need
        # not equal the final *set* language: set_language assigns the
        # internal state before notifying listeners, so two threads can
        # interleave as set(A), set(B), notify(B), notify(A) — leaving the
        # final state B while the last notification was A.
        assert i18n.get_language() in {"en", "ro", "fr", "de"}, (
            f"Final language {i18n.get_language()!r} is not a valid language"
        )
        assert set(notified_languages) <= {"en", "ro", "fr", "de"}, (
            f"Listener was notified with an unexpected language: {notified_languages}"
        )

    def test_set_language_listener_exception_does_not_affect_others(self, multi_lang_translations):
        """A failing listener does not prevent other listeners from being called."""
        call_count = [0]
        lock = threading.Lock()

        def good_listener(lang: str):
            with lock:
                call_count[0] += 1

        def bad_listener(lang: str):
            raise RuntimeError("listener failure")

        i18n.register_listener(bad_listener)
        i18n.register_listener(good_listener)

        errors = []

        def switch_language(lang: str):
            try:
                i18n.set_language(lang)
            except Exception as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=4) as pool:
            for lang in ["ro", "fr", "de", "en"]:
                pool.submit(switch_language, lang)

        # The good listener should still have been called
        assert call_count[0] > 0, "Good listener was never called despite bad listener"


# ======================================================================
# load_translations() during active t() calls
# ======================================================================


class TestConcurrencyI18nLoadTranslations:
    """load_translations() during active t() calls — no partial state."""

    def test_load_translations_during_active_t_calls(self):
        """Reloading translations while t() is called does not expose partial state."""
        from unittest.mock import patch

        errors = []
        lock = threading.Lock()
        stop_event = threading.Event()

        # Seed initial translations
        i18n._translations = {
            "en": {"key": "initial_value"},
            "ro": {"key": "valoare_initiala"},
        }
        i18n._current_lang = "en"

        def busy_translator():
            while not stop_event.is_set():
                try:
                    val = i18n.t("key")
                    # Should never be empty or malformed
                    assert isinstance(val, str), f"Translation is not a string: {val}"
                    assert len(val) > 0, "Translation is empty string"
                except Exception as e:
                    with lock:
                        errors.append(("translator", str(e)))
                    break

        def reload_translations():
            """Simulate load_translations with new data."""
            import json
            import tempfile

            # Create temp translation files
            tmpdir = tempfile.mkdtemp()
            with open(f"{tmpdir}/en.json", "w", encoding="utf-8") as f:
                json.dump({"key": "reloaded_en", "new_key": "new_value"}, f)
            with open(f"{tmpdir}/ro.json", "w", encoding="utf-8") as f:
                json.dump({"key": "reloaded_ro"}, f)

            with patch.object(i18n, "_TRANSLATIONS_DIR", tmpdir):
                for _ in range(5):  # Reload multiple times
                    if stop_event.is_set():
                        break
                    try:
                        i18n.load_translations()
                    except Exception as e:
                        with lock:
                            errors.append(("reload", str(e)))
                    time.sleep(0.01)

        translator_threads = [threading.Thread(target=busy_translator) for _ in range(5)]
        reload_thread = threading.Thread(target=reload_translations)

        for t in translator_threads:
            t.daemon = True
            t.start()
        reload_thread.start()

        time.sleep(1.0)
        stop_event.set()
        reload_thread.join(timeout=5)
        for t in translator_threads:
            t.join(timeout=3)

        assert len(errors) == 0, f"Errors during concurrent load+translate: {errors[:5]}"

    def test_load_translations_atomic_swap(self):
        """Loading translations should present an atomic view to concurrent readers."""
        from unittest.mock import patch

        errors = []
        lock = threading.Lock()
        observed_values: set[str] = set()

        i18n._translations = {"en": {"greeting": "Hello"}}
        i18n._current_lang = "en"

        barrier = threading.Barrier(2, timeout=10)

        def reader():
            try:
                barrier.wait()
                for _ in range(100):
                    val = i18n.t("greeting")
                    with lock:
                        observed_values.add(val)
            except Exception as e:
                with lock:
                    errors.append(("reader", str(e)))

        def reloader():
            import json
            import tempfile

            tmpdir = tempfile.mkdtemp()
            with open(f"{tmpdir}/en.json", "w", encoding="utf-8") as f:
                json.dump({"greeting": "Bonjour"}, f)

            try:
                barrier.wait()
                with patch.object(i18n, "_TRANSLATIONS_DIR", tmpdir):
                    i18n.load_translations()
            except Exception as e:
                with lock:
                    errors.append(("reloader", str(e)))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(reader), pool.submit(reloader)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(("submit", str(e)))

        assert len(errors) == 0, f"Atomic swap errors: {errors}"
        # Reader should only see complete state (either old or new, not partial)
        # Observed values should be either "Hello" (old) or "Bonjour" (new)
        assert observed_values.issubset({"Hello", "Bonjour"}), (
            f"Reader saw unexpected values: {observed_values}"
        )
