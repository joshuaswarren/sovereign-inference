import { render, screen } from "@testing-library/react";
import { type Mock, beforeEach, describe, expect, test, vi } from "vitest";

import { App } from "./App";
import type { ConfigState } from "./onboarding/api";

// Stub the two branches so the gate logic is what's under test: if the dashboard
// stub is absent, its data panels never mounted.
vi.mock("./Dashboard", () => ({ Dashboard: () => <div>DASHBOARD</div> }));
vi.mock("./onboarding/Onboarding", () => ({ Onboarding: () => <div>ONBOARDING</div> }));
vi.mock("./onboarding/api", () => ({ getConfig: vi.fn() }));

import { getConfig } from "./onboarding/api";

const mockConfig = (overrides: Partial<ConfigState>): ConfigState => ({
  onboarding_complete: false,
  providers: [],
  directories: [],
  models: [],
  local_use: null,
  warnings: [],
  ...overrides,
});

describe("App gate", () => {
  beforeEach(() => vi.clearAllMocks());

  test("shows onboarding (never the dashboard) when not yet onboarded", async () => {
    (getConfig as Mock).mockResolvedValue(mockConfig({ onboarding_complete: false }));
    render(<App />);
    expect(await screen.findByText("ONBOARDING")).toBeInTheDocument();
    expect(screen.queryByText("DASHBOARD")).not.toBeInTheDocument();
  });

  test("shows the dashboard once onboarding is complete", async () => {
    (getConfig as Mock).mockResolvedValue(mockConfig({ onboarding_complete: true }));
    render(<App />);
    expect(await screen.findByText("DASHBOARD")).toBeInTheDocument();
    expect(screen.queryByText("ONBOARDING")).not.toBeInTheDocument();
  });

  test("falls back to the dashboard if the app server is unreachable", async () => {
    (getConfig as Mock).mockRejectedValue(new Error("no app server"));
    render(<App />);
    expect(await screen.findByText("DASHBOARD")).toBeInTheDocument();
  });
});
