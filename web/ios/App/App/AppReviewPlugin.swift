import UIKit
import StoreKit
import UserNotifications
import Capacitor

class CFFBBridgeViewController: CAPBridgeViewController {
    override func capacitorDidLoad() {
        bridge?.registerPluginInstance(AppReviewPlugin())
        bridge?.registerPluginInstance(ProMembershipPlugin())
        bridge?.registerPluginInstance(PushRuntimePlugin())
    }
}

@objc(AppReviewPlugin)
public class AppReviewPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "AppReviewPlugin"
    public let jsName = "AppReview"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "synchronize", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "request", returnType: CAPPluginReturnPromise)
    ]
    private var policy = AppReviewPolicy()
    private var keyboardVisible = false
    private var observers: [NSObjectProtocol] = []

    public override func load() {
        observers.append(NotificationCenter.default.addObserver(forName: UIResponder.keyboardWillShowNotification, object: nil, queue: .main) { [weak self] _ in
            self?.keyboardVisible = true
            self?.policy.deactivate()
            self?.notifyListeners("availabilityChanged", data: ["active": false])
        })
        observers.append(NotificationCenter.default.addObserver(forName: UIResponder.keyboardDidHideNotification, object: nil, queue: .main) { [weak self] _ in
            self?.keyboardVisible = false
            self?.notifyListeners("availabilityChanged", data: ["active": self?.activeScene != nil])
        })
        for event in [UIApplication.willResignActiveNotification, UIScene.willDeactivateNotification] {
            observers.append(NotificationCenter.default.addObserver(forName: event, object: nil, queue: .main) { [weak self] _ in
                self?.policy.deactivate()
                self?.notifyListeners("availabilityChanged", data: ["active": false])
            })
        }
        for event in [UIApplication.didBecomeActiveNotification, UIScene.didActivateNotification] {
            observers.append(NotificationCenter.default.addObserver(forName: event, object: nil, queue: .main) { [weak self] _ in
                self?.notifyListeners("availabilityChanged", data: ["active": self?.activeScene != nil])
            })
        }
    }

    deinit { observers.forEach { NotificationCenter.default.removeObserver($0) } }

    private var activeScene: UIWindowScene? {
        guard UIApplication.shared.applicationState == .active,
              let window = bridge?.viewController?.view.window,
              window.isKeyWindow, let scene = window.windowScene,
              scene.activationState == .foregroundActive else { return nil }
        return scene
    }

    private var unobstructed: Bool {
        guard !keyboardVisible, let scene = activeScene, let controller = bridge?.viewController,
              controller.presentedViewController == nil,
              controller.view.window?.rootViewController?.presentedViewController == nil else { return false }
        // UIKit can retain a non-key text-effects window at normal + 1 after
        // editing ends. It is not a blocking modal. Keyboard notifications,
        // the key scene/window and presented controllers guard actual input
        // and presentations; alert-level windows are additional blockers.
        return !scene.windows.contains { !$0.isHidden && $0.alpha > 0 && $0.windowLevel >= .alert }
    }

    private func consumed(_ accountId: String) -> Bool {
        UserDefaults.standard.bool(forKey: "cffb.automaticReview.invoked.\(accountId)")
    }

    @objc public func synchronize(_ call: CAPPluginCall) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { call.resolve(["ready": false]); return }
            let accountId = call.getString("accountId") ?? ""
            let token = call.getString("token") ?? ""
            self.policy.synchronize(accountId: accountId, token: token, safe: call.getBool("safe") == true)
            call.resolve([
                "ready": self.policy.canInvoke(accountId: accountId, token: token,
                    activeScene: self.activeScene != nil, unobstructed: self.unobstructed, consumed: self.consumed(accountId)),
                "appVersion": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "",
                "appBuild": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? ""
            ])
        }
    }

    @objc public func request(_ call: CAPPluginCall) {
        DispatchQueue.main.async { [weak self] in
            guard let self, let accountId = call.getString("accountId"), let token = call.getString("token"),
                  let scene = self.activeScene,
                  self.policy.canInvoke(accountId: accountId, token: token, activeScene: true,
                      unobstructed: self.unobstructed, consumed: self.consumed(accountId)) else {
                call.resolve(["invoked": false]); return
            }
            // Write before StoreKit. Suppression, dismissal or a crash cannot
            // clear this additional guard; the server ledger is authoritative.
            UserDefaults.standard.set(true, forKey: "cffb.automaticReview.invoked.\(accountId)")
            self.policy.deactivate()
            if #available(iOS 16.0, *) {
                AppStore.requestReview(in: scene)
            } else {
                SKStoreReviewController.requestReview(in: scene)
            }
            call.resolve(["invoked": true]) // NOT proof of display or submission.
        }
    }
}


@objc(PushRuntimePlugin)
public class PushRuntimePlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "PushRuntimePlugin"
    public let jsName = "PushRuntime"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "state", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "bindAccount", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "setBadge", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "openSettings", returnType: CAPPluginReturnPromise)
    ]
    @objc func state(_ call: CAPPluginCall) {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                #if DEBUG
                let environment = "development"
                #else
                let environment = "distribution"
                #endif
                let controller = self.bridge?.viewController
                let window = controller?.view.window
                let canPrompt = UIApplication.shared.applicationState == .active && window?.isKeyWindow == true &&
                    window?.windowScene?.activationState == .foregroundActive && controller?.presentedViewController == nil &&
                    window?.rootViewController?.presentedViewController == nil
                call.resolve(["authorization": settings.authorizationStatus.rawValue, "environment": environment, "canPrompt": canPrompt])
            }
        }
    }
    @objc func bindAccount(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard let defaults = UserDefaults(suiteName: "group.org.collegefantasyfootball.app.onesignal") else { call.reject("Push account storage is unavailable"); return }
            if let id = call.getInt("accountId"), id > 0 { defaults.set(id, forKey: "cffbPushAccountId") }
            else {
                defaults.removeObject(forKey: "cffbPushAccountId")
                UNUserNotificationCenter.current().removeAllDeliveredNotifications()
                UIApplication.shared.applicationIconBadgeNumber = 0
            }
            call.resolve()
        }
    }
    @objc func setBadge(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            UIApplication.shared.applicationIconBadgeNumber = max(0, call.getInt("count") ?? 0)
            call.resolve()
        }
    }
    @objc func openSettings(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard let url = URL(string: UIApplication.openSettingsURLString) else { call.reject("Settings is unavailable"); return }
            UIApplication.shared.open(url, options: [:]) { opened in
                if opened { call.resolve() } else { call.reject("Unable to open iPhone Settings") }
            }
        }
    }
}
