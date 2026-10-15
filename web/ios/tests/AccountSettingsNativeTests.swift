import XCTest
import WebKit
import Capacitor
@testable import App

/// Development host tests only. Run with an isolated localhost API and a
/// designated name-e2e account. This file is not in the production App target.
@MainActor
final class AccountSettingsNativeTests: XCTestCase {
    private var webView: WKWebView!

    private func attachWindow(_ name: String) throws {
        let window = try XCTUnwrap(webView.window)
        let rendered = UIGraphicsImageRenderer(bounds: window.bounds).image { _ in
            window.drawHierarchy(in: window.bounds, afterScreenUpdates: true)
        }
        let attachment = XCTAttachment(image: rendered)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func js(_ source: String) async throws -> Any {
        try await webView.evaluateJavaScript(source)
    }

    private func waitFor(_ expression: String, seconds: TimeInterval = 30) async throws -> Bool {
        let deadline = Date().addingTimeInterval(seconds)
        while Date() < deadline {
            if (try? await js(expression)) as? Bool == true { return true }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        return false
    }

    private func assertReady(_ expression: String, seconds: TimeInterval = 30) async throws {
        let ready = try await waitFor(expression, seconds: seconds)
        XCTAssertTrue(ready, expression)
        if !ready {
            let diagnostic = try? await js("JSON.stringify({path: location.pathname, input: document.querySelector('input[aria-label=\"Manager Name\"]')?.value, buttons: Array.from(document.querySelectorAll('button')).map(b => ({text: b.textContent.trim(), disabled: b.disabled})), text: document.querySelector('main')?.innerText})")
            print("Native Settings readiness failure:", diagnostic ?? "unavailable")
            throw NSError(domain: "NativeSettingsTest", code: 1, userInfo: [NSLocalizedDescriptionKey: expression])
        }
    }

    private func profile(token: String) async throws -> [String: Any] {
        var request = URLRequest(url: URL(string: "http://127.0.0.1:18437/auth/me")!)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await URLSession.shared.data(for: request)
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    private func reviewState(token: String, accountId: Int) async throws -> [String: Any] {
        var request = URLRequest(url: URL(string: "http://127.0.0.1:18437/app-review/state")!)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("capacitor://localhost", forHTTPHeaderField: "Origin")
        request.setValue("ios", forHTTPHeaderField: "X-CFFB-Native-Session")
        request.setValue(String(accountId), forHTTPHeaderField: "X-CFFB-Review-Account")
        let (data, response) = try await URLSession.shared.data(for: request)
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        let state = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(state["account_id"] as? Int, accountId)
        return state
    }

    func testSettingsSaveAndAutomaticReviewOnNativeRestoredSession() async throws {
        let environment = ProcessInfo.processInfo.environment
        let accountId = try XCTUnwrap(Int(environment["CFF_NATIVE_TEST_ACCOUNT_ID"] ?? ""))
        let token = try XCTUnwrap(environment["CFF_NATIVE_TEST_TOKEN"])
        let expiresAt = try XCTUnwrap(environment["CFF_NATIVE_TEST_EXPIRES_AT"])
        let user = try await profile(token: token)
        XCTAssertEqual(user["id"] as? Int, accountId)
        XCTAssertTrue((user["email"] as? String)?.hasPrefix("name-e2e-") == true)
        for _ in 0..<100 {
            let controller = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
                .flatMap { $0.windows }.first { $0.isKeyWindow }?.rootViewController as? CAPBridgeViewController
            if let view = controller?.bridge?.webView { webView = view; break }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        XCTAssertNotNil(webView)
        guard webView != nil else { return }
        try await assertReady("location.protocol === 'capacitor:' && location.hostname === 'localhost' && document.readyState === 'complete' && document.querySelector('#root')?.childElementCount > 0")
        let cached: [String: Any] = ["id": accountId, "firstName": user["first_name"]!, "email": user["email"]!, "avatarUrl": user["avatar_url"] ?? NSNull(), "isAdmin": false]
        let cacheJSON = String(data: try JSONSerialization.data(withJSONObject: cached), encoding: .utf8)!
        let tokenJSON = String(data: try JSONSerialization.data(withJSONObject: [token, expiresAt]), encoding: .utf8)!
        _ = try await js("""
            (() => { window.__cffNativeReloadPending = true; const tokens = \(tokenJSON);
              localStorage.setItem('cfb_user', JSON.stringify(\(cacheJSON)));
              localStorage.setItem('cfb_access_token', tokens[0]);
              localStorage.setItem('cfb_access_token_expires_at', tokens[1]);
              localStorage.setItem('cfb_completed_guide_\(accountId)', 'true');
              history.replaceState(null, '', '/settings');
              setTimeout(() => location.reload(), 0); return true;
            })()
            """)
        try await assertReady("window.__cffNativeReloadPending !== true && location.pathname === '/settings' && document.querySelector('input[aria-label=\"Manager Name\"]')?.disabled === false")
        _ = try await js("""
            (() => { const input = document.querySelector('input[aria-label="Manager Name"]');
              input.focus();
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, 'Native Saved Manager');
              input.dispatchEvent(new Event('input', { bubbles: true }));
              input.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            })()
            """)
        try await Task.sleep(nanoseconds: 200_000_000)
        _ = try await js("Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim().toLowerCase() === 'save changes').click(); true")
        try await assertReady("Array.from(document.querySelectorAll('button')).some(b => b.textContent.trim().toLowerCase() === 'confirm name change')", seconds: 5)
        _ = try await js("Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim().toLowerCase() === 'confirm name change').click(); true")
        try await assertReady("document.querySelector('input[aria-label=\"Manager Name\"]')?.value === 'Native Saved Manager' && document.querySelector('input[aria-label=\"Manager Name\"]')?.disabled === true")
        try await assertReady("document.querySelector('[data-testid=\"name-change-wait\"]')?.textContent.includes('Available:') === true")
        let saved = try await profile(token: token)
        XCTAssertEqual(saved["first_name"] as? String, "Native Saved Manager")
        let changedAt = saved["manager_name_changed_at"] as? String
        XCTAssertNotNil(changedAt)
        try attachWindow("native-settings-persisted-cooldown")

        _ = try await js("window.__cffNativeReloadPending = true; setTimeout(() => location.reload(), 0); true")
        try await assertReady("window.__cffNativeReloadPending !== true && document.querySelector('input[aria-label=\"Manager Name\"]')?.value === 'Native Saved Manager' && document.querySelector('input[aria-label=\"Manager Name\"]')?.disabled === true")
        let beforeReview = try await reviewState(token: token, accountId: accountId)
        XCTAssertTrue(beforeReview["review_request_claimed_at"] is NSNull)
        XCTAssertFalse(UserDefaults.standard.bool(forKey: "cffb.automaticReview.invoked.\(accountId)"))
        // The actual coordinator/bridge must invoke supported StoreKit from a
        // valid foreground scene. Apple's decision to display is not asserted.
        _ = try await js("document.querySelector('a[href=\"/\"]').click(); true")
        print("Native windows after editing:", webView.window?.windowScene?.windows.map { "\(type(of: $0)) level=\($0.windowLevel.rawValue) hidden=\($0.isHidden)" } ?? [])
        let reviewDeadline = Date().addingTimeInterval(30)
        while Date() < reviewDeadline && !UserDefaults.standard.bool(forKey: "cffb.automaticReview.invoked.\(accountId)") {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        if !UserDefaults.standard.bool(forKey: "cffb.automaticReview.invoked.\(accountId)") {
            print("Native review application state:", UIApplication.shared.applicationState.rawValue)
            for scene in UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }) {
                print("Native scene state:", scene.activationState.rawValue, "windows:", scene.windows.map { [$0.isKeyWindow ? 1 : 0, $0.isHidden ? 1 : 0, Int($0.windowLevel.rawValue)] })
            }
            let plugin = (webView.window?.rootViewController as? CAPBridgeViewController)?.bridge?.plugin(withName: "AppReview")
            if let plugin, let policy = Mirror(reflecting: plugin).children.first(where: { $0.label == "policy" })?.value as? AppReviewPolicy {
                print("Native review policy safe/account:", policy.safe, policy.accountId)
            }
            print("Native review DOM:", try await js("JSON.stringify({visibility: document.visibilityState, path: location.pathname, active: document.activeElement?.tagName, busy: !!document.querySelector('main [aria-busy=\"true\"]'), pendingGuide: localStorage.getItem('cfb_pending_guide_\(accountId)')})"))
        }
        XCTAssertTrue(UserDefaults.standard.bool(forKey: "cffb.automaticReview.invoked.\(accountId)"))
        try await assertReady("location.pathname === '/' && !/pick\\s*6|make your pick/i.test(document.querySelector('main').innerText) && !document.querySelector('main a[href=\"/saturday-pick-6\"]')")
        let claimed = try await reviewState(token: token, accountId: accountId)
        let claimTime = try XCTUnwrap(claimed["review_request_claimed_at"] as? String)
        let afterReview = try await profile(token: token)
        XCTAssertEqual(afterReview["manager_name_changed_at"] as? String, changedAt)
        try await Task.sleep(nanoseconds: 2_000_000_000)
        print("Native StoreKit handoff verified; capturing device evidence")
        try await Task.sleep(nanoseconds: 5_000_000_000)
        try attachWindow("native-after-storekit-invocation")
        // Losing the WebView cache must never erase the authoritative claim.
        _ = try await js("localStorage.removeItem('cffb_ios_review_claimed_\(accountId)'); window.__cffNativeReloadPending = true; setTimeout(() => location.reload(), 0); true")
        try await assertReady("window.__cffNativeReloadPending !== true && location.pathname === '/' && document.querySelector('main')?.innerText.includes('Native Saved Manager') === true")
        let restored = try await reviewState(token: token, accountId: accountId)
        XCTAssertEqual(restored["review_request_claimed_at"] as? String, claimTime)
        XCTAssertTrue(UserDefaults.standard.bool(forKey: "cffb.automaticReview.invoked.\(accountId)"))
    }
}
