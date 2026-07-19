import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_providers.dart';

/// Fetches the authenticated user's full profile from the API.
///
/// Expected response shape (all fields optional):
/// ```json
/// {
///   "id": "user_1",
///   "email": "driver@example.com",
///   "fullName": "John Doe",
///   "role": "driver",
///   "phone": "+40123456789",
///   "avatarUrl": null,
///   "driverProfile": {
///     "licenseNumber": "RO123456",
///     "licenseCategory": "B, C, CE",
///     "licenseExpiry": "2027-06-15"
///   },
///   "documents": [
///     {
///       "type": "license",
///       "expiryDate": "2027-06-15",
///       "status": "uploaded",
///       "fileUrl": "https://..."
///     }
///   ]
/// }
/// ```
///
/// Throws on network or server errors. The calling widget should handle
/// loading / error / data states via `.when()`.
final userProfileProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final client = ref.read(apiClientProvider);
  final response = await client.get('/mobile/user/profile');
  return response.data as Map<String, dynamic>;
});

/// Tracks whether a profile PATCH request is in flight.
final profileUpdatingProvider = StateProvider<bool>((ref) => false);

/// Tracks whether the profile screen is in edit mode.
final profileEditingProvider = StateProvider<bool>((ref) => false);
