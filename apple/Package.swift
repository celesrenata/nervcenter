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
        .testTarget(
            name: "NerveSharedTests",
            dependencies: [
                "NerveModels",
                "NerveAPI",
                "NervePersistence",
            ],
            path: "Tests"
        ),
    ]
)
