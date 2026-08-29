import Foundation

struct RunSamplePayload: Codable {
    let id: String
    let type: String
    let at: String
    let value: Double
    let unit: String
}

struct RoutePointPayload: Codable {
    let at: String
    let lat: Double
    let lon: Double
    let elevation_m: Double?
}

struct WorkoutPayload: Codable {
    let id: String
    let activity_type: String
    let start_at: String
    let end_at: String
    let distance_km: Double
    let duration_s: Double
    let avg_hr: Double?
    let elevation_m: Double?
    let calories: Double?
    let samples: [RunSamplePayload]
    let route: [RoutePointPayload]
}

struct HealthMetricPayload: Codable {
    let id: String
    let type: String
    let start_at: String
    let end_at: String?
    let value: Double
    let unit: String
}

struct HealthSyncPayload: Codable {
    let schema_version = 1
    let source = "laufapp_ios"
    let device_id: String
    let workouts: [WorkoutPayload]
    let metrics: [HealthMetricPayload]
}

struct IngressContext {
    let appURL: URL
    let session: String
    let cookieDomain: String
}

extension ISO8601DateFormatter {
    static let laufapp: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
}
