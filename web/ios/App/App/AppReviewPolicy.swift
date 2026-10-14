import Foundation

/// Platform-independent stale-context guard. Persistent consumption is injected
/// by the plugin; authorization is obtained by JS from the authenticated API.
struct AppReviewPolicy {
    private(set) var accountId = ""
    private(set) var token = ""
    private(set) var safe = false

    mutating func synchronize(accountId: String, token: String, safe: Bool) {
        self.accountId = accountId
        self.token = token
        self.safe = safe
    }

    mutating func deactivate() { safe = false }

    func canInvoke(accountId: String, token: String, activeScene: Bool, unobstructed: Bool, consumed: Bool) -> Bool {
        return safe && !accountId.isEmpty && self.accountId == accountId && self.token == token &&
            activeScene && unobstructed && !consumed
    }
}
