(function () {
  "use strict";

  var isLocalRuntime =
    window.location.protocol === "file:" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "localhost";
  var forceDemo = new URLSearchParams(window.location.search).has("demo");
  window.PlotLoopSpeakerForceDemo = forceDemo;

  function loadScript(src) {
    return new Promise(function (resolve) {
      var script = document.createElement("script");
      script.src = src;
      script.onload = resolve;
      script.onerror = resolve;
      document.body.appendChild(script);
    });
  }

  var localData = isLocalRuntime && !forceDemo
    ? Promise.all([
        loadScript("./local-review-data.js"),
        loadScript("./local-review-config.js")
      ])
    : Promise.resolve();

  localData.then(function () {
    loadScript("./src/app.js?v=0.3.3");
  });
})();
