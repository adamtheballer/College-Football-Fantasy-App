import Foundation
import UIKit
import StoreKit
import Capacitor

/// StoreKit purchase authority is still independently verified by the server.
@objc(ProMembershipPlugin)
public class ProMembershipPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "ProMembershipPlugin"
    public let jsName = "ProMembership"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "product", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "purchase", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "restore", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "finish", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "manage", returnType: CAPPluginReturnPromise)
    ]
    private var updates: Task<Void, Never>?

    public override func load() {
        updates = Task { [weak self] in
            for await result in Transaction.updates {
                guard !Task.isCancelled else { return }
                if case .verified(let transaction) = result {
                    self?.notifyListeners("transactionUpdated", data: self?.payload(transaction, signed: result.jwsRepresentation) ?? [:])
                }
            }
        }
    }
    deinit { updates?.cancel() }

    private func payload(_ transaction: Transaction, signed: String) -> [String: Any] {
        ["signedTransaction": signed, "transactionId": String(transaction.id),
         "appAccountToken": transaction.appAccountToken?.uuidString.lowercased() ?? ""]
    }
    private func annualProduct(_ identifier: String) async throws -> Product {
        guard let product = try await Product.products(for: [identifier]).first,
              let subscription = product.subscription,
              subscription.subscriptionPeriod.unit == .year,
              subscription.subscriptionPeriod.value == 1,
              subscription.introductoryOffer == nil else {
            throw NSError(domain: "CFFBMembership", code: 1, userInfo: [NSLocalizedDescriptionKey: "Annual membership is unavailable in the App Store."])
        }
        return product
    }

    @objc public func product(_ call: CAPPluginCall) {
        guard let identifier = call.getString("productId"), !identifier.isEmpty else { call.reject("Missing membership product"); return }
        Task { @MainActor in
            do {
                let product = try await annualProduct(identifier)
                call.resolve(["displayPrice": product.displayPrice, "displayName": product.displayName])
            } catch { call.reject("The App Store price could not be loaded. Please try again.") }
        }
    }

    @objc public func purchase(_ call: CAPPluginCall) {
        guard let identifier = call.getString("productId"),
              let rawToken = call.getString("appAccountToken"), let token = UUID(uuidString: rawToken) else {
            call.reject("Sign in before purchasing membership."); return
        }
        Task { @MainActor in
            do {
                let product = try await annualProduct(identifier)
                switch try await product.purchase(options: [.appAccountToken(token)]) {
                case .success(let result):
                    guard case .verified(let transaction) = result else {
                        call.reject("App Store purchase is unverified. Restore after reconnecting."); return
                    }
                    // Never finish here. JS finishes only after server ownership verification.
                    call.resolve(["status": "purchased", "transaction": payload(transaction, signed: result.jwsRepresentation)])
                case .userCancelled: call.resolve(["status": "cancelled"])
                case .pending: call.resolve(["status": "pending"])
                @unknown default: call.reject("App Store purchase status is unavailable.")
                }
            } catch { call.reject("Membership purchase did not complete. Check the App Store and try again.") }
        }
    }

    @objc public func restore(_ call: CAPPluginCall) {
        guard let identifier = call.getString("productId"),
              let rawToken = call.getString("appAccountToken"), let token = UUID(uuidString: rawToken) else {
            call.reject("Sign in before restoring membership."); return
        }
        Task { @MainActor in
            do {
                if call.getBool("synchronize") == true { try await AppStore.sync() }
                var transactions: [[String: Any]] = []
                var seen = Set<UInt64>()
                for await result in Transaction.currentEntitlements {
                    if case .verified(let transaction) = result,
                       transaction.productID == identifier, transaction.appAccountToken == token,
                       seen.insert(transaction.id).inserted {
                        transactions.append(payload(transaction, signed: result.jwsRepresentation))
                    }
                }
                for await result in Transaction.unfinished {
                    if case .verified(let transaction) = result,
                       transaction.productID == identifier, transaction.appAccountToken == token,
                       seen.insert(transaction.id).inserted {
                        transactions.append(payload(transaction, signed: result.jwsRepresentation))
                    }
                }
                call.resolve(["transactions": transactions])
            } catch { call.reject("App Store purchases could not be restored. Your plan is unchanged.") }
        }
    }

    @objc public func finish(_ call: CAPPluginCall) {
        guard let identifier = call.getString("transactionId") else { call.reject("Missing transaction"); return }
        Task { @MainActor in
            for await result in Transaction.unfinished {
                if case .verified(let transaction) = result, String(transaction.id) == identifier {
                    await transaction.finish(); call.resolve(); return
                }
            }
            call.resolve() // Already acknowledged: retry-safe.
        }
    }

    @objc public func manage(_ call: CAPPluginCall) {
        Task { @MainActor in
            guard let scene = self.bridge?.viewController?.view.window?.windowScene else {
                call.reject("Open the app before managing your membership."); return
            }
            do { try await AppStore.showManageSubscriptions(in: scene); call.resolve() }
            catch { call.reject("App Store subscription management is unavailable.") }
        }
    }
}
