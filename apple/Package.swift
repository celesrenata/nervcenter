// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NerveCenter",
    platforms: [
        .macOS(.v14),
        .iOS(.v17),
        .watchOS(.v10),
        .macCatalyst(.v17),
    ],
    products: [
        .library(name: "NerveShared", targets: [
            "NerveModels",
            "NerveAPI",
            "NerveAuth",
            "NervePersistence",
            "NerveRealtime",
            "NerveDesign",
        ]),
        // Cross-platform app domain logic shared by the iPhone, Watch, and
        // Widget targets (T311/T312).
        .library(name: "NerveApps", targets: ["NerveApps"]),
    ],
    targets: [
        .target(
            name: "NerveModels",
            dependencies: [],
            path: "Shared/Sources/NerveModels",
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency")
            ]
        ),
        .target(
            name: "NerveAPI",
            dependencies: ["NerveModels"],
            path: "Shared/Sources/NerveAPI"
        ),
        .target(
            name: "NerveAuth",
            dependencies: ["NerveModels"],
            path: "Shared/Sources/NerveAuth"
        ),
        .target(
            name: "NervePersistence",
            dependencies: ["NerveModels"],
            path: "Shared/Sources/NervePersistence"
        ),
        .target(
            name: "NerveRealtime",
            dependencies: ["NerveModels"],
            path: "Shared/Sources/NerveRealtime"
        ),
        .target(
            name: "NerveDesign",
            path: "Shared/Sources/NerveDesign"
        ),
        // App-domain logic (T311/T312): platform-free models, contracts,
        // policies, and caches shared by the three app targets.
        .target(
            name: "NerveApps",
            dependencies: [
                "NerveModels",
                "NerveAPI",
                "NerveAuth",
                "NervePersistence",
                "NerveRealtime",
                "NerveDesign",
            ],
            path: "Shared/Sources/NerveApps"
        ),
        // iPhone app target (T311). App-level wiring ships via `project.yml`
        // (XcodeGen) — the target here exists so the whole package builds
        // and cross-compiles (iOS 17 simulator triple) with no extra tooling.
        .target(
            name: "NervePhone",
            dependencies: [
                "NerveModels",
                "NerveAPI",
                "NerveAuth",
                "NervePersistence",
                "NerveRealtime",
                "NerveDesign",
                "NerveApps",
            ],
            path: "iOS/App"
        ),
        // Watch app target (T312). Same notes as NervePhone.
        .target(
            name: "NerveWatch",
            dependencies: [
                "NerveModels",
                "NerveAPI",
                "NerveAuth",
                "NervePersistence",
                "NerveDesign",
                "NerveApps",
            ],
            path: "Watch"
        ),
        // Widget extension target (T312). iOS/visionOS/macCatalyst only.
                // watchOS/macOS host builds skip this target; cross-compile for them
                // is skipped because WidgetKit families are unavailable on watchOS.
                .target(
                    name: "NerveWidgets",
                    dependencies: [
                        "NerveModels",
                        "NerveAPI",
                        "NerveAuth",
                        "NervePersistence",
                        "NerveDesign",
                        "NerveApps",
                    ],
                    path: "Widgets"
                ),
        // Cross-platform unit tests for the app domain logic.
        .testTarget(
            name: "NerveAppsTests",
            dependencies: [
                "NerveApps",
            ],
            path: "Tests/NerveAppsTests"
        ),
        // Pre-existing shared-SDK test suite (kept; the INT-apple patch
        // initially dropped this target, orphaning the files below it).
        .testTarget(
            name: "NerveSharedTests",
            dependencies: [
                "NerveModels",
                "NerveAPI",
                "NervePersistence",
            ],
            path: "Tests/NerveSharedTests"
        ),
    ]
)
