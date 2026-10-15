import Foundation
import CoreFoundation

/// Validate only server-issued recipient and expiry metadata; never log notification payloads.
enum NotificationPrivacyPolicy {
    static func allows(data: [String: Any], accountId: Int?, now: Date = Date()) -> Bool {
        guard let accountId = accountId, accountId > 0,
              let recipient = data["recipient_user_id"] as? NSNumber,
              CFGetTypeID(recipient) != CFBooleanGetTypeID(),
              recipient.doubleValue == Double(accountId),
              let expiry = data["expires_at"] as? NSNumber,
              CFGetTypeID(expiry) != CFBooleanGetTypeID(),
              expiry.doubleValue.isFinite, expiry.doubleValue > now.timeIntervalSince1970 else { return false }
        return true
    }
}
