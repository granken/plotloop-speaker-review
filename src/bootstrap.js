(function () {
  "use strict";

  const isLocalRuntime =
    window.location.protocol === "file:" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "localhost";
  const forceDemo = new URLSearchParams(window.location.search).has("demo");
  window.PlotLoopSpeakerForceDemo = forceDemo;

  function loadScript(src) {
    return new Promise(function (resolve) {
      const script = document.createElement("script");
      script.src = src;
      script.onload = resolve;
      script.onerror = resolve;
      document.body.appendChild(script);
    });
  }

  const localData = isLocalRuntime && !forceDemo
    ? Promise.all([
        loadScript("./local-review-data.js?v=" + Date.now()),
        loadScript("./local-review-config.js?v=" + Date.now())
      ])
    : Promise.resolve();

  localData.then(function () {
    loadScript("./src/app.js?v=" + Date.now());
  });
})();
