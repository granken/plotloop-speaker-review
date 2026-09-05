import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
const packageData = JSON.parse(
  fs.readFileSync(new URL("../package.json", import.meta.url), "utf8")
);
const bootstrap = fs.readFileSync(
  new URL("../src/bootstrap.js", import.meta.url),
  "utf8"
);

test("continuous review controls sit near the summary in primary-first order", () => {
  const barStart = html.indexOf('class="review-command-bar"');
  const barEnd = html.indexOf("</div>", barStart);
  const bar = html.slice(barStart, barEnd);

  assert.ok(barStart >= 0);
  assert.ok(bar.indexOf('id="acceptNextButton"') < bar.indexOf('id="nextButton"'));
  assert.ok(bar.indexOf('id="nextButton"') < bar.indexOf('id="summaryToggleButton"'));
  assert.equal(html.includes('class="review-action-bar"'), false);
});

test("public page loads private data only through the local bootstrap", () => {
  assert.equal(html.includes('src="./local-review-data.js"'), false);
  assert.equal(html.includes('src="./local-review-config.js"'), false);
  assert.ok(
    html.includes(`href="./src/styles.css?v=${packageData.version}"`)
  );
  assert.ok(html.includes(`src="./src/core.js?v=${packageData.version}"`));
  assert.ok(
    html.includes(`src="./src/demo-data.js?v=${packageData.version}"`)
  );
  assert.ok(
    html.includes(`src="./src/bootstrap.js?v=${packageData.version}"`)
  );
  assert.ok(bootstrap.includes('window.location.hostname === "localhost"'));
  assert.ok(bootstrap.includes('URLSearchParams(window.location.search).has("demo")'));
});

test("forced demo mode cannot read or overwrite personal browser state", () => {
  const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");

  assert.ok(bootstrap.includes("window.PlotLoopSpeakerForceDemo = forceDemo"));
  assert.ok(app.includes("const restored = forceDemo ? false : restore()"));
  assert.match(app, /function save\(\) \{\s+if \(forceDemo\) \{\s+return;/);
  assert.ok(app.includes("!forceDemo &&"));
});

test("writeback controls are local-only and hidden by default", () => {
  const app = fs.readFileSync(new URL("../src/app.js", import.meta.url), "utf8");

  assert.match(html, /id="submitQuickButton"[^>]+hidden/);
  assert.match(html, /id="submitConfirmButton"[^>]+hidden/);
  assert.ok(app.includes('const CONFIRM_ENDPOINT = "/api/confirm"'));
  assert.ok(app.includes("button.hidden = !localSubmitEnabled"));
  assert.ok(app.includes("!forceDemo &&"));
  assert.equal(app.includes("http://127.0.0.1:4173/api/confirm"), false);
});
