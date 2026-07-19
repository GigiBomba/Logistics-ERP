DateTime _parseDateTime(dynamic value) {
  if (value is int) {
    return DateTime.fromMillisecondsSinceEpoch(
        value > 1e12 ? value : value * 1000);
  }
  if (value is String) {
    return DateTime.tryParse(value) ?? DateTime.now();
  }
  return DateTime.now();
}

class Expense {
  final String id;
  final String driverId;
  final String? transportId;
  final String type; // fuel, tolls, per_diem, other
  final double amount;
  final String currency;
  final DateTime date;
  final String? receiptImageUrl;
  final String status; // pending, approved, rejected
  final String? notes;

  const Expense({
    required this.id,
    required this.driverId,
    this.transportId,
    required this.type,
    required this.amount,
    this.currency = 'RON',
    required this.date,
    this.receiptImageUrl,
    this.status = 'pending',
    this.notes,
  });

  factory Expense.fromJson(Map<String, dynamic> json) {
    return Expense(
      id: json['id'] as String? ?? '',
      driverId: json['driverId'] as String? ?? '',
      transportId: json['transportId'] as String?,
      type: json['type'] as String? ?? '',
      amount: (json['amount'] as num?)?.toDouble() ?? 0.0,
      currency: json['currency'] as String? ?? 'RON',
      date: _parseDateTime(json['date']),
      receiptImageUrl: json['receiptImageUrl'] as String?,
      status: json['status'] as String? ?? 'pending',
      notes: json['notes'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'driverId': driverId,
      'transportId': transportId,
      'type': type,
      'amount': amount,
      'currency': currency,
      'date': date.toIso8601String(),
      'receiptImageUrl': receiptImageUrl,
      'status': status,
      'notes': notes,
    };
  }

  Expense copyWith({
    String? id,
    String? driverId,
    String? transportId,
    String? type,
    double? amount,
    String? currency,
    DateTime? date,
    String? receiptImageUrl,
    String? status,
    String? notes,
  }) {
    return Expense(
      id: id ?? this.id,
      driverId: driverId ?? this.driverId,
      transportId: transportId ?? this.transportId,
      type: type ?? this.type,
      amount: amount ?? this.amount,
      currency: currency ?? this.currency,
      date: date ?? this.date,
      receiptImageUrl: receiptImageUrl ?? this.receiptImageUrl,
      status: status ?? this.status,
      notes: notes ?? this.notes,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Expense &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          driverId == other.driverId &&
          transportId == other.transportId &&
          type == other.type &&
          amount == other.amount &&
          currency == other.currency &&
          date == other.date &&
          receiptImageUrl == other.receiptImageUrl &&
          status == other.status &&
          notes == other.notes;

  @override
  int get hashCode => Object.hash(
        id,
        driverId,
        transportId,
        type,
        amount,
        currency,
        date,
        receiptImageUrl,
        status,
        notes,
      );

  @override
  String toString() =>
      'Expense(id: $id, driverId: $driverId, type: $type, '
      'amount: $amount $currency, status: $status)';
}
