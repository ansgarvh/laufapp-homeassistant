import SwiftUI

@main
struct LaufappApp: App {
    @StateObject private var settings = AppSettings()
    @StateObject private var health = HealthKitService()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(settings)
                .environmentObject(health)
                .task { health.startIfConfigured() }
        }
    }
}
