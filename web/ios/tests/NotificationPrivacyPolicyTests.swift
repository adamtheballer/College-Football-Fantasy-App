import Foundation
@main struct NotificationPrivacyPolicyTests {
    static func main() {
        let now = Date(timeIntervalSince1970: 100)
        let data: [String: Any] = ["recipient_user_id": 7, "expires_at": 120]
        assert(NotificationPrivacyPolicy.allows(data: data, accountId: 7, now: now))
        assert(!NotificationPrivacyPolicy.allows(data: data, accountId: nil, now: now))
        assert(!NotificationPrivacyPolicy.allows(data: data, accountId: 8, now: now))
        assert(!NotificationPrivacyPolicy.allows(data: data, accountId: 7, now: Date(timeIntervalSince1970: 120)))
        assert(!NotificationPrivacyPolicy.allows(data: ["recipient_user_id": "7", "expires_at": "120"], accountId: 7, now: now))
        assert(!NotificationPrivacyPolicy.allows(data: [:], accountId: 7, now: now))
        assert(!NotificationPrivacyPolicy.allows(data: ["recipient_user_id": 7.5, "expires_at": 120], accountId: 7, now: now))
        assert(!NotificationPrivacyPolicy.allows(data: ["recipient_user_id": true, "expires_at": 120], accountId: 1, now: now))
        assert(!NotificationPrivacyPolicy.allows(data: ["recipient_user_id": 7, "expires_at": Double.infinity], accountId: 7, now: now))
        print("Notification privacy: recipient, logout, account switch, expiry and malformed payload checks passed")
    }
}
