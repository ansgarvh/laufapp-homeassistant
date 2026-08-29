import Foundation
import HealthKit
import CoreLocation
import Combine

final class HealthKitService: ObservableObject {
    @Published private(set) var status = "HealthKit noch nicht verbunden"
    @Published private(set) var lastSync: Date?
    @Published private(set) var authorized = false

    private let store = HKHealthStore()
    private var observerQuery: HKObserverQuery?
    private let syncDateKey = "healthKitLastSuccessfulSync"
    private let deviceIDKey = "healthKitDeviceID"

    private var workoutType: HKWorkoutType { HKObjectType.workoutType() }

    private var readTypes: Set<HKObjectType> {
        var result: Set<HKObjectType> = [workoutType, HKSeriesType.workoutRoute()]
        let ids: [HKQuantityTypeIdentifier] = [
            .distanceWalkingRunning, .heartRate, .runningSpeed, .runningPower,
            .runningStrideLength, .runningVerticalOscillation, .runningGroundContactTime,
            .stepCount, .restingHeartRate, .heartRateVariabilitySDNN, .bodyMass, .vo2Max,
        ]
        for id in ids { if let type = HKObjectType.quantityType(forIdentifier: id) { result.insert(type) } }
        if let sleep = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) { result.insert(sleep) }
        return result
    }

    func requestAuthorizationAndStart() async throws {
        guard HKHealthStore.isHealthDataAvailable() else { throw NSError(domain: "LaufappHealthKit", code: 1) }
        try await store.requestAuthorization(toShare: [], read: readTypes)
        try await store.enableBackgroundDelivery(for: workoutType, frequency: .immediate)
        await MainActor.run {
            authorized = true
            status = "HealthKit verbunden"
        }
        installObserver()
        try await syncNow()
    }

    func startIfConfigured() {
        guard configuredClient() != nil else { return }
        installObserver()
    }

    private func installObserver() {
        guard observerQuery == nil else { return }
        let query = HKObserverQuery(sampleType: workoutType, predicate: nil) { [weak self] _, completion, error in
            guard let self else { completion(); return }
            if error != nil { completion(); return }
            Task {
                do { try await self.syncRecentRuns(forceOverlap: false) } catch { }
                completion()
            }
        }
        observerQuery = query
        store.execute(query)
    }

    func syncNow() async throws {
        try await syncRecentRuns(forceOverlap: true)
    }

    private func configuredClient() -> HomeAssistantClient? {
        guard let text = UserDefaults.standard.string(forKey: "homeAssistantURL"),
              let url = URL(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              let token = KeychainStore.get("homeAssistantToken"), !token.isEmpty else { return nil }
        return HomeAssistantClient(baseURL: url, token: token)
    }

    private func deviceID() -> String {
        if let value = UserDefaults.standard.string(forKey: deviceIDKey) { return value }
        let value = UUID().uuidString
        UserDefaults.standard.set(value, forKey: deviceIDKey)
        return value
    }

    private func syncRecentRuns(forceOverlap: Bool) async throws {
        guard let client = configuredClient() else { return }
        let stored = UserDefaults.standard.object(forKey: syncDateKey) as? Date
        let defaultStart = Calendar.current.date(byAdding: .day, value: -7, to: Date())!
        let start = forceOverlap ? (stored.map { min($0.addingTimeInterval(-6 * 3600), defaultStart) } ?? defaultStart) : (stored?.addingTimeInterval(-6 * 3600) ?? defaultStart)
        let workouts = try await runningWorkouts(since: start)
        let metrics = try await generalMetrics(since: start)

        if workouts.isEmpty {
            if !metrics.isEmpty {
                _ = try await client.upload(HealthSyncPayload(device_id: deviceID(), workouts: [], metrics: metrics))
            }
            await MainActor.run { status = "HealthKit aktuell"; lastSync = Date(); authorized = true }
            return
        }

        var newest = stored ?? start
        for workout in workouts {
            let payloadWorkout = try await buildWorkout(workout)
            let payloadMetrics = workout == workouts.last ? metrics : []
            _ = try await client.upload(HealthSyncPayload(device_id: deviceID(), workouts: [payloadWorkout], metrics: payloadMetrics))
            newest = max(newest, workout.endDate)
        }
        UserDefaults.standard.set(newest, forKey: syncDateKey)
        await MainActor.run {
            status = "Automatisch synchronisiert"
            lastSync = Date()
            authorized = true
        }
    }

    private func runningWorkouts(since: Date) async throws -> [HKWorkout] {
        let predicate = HKQuery.predicateForSamples(withStart: since, end: nil, options: .strictEndDate)
        return try await withCheckedThrowingContinuation { continuation in
            let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
            let query = HKSampleQuery(sampleType: workoutType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { _, samples, error in
                if let error { continuation.resume(throwing: error); return }
                let runs = (samples as? [HKWorkout] ?? []).filter { $0.workoutActivityType == .running }
                continuation.resume(returning: runs)
            }
            store.execute(query)
        }
    }

    private func quantitySamples(_ identifier: HKQuantityTypeIdentifier, workout: HKWorkout) async throws -> [HKQuantitySample] {
        guard let type = HKObjectType.quantityType(forIdentifier: identifier) else { return [] }
        let predicate = HKQuery.predicateForSamples(withStart: workout.startDate, end: workout.endDate, options: [.strictStartDate, .strictEndDate])
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: type, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, error in
                if let error { continuation.resume(throwing: error); return }
                continuation.resume(returning: samples as? [HKQuantitySample] ?? [])
            }
            store.execute(query)
        }
    }

    private func buildWorkout(_ workout: HKWorkout) async throws -> WorkoutPayload {
        let specs: [(HKQuantityTypeIdentifier, String)] = [
            (.distanceWalkingRunning, "distance"), (.heartRate, "heart_rate"), (.runningSpeed, "running_speed"),
            (.runningPower, "running_power"), (.runningStrideLength, "stride_length"),
            (.runningVerticalOscillation, "vertical_oscillation"), (.runningGroundContactTime, "ground_contact_time"),
            (.stepCount, "cadence"),
        ]
        var allSamples: [RunSamplePayload] = []
        var heartRates: [Double] = []
        for (identifier, name) in specs {
            let samples = try await quantitySamples(identifier, workout: workout)
            for sample in samples {
                guard let converted = convert(sample, identifier: identifier) else { continue }
                allSamples.append(RunSamplePayload(id: sample.uuid.uuidString, type: name, at: ISO8601DateFormatter.laufapp.string(from: sample.startDate), value: converted.0, unit: converted.1))
                if identifier == .heartRate { heartRates.append(converted.0) }
            }
        }
        allSamples.sort { $0.at < $1.at }
        let route = try await routePoints(workout)
        let distance = workout.totalDistance?.doubleValue(for: HKUnit.meterUnit(with: .kilo)) ?? distanceFromSamples(allSamples)
        let avgHR = heartRates.isEmpty ? nil : heartRates.reduce(0, +) / Double(heartRates.count)
        let calories = workout.totalEnergyBurned?.doubleValue(for: .kilocalorie())
        let elevation = positiveElevationGain(route)
        return WorkoutPayload(
            id: workout.uuid.uuidString,
            activity_type: "running",
            start_at: ISO8601DateFormatter.laufapp.string(from: workout.startDate),
            end_at: ISO8601DateFormatter.laufapp.string(from: workout.endDate),
            distance_km: distance,
            duration_s: workout.duration,
            avg_hr: avgHR,
            elevation_m: elevation,
            calories: calories,
            samples: allSamples,
            route: route
        )
    }

    private func convert(_ sample: HKQuantitySample, identifier: HKQuantityTypeIdentifier) -> (Double, String)? {
        switch identifier {
        case .distanceWalkingRunning:
            return (sample.quantity.doubleValue(for: HKUnit.meterUnit(with: .kilo)), "km")
        case .heartRate:
            return (sample.quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute())), "count/min")
        case .runningSpeed:
            return (sample.quantity.doubleValue(for: HKUnit.meter().unitDivided(by: .second())), "m/s")
        case .runningPower:
            return (sample.quantity.doubleValue(for: .watt()), "W")
        case .runningStrideLength:
            return (sample.quantity.doubleValue(for: .meter()), "m")
        case .runningVerticalOscillation:
            return (sample.quantity.doubleValue(for: .meter()) * 100.0, "cm")
        case .runningGroundContactTime:
            return (sample.quantity.doubleValue(for: .second()) * 1000.0, "ms")
        case .stepCount:
            let seconds = sample.endDate.timeIntervalSince(sample.startDate)
            guard seconds > 0 else { return nil }
            return (sample.quantity.doubleValue(for: .count()) / seconds * 60.0, "spm")
        default: return nil
        }
    }

    private func distanceFromSamples(_ samples: [RunSamplePayload]) -> Double {
        samples.filter { $0.type == "distance" }.reduce(0) { $0 + $1.value }
    }

    private func routePoints(_ workout: HKWorkout) async throws -> [RoutePointPayload] {
        let routeType = HKSeriesType.workoutRoute()
        let predicate = HKQuery.predicateForObjects(from: workout)
        let routes: [HKWorkoutRoute] = try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: routeType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, error in
                if let error { continuation.resume(throwing: error); return }
                continuation.resume(returning: samples as? [HKWorkoutRoute] ?? [])
            }
            store.execute(query)
        }
        var locations: [CLLocation] = []
        for route in routes {
            let chunk = try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<[CLLocation], Error>) in
                var collected: [CLLocation] = []
                let query = HKWorkoutRouteQuery(route: route) { _, values, done, error in
                    if let error { continuation.resume(throwing: error); return }
                    collected.append(contentsOf: values ?? [])
                    if done { continuation.resume(returning: collected) }
                }
                store.execute(query)
            }
            locations.append(contentsOf: chunk)
        }
        locations.sort { $0.timestamp < $1.timestamp }
        return locations.map { RoutePointPayload(at: ISO8601DateFormatter.laufapp.string(from: $0.timestamp), lat: $0.coordinate.latitude, lon: $0.coordinate.longitude, elevation_m: $0.altitude) }
    }

    private func positiveElevationGain(_ points: [RoutePointPayload]) -> Double? {
        guard points.count > 1 else { return nil }
        var total = 0.0
        var previous = points[0].elevation_m
        for point in points.dropFirst() {
            if let p = previous, let current = point.elevation_m, current > p { total += current - p }
            previous = point.elevation_m ?? previous
        }
        return total
    }

    private func generalMetrics(since: Date) async throws -> [HealthMetricPayload] {
        var output: [HealthMetricPayload] = []
        let specs: [(HKQuantityTypeIdentifier, String, HKUnit)] = [
            (.restingHeartRate, "resting_hr", HKUnit.count().unitDivided(by: .minute())),
            (.heartRateVariabilitySDNN, "hrv_sdnn", .secondUnit(with: .milli)),
            (.bodyMass, "body_mass", .gramUnit(with: .kilo)),
            (.vo2Max, "vo2max", HKUnit(from: "ml/kg*min")),
        ]
        for (identifier, name, unit) in specs {
            guard let type = HKObjectType.quantityType(forIdentifier: identifier) else { continue }
            let predicate = HKQuery.predicateForSamples(withStart: since, end: nil, options: .strictEndDate)
            let samples: [HKQuantitySample] = try await withCheckedThrowingContinuation { continuation in
                let q = HKSampleQuery(sampleType: type, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, values, error in
                    if let error { continuation.resume(throwing: error); return }
                    continuation.resume(returning: values as? [HKQuantitySample] ?? [])
                }
                store.execute(q)
            }
            output.append(contentsOf: samples.map { HealthMetricPayload(id: $0.uuid.uuidString, type: name, start_at: ISO8601DateFormatter.laufapp.string(from: $0.startDate), end_at: ISO8601DateFormatter.laufapp.string(from: $0.endDate), value: $0.quantity.doubleValue(for: unit), unit: name == "body_mass" ? "kg" : name == "hrv_sdnn" ? "ms" : name == "vo2max" ? "mL/min·kg" : "count/min") })
        }
        output.append(contentsOf: try await sleepMetrics(since: since))
        return output
    }

    private func sleepMetrics(since: Date) async throws -> [HealthMetricPayload] {
        guard let type = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return [] }
        let predicate = HKQuery.predicateForSamples(withStart: since, end: nil, options: .strictEndDate)
        let samples: [HKCategorySample] = try await withCheckedThrowingContinuation { continuation in
            let q = HKSampleQuery(sampleType: type, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, values, error in
                if let error { continuation.resume(throwing: error); return }
                continuation.resume(returning: values as? [HKCategorySample] ?? [])
            }
            store.execute(q)
        }
        let asleepValues: Set<Int> = [
            HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue,
            HKCategoryValueSleepAnalysis.asleepCore.rawValue,
            HKCategoryValueSleepAnalysis.asleepDeep.rawValue,
            HKCategoryValueSleepAnalysis.asleepREM.rawValue,
        ]
        let asleep = samples.filter { asleepValues.contains($0.value) }
        let grouped = Dictionary(grouping: asleep) { Calendar.current.startOfDay(for: $0.endDate) }
        return grouped.compactMap { day, values in
            let intervals = values.map { DateInterval(start: $0.startDate, end: $0.endDate) }.sorted { $0.start < $1.start }
            guard !intervals.isEmpty else { return nil }
            var merged: [DateInterval] = []
            for interval in intervals {
                if let last = merged.last, interval.start <= last.end {
                    merged[merged.count - 1] = DateInterval(start: last.start, end: max(last.end, interval.end))
                } else { merged.append(interval) }
            }
            let hours = merged.reduce(0.0) { $0 + $1.duration } / 3600.0
            let key = ISO8601DateFormatter.laufapp.string(from: day).prefix(10)
            return HealthMetricPayload(id: "apple_health_sleep_\(key)", type: "sleep_hours", start_at: ISO8601DateFormatter.laufapp.string(from: merged.first!.start), end_at: ISO8601DateFormatter.laufapp.string(from: merged.last!.end), value: hours, unit: "h")
        }
    }
}
