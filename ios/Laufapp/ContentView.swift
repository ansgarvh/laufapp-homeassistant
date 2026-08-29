import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var settings: AppSettings
    @EnvironmentObject private var health: HealthKitService
    @State private var tokenInput = ""
    @State private var errorText: String?
    @State private var showSetup = false

    private var configured: Bool {
        settings.hasToken && URL(string: settings.homeAssistantURL.trimmingCharacters(in: .whitespacesAndNewlines)) != nil
    }

    var body: some View {
        Group {
            if configured, !showSetup,
               let url = URL(string: settings.homeAssistantURL.trimmingCharacters(in: .whitespacesAndNewlines)),
               let token = settings.token() {
                ZStack(alignment: .topTrailing) {
                    LaufappWebView(baseURL: url, token: token) { errorText = $0 }
                        .ignoresSafeArea()
                    Button {
                        showSetup = true
                    } label: {
                        Image(systemName: "gearshape.fill")
                            .font(.system(size: 14, weight: .semibold))
                            .padding(10)
                            .background(.ultraThinMaterial, in: Circle())
                    }
                    .padding(.top, 8)
                    .padding(.trailing, 10)
                    .accessibilityLabel("iOS-Verbindung einstellen")
                }
            } else {
                setupView
            }
        }
        .alert("Laufapp", isPresented: Binding(get: { errorText != nil }, set: { if !$0 { errorText = nil } })) {
            Button("OK", role: .cancel) { errorText = nil }
        } message: { Text(errorText ?? "") }
    }

    private var setupView: some View {
        NavigationStack {
            Form {
                Section("Home Assistant") {
                    TextField("https://…", text: $settings.homeAssistantURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                    SecureField(settings.hasToken ? "Token gespeichert – nur zum Ersetzen tippen" : "Long-Lived Access Token", text: $tokenInput)
                        .textInputAutocapitalization(.never)
                    Text("Der Token wird ausschließlich im iOS-Keychain gespeichert. Er wird verwendet, um eine kurzlebige Home-Assistant-Ingress-Sitzung für Laufapp zu erzeugen; Port 8099 bleibt geschlossen.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                Section("Apple Health") {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(health.status)
                            if let date = health.lastSync {
                                Text("Letzter Sync: \(date.formatted(date: .abbreviated, time: .shortened))")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                    }
                    Button("HealthKit verbinden und testen") {
                        Task {
                            do { try await health.requestAuthorizationAndStart() }
                            catch { errorText = error.localizedDescription }
                        }
                    }
                    Button("Jetzt synchronisieren") {
                        Task {
                            do { try await health.syncNow() }
                            catch { errorText = error.localizedDescription }
                        }
                    }
                    .disabled(!configured)
                }
                Section {
                    Button("Verbindung speichern") {
                        do {
                            let trimmed = tokenInput.trimmingCharacters(in: .whitespacesAndNewlines)
                            if !trimmed.isEmpty { try settings.saveToken(trimmed) }
                            guard URL(string: settings.homeAssistantURL.trimmingCharacters(in: .whitespacesAndNewlines)) != nil, settings.hasToken else {
                                throw NSError(domain: "Laufapp", code: 2, userInfo: [NSLocalizedDescriptionKey: "Bitte Home-Assistant-URL und Token vollständig eintragen."])
                            }
                            tokenInput = ""
                            showSetup = false
                            Task {
                                do { try await health.requestAuthorizationAndStart() }
                                catch { errorText = error.localizedDescription }
                            }
                        } catch { errorText = error.localizedDescription }
                    }
                    .buttonStyle(.borderedProminent)
                    if configured {
                        Button("Zur Laufapp", role: .cancel) { showSetup = false }
                        Button("Verbindung zurücksetzen", role: .destructive) {
                            settings.reset(); tokenInput = ""; showSetup = false
                        }
                    }
                }
            }
            .navigationTitle("Laufapp einrichten")
        }
    }
}
