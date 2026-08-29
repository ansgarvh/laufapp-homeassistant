import Foundation
import Security

enum KeychainStore {
    private static let service = "de.ansgarvh.laufapp"

    static func set(_ value: String, for key: String) throws {
        let data = Data(value.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)
        var add = query
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(add as CFDictionary, nil)
        guard status == errSecSuccess else { throw NSError(domain: NSOSStatusErrorDomain, code: Int(status)) }
    }

    static func get(_ key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(_ key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)
    }
}

@MainActor
final class AppSettings: ObservableObject {
    @Published var homeAssistantURL: String {
        didSet { UserDefaults.standard.set(homeAssistantURL, forKey: "homeAssistantURL") }
    }
    @Published private(set) var hasToken: Bool

    init() {
        homeAssistantURL = UserDefaults.standard.string(forKey: "homeAssistantURL") ?? ""
        hasToken = KeychainStore.get("homeAssistantToken")?.isEmpty == false
    }

    func saveToken(_ token: String) throws {
        try KeychainStore.set(token.trimmingCharacters(in: .whitespacesAndNewlines), for: "homeAssistantToken")
        hasToken = true
    }

    func token() -> String? { KeychainStore.get("homeAssistantToken") }

    func reset() {
        homeAssistantURL = ""
        KeychainStore.delete("homeAssistantToken")
        hasToken = false
    }
}
