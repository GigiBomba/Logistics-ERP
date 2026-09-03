/// Operion AI Co-Pilot — Mobile Integration (§32)
///
/// The Co-Pilot is a first-class feature of the Flutter mobile app,
/// not a scaled-down afterthought. It talks to the exact same backend
/// surface (§30) as the PySide6 desktop client.
///
/// ## Architecture
/// - **State:** Riverpod StateNotifier mirroring backend state machine (§32.1)
/// - **Networking:** Dio-based CopilotApiClient with JWT auth (§32.2) and the
///   §28.1 retry policy (one transient retry with backoff, no retry on 4xx)
/// - **Offline:** read-only conversation history cache backed by the shared
///   LocalDatabase JSON store, with TTL + bounded size and an explicit
///   offline/read-only flag (§32.3)
/// - **Push:** Co-Pilot events (insights ready, circuit-breaker trips)
///   surfaced through the push/in-app notification layer (§32.5)
/// - **Voice:** Push-to-talk + foreground wake word, platform mic permission (§32.4)
/// - **Confirmations:** Bottom sheet with typed phrase for Level 3 (§32.6)
library;

export 'models/copilot_models.dart';
export 'network/copilot_retry_policy.dart';
export 'notifications/copilot_notification_providers.dart';
export 'notifications/copilot_notification_service.dart';
export 'providers/copilot_providers.dart';
export 'screens/copilot_screen.dart';
export 'storage/copilot_conversation_cache.dart';
export 'voice/copilot_voice_handler.dart';
export 'widgets/copilot_chat_bubble.dart';
export 'widgets/copilot_confirmation_sheet.dart';
