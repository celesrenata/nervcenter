import XCTest
import NerveApps
import NerveModels

final class NerveAppsTests: XCTestCase {
    func testAskAnswerProvenance() {
        let evidence = [
            Evidence(
                id: "1",
                sourceType: .toolResult,
                sourceRef: "test-tool",
                content: "Test evidence",
                capturedAt: Date(),
                trust: 0.9
            )
        ]
        let answer = AskAnswer(
            answer: "Test answer",
            evidence: evidence,
            traceID: "test-trace"
        )
        
        XCTAssertEqual(answer.provenanceSummary, "1 evidence record · trace test-tra…")
        XCTAssertTrue(answer.hasInspectableEvidence)
    }

    func testEvidenceCitation() {
        let evidence = Evidence(
            id: "1",
            sourceType: .webPage,
            sourceRef: "https://example.com",
            content: "Test content",
            capturedAt: Date(),
            trust: 0.8
        )
        let citation = EvidenceCitation(evidence: evidence)
        
        XCTAssertEqual(citation.sourceLabel, "Web page")
    }
}