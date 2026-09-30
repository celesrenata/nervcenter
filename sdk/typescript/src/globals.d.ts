/**
 * Minimal ambient declarations for the Node.js globals this SDK uses.
 *
 * The SDK is built with `lib: ["ES2022", "DOM"]` (fetch/Response/AbortSignal/
 * URL come from the DOM lib) and NO `@types/node` package — Node built-ins
 * only, zero npm dependencies.
 */

declare const process: {
  argv: string[];
  env: Record<string, string | undefined>;
  exit(code?: number): never;
};

declare module "node:crypto" {
  /** Generate a random UUID (v4). */
  export function randomUUID(): string;
}
