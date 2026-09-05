import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const core = require("../src/core.js");

test("parseReviewPayload de-duplicates current and batch meetings", () => {
  const meeting = {
    meeting: "周会",
    date: "2026-01-01",
    time: "09:00:00",
    file_stem: "weekly",
    mappings: []
  };
  const result = core.parseReviewPayload({
    type: "speaker-review",
    current: meeting,
    batch: [meeting]
  });
  assert.equal(result.meetings.length, 1);
});

test("changing a suggested name forces replace and high confidence", () => {
  const mapping = core.normalizeMapping({
    label: "Speaker 0",
    name: "角色A",
    action: "keep",
    confidence: "low"
  });
  const changed = core.applyNameDecision(mapping, "林青");
  assert.equal(changed.action, "replace");
  assert.equal(changed.confidence, "high");
});

test("restoring the suggested name restores original action and confidence", () => {
  const mapping = core.normalizeMapping({
    label: "Speaker 0",
    name: "角色A",
    action: "keep",
    confidence: "low"
  });
  const changed = core.applyNameDecision(mapping, "林青");
  const restored = core.applyNameDecision(changed, "角色A");
  assert.equal(restored.action, "keep");
  assert.equal(restored.confidence, "low");
});

test("serializeMeeting removes internal suggestion metadata", () => {
  const meeting = core.normalizeMeeting({
    meeting: "周会",
    mappings: [{ label: "Speaker 0", name: "林青" }]
  });
  const output = core.serializeMeeting(meeting);
  assert.equal("_suggestedName" in output.mappings[0], false);
});

test("parseRoster accepts commas, punctuation and line breaks", () => {
  assert.deepEqual(core.parseRoster("林青、顾川\n程澄，林青"), [
    "林青",
    "顾川",
    "程澄"
  ]);
});

test("mergeRoster keeps existing order and appends new unique names", () => {
  assert.deepEqual(core.mergeRoster(["林青", "顾川"], ["顾川", "程澄"]), [
    "林青",
    "顾川",
    "程澄"
  ]);
});
