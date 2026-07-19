import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/auth_providers.dart';
import '../../core/i18n/app_localizations.dart';
import '../../shared/widgets/offline_banner.dart';

import 'home/dispatcher_home_screen.dart';
import 'fleet/fleet_map_screen.dart';
import 'home/dispatcher_providers.dart';
import '../copilot/screens/copilot_screen.dart';
import '../more_hub/screens/more_hub_screen.dart';

/// Dispatcher / Manager-mode bottom navigation shell.
///
/// Provides four tabs:
/// 1. **Overview** — dashboard with KPIs and quick actions.
/// 2. **Fleet Tracker** — live map of vehicles and drivers.
/// 3. **AI Copilot** — AI-powered chat assistant.
/// 4. **More** — additional tools (messages, teams, jobs, alerts, etc.).
///
/// Uses a denser layout and smaller label text compared to the driver shell,
/// fitting more information into the available space.
class DispatcherShell extends ConsumerStatefulWidget {
  const DispatcherShell({super.key});

  @override
  ConsumerState<DispatcherShell> createState() => _DispatcherShellState();
}

class _DispatcherShellState extends ConsumerState<DispatcherShell> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final isOffline = ref.watch(isOfflineProvider);
    final loc = context.loc;

    return Scaffold(
      body: Column(
        children: [
          // Offline banner pinned at the top
          OfflineBanner(isOffline: isOffline),
          // Main tab content fills remaining space
          Expanded(child: _buildBody()),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() => _currentIndex = index);
          ref.read(dispatcherTabProvider.notifier).state = index;
        },
        type: BottomNavigationBarType.fixed,
        selectedItemColor: Theme.of(context).colorScheme.primary,
        unselectedItemColor:
            Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.55),
        // Smaller, denser labels for enterprise / operations users
        selectedLabelStyle: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w400,
        ),
        items: [
          BottomNavigationBarItem(
            icon: const Icon(Icons.dashboard_outlined),
            activeIcon: const Icon(Icons.dashboard),
            label: loc.dispatcher_overview,
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.map_outlined),
            activeIcon: const Icon(Icons.map),
            label: loc.nav_fleetTracker,
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.auto_awesome_outlined),
            activeIcon: const Icon(Icons.auto_awesome),
            label: loc.nav_copilot,
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.menu),
            activeIcon: const Icon(Icons.menu),
            label: loc.nav_more,
          ),
        ],
      ),
    );
  }

  /// Returns the screen widget for the currently selected tab.
  Widget _buildBody() {
    switch (_currentIndex) {
      case 0:
        return const DispatcherHomeScreen();
      case 1:
        return const FleetMapScreen();
      case 2:
        return const CopilotChatScreen();
      case 3:
        return const MoreHubScreen();
      default:
        return const SizedBox.shrink();
    }
  }
}
