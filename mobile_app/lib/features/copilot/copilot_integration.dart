/// Operion AI Co-Pilot — Mobile Integration (§32)
///
/// The Co-Pilot is a first-class feature of the Flutter mobile app,
/// not a scaled-down afterthought. It talks to the exact same backend
/// surface (§30) as the PySide6 desktop client.
///
/// ## Architecture
/// - **State:** Riverpod StateNotifier mirroring backend state machine (§32.1)
/// - **Networking:** Dio-based CopilotApiClient with JWT auth (§32.2)
/// - **Offline:** Isar-backed cache for conversation history, read-only results (§32.3)
/// - **Voice:** Push-to-talk + foreground wake word, platform mic permission (§32.4)
/// - **Confirmations:** Bottom sheet with typed phrase for Level 3 (§32.6)

export 'models/copilot_models.dart';
export 'providers/copilot_providers.dart';
export 'screens/copilot_screen.dart';
export 'voice/copilot_voice_handler.dart';
export 'widgets/copilot_chat_bubble.dart';
export 'widgets/copilot_confirmation_sheet.dart';
