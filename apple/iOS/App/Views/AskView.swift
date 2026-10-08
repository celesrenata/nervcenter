import SwiftUI

import NerveApps
import NerveDesign

// MARK: - Ask tab

/// Ask tab — §65 "Ask the system a question".
public struct AskView: View {
    @ObservedObject public var store: PhoneDataStore
    @State private var question = ""
    @State private var answer: String?
    @State private var isAnswering = false
    @State private var errorMessage: String?

    public init(store: PhoneDataStore) {
        self.store = store
    }

    public var body: some View {
        ScrollView {
            VStack(spacing: Spacing.md) {
                // Question input
                TextField("Ask a question…", text: $question, axis: .vertical)
                    .textFieldStyle(platformTextFieldStyle)
                    .padding(.horizontal, Spacing.md)

                // Answer button
                Button("Ask") {
                    submit()
                }
                .disabled(question.isEmpty || isAnswering)
                .buttonStyle(.borderedProminent)
                .padding(.horizontal, Spacing.md)

                // Spinner while answering
                if isAnswering {
                    ProgressView()
                        .padding(.top, Spacing.sm)
                }

                // Answer text
                if let answer {
                    Text(answer)
                        .font(.body)
                        .foregroundStyle(.primary)
                        .padding(.horizontal, Spacing.md)
                        .padding(.vertical, Spacing.xs)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                // Error
                if let errorMessage {
                    Text(errorMessage)
                        .font(.caption)
                        .foregroundStyle(.red)
                        .padding(.horizontal, Spacing.md)
                }
            }
            .padding(.vertical, Spacing.sm)
        }
        .background(Color.phoneCanvas.ignoresSafeArea())
    }

    // MARK: - Submit

    private func submit() {
        guard !question.isEmpty else { return }
        errorMessage = nil
        isAnswering = true
        answer = nil

        // The AskView is a pure UI view; it uses the fetch service when
        // provided via the environment. For now, it shows a placeholder.
        Task {
            // TODO: wire to PhoneFetchService.ask(question)
            try? await Task.sleep(for: .seconds(1))
            await MainActor.run {
                isAnswering = false
                answer = "The system has not yet responded. Please check back later."
            }
        }
    }
}

// MARK: - Platform helpers

/// A platform-safe text field style: `.roundedBorder` is unavailable on
/// watchOS, so fall back to `.plain` there (the watch does not host this view
/// directly; the macOS host build exercises the same code path).
private var platformTextFieldStyle: some TextFieldStyle {
    #if os(watchOS)
    PlainTextFieldStyle()
    #else
    RoundedBorderTextFieldStyle()
    #endif
}
