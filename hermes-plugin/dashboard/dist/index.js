(function() {
  /* PiHermes dashboard tab — status + controls for voice pipeline */

  var SDK = window.__HERMES_PLUGIN_SDK__;
  var React = SDK.React;
  var useState = React.useState;
  var useEffect = React.useEffect;
  var Card = SDK.components.Card;
  var CardHeader = SDK.components.CardHeader;
  var CardTitle = SDK.components.CardTitle;
  var CardContent = SDK.components.CardContent;
  var Button = SDK.components.Button;
  var Badge = SDK.components.Badge;

  function PiHermesPage() {
    var _useState = useState("loading");  // loading | running | stopped | error
    var status = _useState[0];
    var setStatus = _useState[1];

    var _useStateLog = useState("");
    var log = _useStateLog[0];
    var setLog = _useStateLog[1];

    function fetchStatus() {
      fetch("/api/plugins/pihermes/status")
        .then(function(r) { return r.json(); })
        .then(function(data) {
          setStatus(data.pipeline_running ? "running" : "stopped");
          setLog(data.recent_log || "");
        })
        .catch(function() { setStatus("error"); });
    }

    useEffect(function() {
      fetchStatus();
      var interval = setInterval(fetchStatus, 5000);
      return function() { clearInterval(interval); };
    }, []);

    function restartPipeline() {
      setStatus("loading");
      fetch("/api/plugins/pihermes/restart", { method: "POST" })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.success) {
            setTimeout(fetchStatus, 2000);
          } else {
            setStatus("error");
            setLog(data.error || "Restart failed");
          }
        })
        .catch(function() { setStatus("error"); });
    }

    var statusBadge;
    if (status === "running") statusBadge = React.createElement(Badge, { variant: "success" }, "Running");
    else if (status === "stopped") statusBadge = React.createElement(Badge, { variant: "warning" }, "Stopped");
    else if (status === "error") statusBadge = React.createElement(Badge, { variant: "destructive" }, "Error");
    else statusBadge = React.createElement(Badge, { variant: "secondary" }, "Loading...");

    return React.createElement("div", null,
      // Status card
      React.createElement(Card, null,
        React.createElement(CardHeader, null,
          React.createElement(CardTitle, null, "PiHermes Voice Pipeline")
        ),
        React.createElement(CardContent, null,
          React.createElement("div", { style: { display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" } },
            React.createElement("span", { className: "text-sm text-muted-foreground" }, "Status:"),
            statusBadge
          ),
          React.createElement(Button, {
            onClick: restartPipeline,
            disabled: status === "loading"
          }, "Restart Pipeline"),
          log ? React.createElement("pre", {
            style: {
              marginTop: "12px",
              padding: "8px",
              background: "var(--card-midground, rgba(0,0,0,0.3))",
              borderRadius: "6px",
              fontSize: "11px",
              fontFamily: "monospace",
              maxHeight: "200px",
              overflow: "auto",
              whiteSpace: "pre-wrap"
            }
          }, log) : null
        )
      ),

      // Quick info card
      React.createElement(Card, { style: { marginTop: "16px" } },
        React.createElement(CardHeader, null,
          React.createElement(CardTitle, null, "Quick Info")
        ),
        React.createElement(CardContent, null,
          React.createElement("ul", { className: "text-sm text-muted-foreground", style: { lineHeight: "1.8" } },
            React.createElement("li", null, "Wake word: \"Hey Bob\""),
            React.createElement("li", null, "STT: Cloud (configurable) + offline fallback"),
            React.createElement("li", null, "TTS: Piper (on-device, female voice)"),
            React.createElement("li", null, "Cycle time: ~10s from wake to response"),
            React.createElement("li", null, "Service: pihermes-voice (systemd)")
          )
        )
      )
    );
  }

  window.__HERMES_PLUGINS__.register("pihermes", PiHermesPage);
})();
