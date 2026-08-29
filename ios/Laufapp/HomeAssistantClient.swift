import Foundation
import WebKit

enum HomeAssistantClientError: LocalizedError {
    case invalidURL
    case websocketProtocol
    case authenticationFailed
    case supervisorRequestFailed(String)
    case laufappNotFound
    case invalidResponse

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Ungültige Home-Assistant-URL."
        case .websocketProtocol: return "Home-Assistant-WebSocket antwortet unerwartet."
        case .authenticationFailed: return "Home-Assistant-Anmeldung fehlgeschlagen."
        case .supervisorRequestFailed(let text): return "Supervisor-Anfrage fehlgeschlagen: \(text)"
        case .laufappNotFound: return "Das Laufapp-Ingress-Panel wurde nicht gefunden."
        case .invalidResponse: return "Home Assistant lieferte eine ungültige Antwort."
        }
    }
}

actor HomeAssistantClient {
    let baseURL: URL
    let token: String
    private var messageID = 1

    init(baseURL: URL, token: String) {
        self.baseURL = baseURL
        self.token = token
    }

    private func websocketURL() throws -> URL {
        guard var c = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else { throw HomeAssistantClientError.invalidURL }
        c.scheme = c.scheme == "https" ? "wss" : "ws"
        c.path = "/api/websocket"
        c.query = nil
        c.fragment = nil
        guard let url = c.url else { throw HomeAssistantClientError.invalidURL }
        return url
    }

    private func decode(_ message: URLSessionWebSocketTask.Message) throws -> [String: Any] {
        let data: Data
        switch message {
        case .data(let d): data = d
        case .string(let s): data = Data(s.utf8)
        @unknown default: throw HomeAssistantClientError.websocketProtocol
        }
        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw HomeAssistantClientError.invalidResponse
        }
        return object
    }

    private func send(_ object: [String: Any], on socket: URLSessionWebSocketTask) async throws {
        let data = try JSONSerialization.data(withJSONObject: object)
        guard let string = String(data: data, encoding: .utf8) else { throw HomeAssistantClientError.invalidResponse }
        try await socket.send(.string(string))
    }

    private func authenticate(_ socket: URLSessionWebSocketTask) async throws {
        let required = try decode(try await socket.receive())
        guard required["type"] as? String == "auth_required" else { throw HomeAssistantClientError.websocketProtocol }
        try await send(["type": "auth", "access_token": token], on: socket)
        let response = try decode(try await socket.receive())
        guard response["type"] as? String == "auth_ok" else { throw HomeAssistantClientError.authenticationFailed }
    }

    private func supervisor(_ endpoint: String, method: String = "get", data: [String: Any]? = nil, on socket: URLSessionWebSocketTask) async throws -> Any {
        let id = messageID
        messageID += 1
        var request: [String: Any] = [
            "id": id,
            "type": "supervisor/api",
            "endpoint": endpoint,
            "method": method,
        ]
        if let data { request["data"] = data }
        try await send(request, on: socket)
        while true {
            let response = try decode(try await socket.receive())
            guard response["id"] as? Int == id else { continue }
            guard response["type"] as? String == "result" else { continue }
            guard response["success"] as? Bool == true else {
                let error = response["error"] as? [String: Any]
                throw HomeAssistantClientError.supervisorRequestFailed(error?["message"] as? String ?? endpoint)
            }
            return response["result"] as Any
        }
    }

    func resolveIngress() async throws -> IngressContext {
        let socket = URLSession.shared.webSocketTask(with: try websocketURL())
        socket.resume()
        defer { socket.cancel(with: .normalClosure, reason: nil) }
        try await authenticate(socket)

        guard let panelsResult = try await supervisor("/ingress/panels", on: socket) as? [String: Any],
              let panels = panelsResult["panels"] as? [String: Any] else {
            throw HomeAssistantClientError.invalidResponse
        }
        var slug: String?
        for (key, value) in panels {
            guard let panel = value as? [String: Any] else { continue }
            if (panel["title"] as? String)?.localizedCaseInsensitiveContains("Laufapp") == true {
                slug = key
                break
            }
        }
        guard let slug else { throw HomeAssistantClientError.laufappNotFound }

        guard let addon = try await supervisor("/addons/\(slug)/info", on: socket) as? [String: Any],
              let ingressPath = addon["ingress_url"] as? String,
              !ingressPath.isEmpty else {
            throw HomeAssistantClientError.invalidResponse
        }
        guard let sessionResult = try await supervisor("/ingress/session", method: "post", on: socket) as? [String: Any],
              let session = sessionResult["session"] as? String else {
            throw HomeAssistantClientError.invalidResponse
        }
        guard let appURL = URL(string: ingressPath.hasSuffix("/") ? ingressPath : ingressPath + "/", relativeTo: baseURL)?.absoluteURL,
              let host = baseURL.host else {
            throw HomeAssistantClientError.invalidURL
        }
        return IngressContext(appURL: appURL, session: session, cookieDomain: host)
    }

    func installIngressCookie(_ context: IngressContext, into webView: WKWebView) async {
        guard let cookie = HTTPCookie(properties: [
            .domain: context.cookieDomain,
            .path: "/api/hassio_ingress/",
            .name: "ingress_session",
            .value: context.session,
            .secure: baseURL.scheme == "https" ? "TRUE" : "FALSE",
        ]) else { return }
        await withCheckedContinuation { continuation in
            webView.configuration.websiteDataStore.httpCookieStore.setCookie(cookie) { continuation.resume() }
        }
    }

    func upload(_ payload: HealthSyncPayload) async throws -> [String: Any] {
        let context = try await resolveIngress()
        let endpoint = context.appURL.appendingPathComponent("api/v3/healthkit/sync")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("ingress_session=\(context.session)", forHTTPHeaderField: "Cookie")
        request.httpBody = try JSONEncoder().encode(payload)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw HomeAssistantClientError.supervisorRequestFailed("HealthKit-Upload")
        }
        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw HomeAssistantClientError.invalidResponse
        }
        return object
    }
}
