import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type Mock, beforeEach, expect, test, vi } from "vitest";

import { type ConfigState, type RuntimeStatus } from "./api";
import { Onboarding } from "./Onboarding";

vi.mock("./api", () => ({
  getRuntimes: vi.fn(),
  startLocalUse: vi.fn(),
  addDirectory: vi.fn(),
  addProvider: vi.fn(),
  completeOnboarding: vi.fn(),
  testChat: vi.fn(),
}));

import { completeOnboarding, getRuntimes, startLocalUse } from "./api";

const baseConfig = (over: Partial<ConfigState> = {}): ConfigState => ({
  onboarding_complete: false,
  providers: [],
  directories: [],
  models: [],
  local_use: null,
  warnings: [],
  ...over,
});

const runtime = (over: Partial<RuntimeStatus> = {}): RuntimeStatus => ({
  name: "ollama",
  available: true,
  models: ["llama3.1:8b"],
  ...over,
});

beforeEach(() => vi.clearAllMocks());

test("offers a detected local model and fronts it on click", async () => {
  (getRuntimes as Mock).mockResolvedValue([runtime()]);
  (startLocalUse as Mock).mockResolvedValue(baseConfig({ models: ["llama3.1:8b"] }));

  render(<Onboarding initialConfig={baseConfig()} onComplete={() => {}} />);

  const useButton = await screen.findByRole("button", { name: /Use llama3\.1:8b/ });
  await userEvent.click(useButton);

  expect(startLocalUse).toHaveBeenCalledWith("ollama", "llama3.1:8b");
  // once a model is available, the ready section + test chat appear
  await waitFor(() => expect(screen.getByRole("button", { name: /Try it/ })).toBeInTheDocument());
});

test("guides the user when no local runtime is available", async () => {
  (getRuntimes as Mock).mockResolvedValue([runtime({ available: false, models: [] })]);
  render(<Onboarding initialConfig={baseConfig()} onComplete={() => {}} />);
  expect(await screen.findByText(/No local runtime detected/)).toBeInTheDocument();
});

test("finishing setup completes onboarding", async () => {
  (getRuntimes as Mock).mockResolvedValue([]);
  (completeOnboarding as Mock).mockResolvedValue(baseConfig({ onboarding_complete: true }));
  const onComplete = vi.fn();

  render(<Onboarding initialConfig={baseConfig()} onComplete={onComplete} />);
  await userEvent.click(await screen.findByRole("button", { name: /Finish setup/ }));

  await waitFor(() => expect(completeOnboarding).toHaveBeenCalled());
  expect(onComplete).toHaveBeenCalled();
});
