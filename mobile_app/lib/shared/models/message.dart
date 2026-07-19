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

class Message {
  final String id;
  final String senderId;
  final String senderName;
  final String receiverId;
  final String text;
  final DateTime timestamp;
  final bool isRead;
  final String? transportId;
  final bool hasFailed;

  const Message({
    required this.id,
    required this.senderId,
    required this.senderName,
    required this.receiverId,
    required this.text,
    required this.timestamp,
    this.isRead = false,
    this.transportId,
    this.hasFailed = false,
  });

  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      id: json['id'] as String? ?? '',
      senderId: json['senderId'] as String? ?? '',
      senderName: json['senderName'] as String? ?? '',
      receiverId: json['receiverId'] as String? ?? '',
      text: json['text'] as String? ?? '',
      timestamp: _parseDateTime(json['timestamp']),
      isRead: json['isRead'] as bool? ?? false,
      transportId: json['transportId'] as String?,
      hasFailed: json['hasFailed'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'senderId': senderId,
      'senderName': senderName,
      'receiverId': receiverId,
      'text': text,
      'timestamp': timestamp.toIso8601String(),
      'isRead': isRead,
      'transportId': transportId,
      'hasFailed': hasFailed,
    };
  }

  Message copyWith({
    String? id,
    String? senderId,
    String? senderName,
    String? receiverId,
    String? text,
    DateTime? timestamp,
    bool? isRead,
    String? transportId,
    bool? hasFailed,
  }) {
    return Message(
      id: id ?? this.id,
      senderId: senderId ?? this.senderId,
      senderName: senderName ?? this.senderName,
      receiverId: receiverId ?? this.receiverId,
      text: text ?? this.text,
      timestamp: timestamp ?? this.timestamp,
      isRead: isRead ?? this.isRead,
      transportId: transportId ?? this.transportId,
      hasFailed: hasFailed ?? this.hasFailed,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Message &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          senderId == other.senderId &&
          senderName == other.senderName &&
          receiverId == other.receiverId &&
          text == other.text &&
          timestamp == other.timestamp &&
          isRead == other.isRead &&
          transportId == other.transportId &&
          hasFailed == other.hasFailed;

  @override
  int get hashCode => Object.hash(
        id,
        senderId,
        senderName,
        receiverId,
        text,
        timestamp,
        isRead,
        transportId,
        hasFailed,
      );

  @override
  String toString() =>
      'Message(id: $id, senderName: $senderName, isRead: $isRead, '
      'transportId: $transportId, hasFailed: $hasFailed)';
}
