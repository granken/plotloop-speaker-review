import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
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
  assert.ok(html.includes('src="./src/bootstrap.js?v=0.3.2"'));
  assert.ok(bootstrap.includes('window.location.hostname === "localhost"'));
  assert.ok(bootstrap.includes('URLSearchParams(window.location.search).has("demo")'));
});
