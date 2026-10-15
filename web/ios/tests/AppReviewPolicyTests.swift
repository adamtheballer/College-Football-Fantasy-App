import Foundation

@main
struct AppReviewPolicyTests {
    static func main() {
        var policy = AppReviewPolicy()
        func allowed(_ account: String = "11", _ token: String = "context-1", active: Bool = true, free: Bool = true, consumed: Bool = false) -> Bool {
            policy.canInvoke(accountId: account, token: token, activeScene: active, unobstructed: free, consumed: consumed)
        }
        assert(!allowed())
        policy.synchronize(accountId: "11", token: "context-1", safe: true)
        assert(allowed())
        assert(!allowed("22"))
        assert(!allowed("11", "old-context"))
        assert(!allowed(active: false))
        assert(!allowed(free: false))
        assert(!allowed(consumed: true))
        policy.deactivate()
        assert(!allowed())
        policy.synchronize(accountId: "22", token: "context-2", safe: true)
        assert(!allowed())
        assert(allowed("22", "context-2"))
        policy.synchronize(accountId: "", token: "context-3", safe: true)
        assert(!allowed("", "context-3"))
        policy.synchronize(accountId: "22", token: "context-4", safe: false)
        assert(!allowed("22", "context-4"))
        print("PASS: 12 native policy assertions (context/account/scene/modal/consumption/deactivation)")
    }
}
