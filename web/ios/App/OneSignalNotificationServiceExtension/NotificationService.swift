import UserNotifications
import OneSignalExtension

class NotificationService: UNNotificationServiceExtension {
    private var contentHandler: ((UNNotificationContent) -> Void)?
    private var request: UNNotificationRequest?
    private var bestAttempt: UNMutableNotificationContent?

    override func didReceive(_ request: UNNotificationRequest, withContentHandler handler: @escaping (UNNotificationContent) -> Void) {
        let defaults = UserDefaults(suiteName: "group.org.collegefantasyfootball.app.onesignal")
        let accountId = defaults?.object(forKey: "cffbPushAccountId") as? Int
        let custom = request.content.userInfo["custom"] as? [String: Any]
        let data = custom?["a"] as? [String: Any] ?? [:]
        guard NotificationPrivacyPolicy.allows(data: data, accountId: accountId) else {
            // An offline logout still removes private content before native presentation.
            handler(UNMutableNotificationContent())
            return
        }
        self.request = request
        let guardedHandler: (UNNotificationContent) -> Void = { content in
            let currentAccount = UserDefaults(suiteName: "group.org.collegefantasyfootball.app.onesignal")?.object(forKey: "cffbPushAccountId") as? Int
            handler(NotificationPrivacyPolicy.allows(data: data, accountId: currentAccount) ? content : UNMutableNotificationContent())
        }
        self.contentHandler = guardedHandler
        self.bestAttempt = request.content.mutableCopy() as? UNMutableNotificationContent
        if let content = bestAttempt {
            content.title = data["alert_title"] as? String ?? content.title
            content.body = data["alert_body"] as? String ?? content.body
            OneSignalExtension.didReceiveNotificationExtensionRequest(request, with: content, withContentHandler: guardedHandler)
        } else { guardedHandler(request.content) }
    }

    override func serviceExtensionTimeWillExpire() {
        if let request = request, let content = bestAttempt, let handler = contentHandler {
            OneSignalExtension.serviceExtensionTimeWillExpireRequest(request, with: content)
            handler(content)
        }
    }
}
