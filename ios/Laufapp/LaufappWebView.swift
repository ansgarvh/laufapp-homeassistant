import SwiftUI
import WebKit

struct LaufappWebView: UIViewRepresentable {
    let baseURL: URL
    let token: String
    let onError: (String) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onError: onError) }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        context.coordinator.load(webView: webView, baseURL: baseURL, token: token)
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) { }

    final class Coordinator: NSObject, WKNavigationDelegate {
        private var didLoad = false
        private let onError: (String) -> Void
        init(onError: @escaping (String) -> Void) { self.onError = onError }

        func load(webView: WKWebView, baseURL: URL, token: String) {
            guard !didLoad else { return }
            didLoad = true
            Task {
                do {
                    let client = HomeAssistantClient(baseURL: baseURL, token: token)
                    let context = try await client.resolveIngress()
                    await client.installIngressCookie(context, into: webView)
                    await MainActor.run { webView.load(URLRequest(url: context.appURL)) }
                } catch {
                    await MainActor.run { self.onError(error.localizedDescription) }
                }
            }
        }
    }
}
