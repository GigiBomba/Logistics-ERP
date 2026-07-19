/// The four RBAC roles recognized by the mobile shell.
enum UserRole { driver, dispatcher, manager, admin }

/// The two navigation shells the app mounts.
enum AppShellVariant { driverShell, managerShell }

/// Resolves a [UserRole] to the correct [AppShellVariant].
extension AppShellRouting on UserRole {
  AppShellVariant get shellVariant => switch (this) {
    UserRole.driver => AppShellVariant.driverShell,
    UserRole.dispatcher ||
    UserRole.manager ||
    UserRole.admin => AppShellVariant.managerShell,
  };
}

/// Parses a raw role string from the backend into a [UserRole].
/// Unrecognized values resolve to [UserRole.driver] (safe default).
UserRole userRoleFromString(String role) => switch (role) {
  'driver' || 'sofer' => UserRole.driver,
  'dispatcher' || 'fleet_manager' => UserRole.dispatcher,
  'manager' => UserRole.manager,
  'admin' || 'owner' => UserRole.admin,
  _ => UserRole.driver,
};
