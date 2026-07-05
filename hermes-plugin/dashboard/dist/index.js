(function() {
  /* PiHermes dashboard tab — status + config for voice pipeline */

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
    var _status = useState("loading");  // loading | running | stopped | error
    var status = _status[0];
    var setStatus = _status[1];
    var _log = useState("");
    var log = _log[0];
    var setLog = _log[1];
    var _config = useState(null);
    var config = _config[0];
    var setConfig = _config[1];
    var _saveMsg = useState("");
    var saveMsg = _saveMsg[0];
    var setSaveMsg = _saveMsg[1];
    var _uptime = useState("");
    var uptime = _uptime[0];
    var setUptime = _uptime[1];

    function fetchStatus() {
      fetch("/api/plugins/pihermes/status")
        .then(function(r) { return r.json(); })
        .then(function(data) {
          setStatus(data.pipeline_running ? "running" : "stopped");
          setLog(data.recent_log || "");
          setUptime(data.uptime || "");
        })
        .catch(function() { setStatus("error"); });
    }

    function fetchConfig() {
      fetch("/api/plugins/pihermes/config")
        .then(function(r) { return r.json(); })
        .then(function(data) { setConfig(data); })
        .catch(function() {});
    }

    useEffect(function() {
      fetchStatus();
      fetchConfig();
      var interval = setInterval(fetchStatus, 5000);
      return function() { clearInterval(interval); };
    }, []);

    function restartPipeline() {
      setStatus("loading");
      fetch("/api/plugins/pihermes/restart", { method: "POST" })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.success) { setTimeout(fetchStatus, 3000); }
          else { setStatus("error"); setLog(data.message || "Restart failed"); }
        })
        .catch(function() { setStatus("error"); });
    }

    function saveConfig() {
      if (!config) return;
      setSaveMsg("Saving...");
      fetch("/api/plugins/pihermes/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config)
      })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.success) { setSaveMsg("Saved! Restart pipeline to apply."); }
          else { setSaveMsg("Save failed: " + JSON.stringify(data)); }
        })
        .catch(function() { setSaveMsg("Save failed — network error"); });
    }

    var statusBadge;
    if (status === "running") statusBadge = React.createElement(Badge, { variant: "success" }, "Running");
    else if (status === "stopped") statusBadge = React.createElement(Badge, { variant: "warning" }, "Stopped");
    else if (status === "error") statusBadge = React.createElement(Badge, { variant: "destructive" }, "Error");
    else statusBadge = React.createElement(Badge, { variant: "secondary" }, "Loading...");

    return React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: "16px" } },

      // ── Status Card ──
      React.createElement(Card, null,
        React.createElement(CardHeader, null,
          React.createElement(CardTitle, null, "PiHermes Voice Pipeline")
        ),
        React.createElement(CardContent, null,
          React.createElement("div", { style: { display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" } },
            React.createElement("span", { className: "text-sm text-muted-foreground" }, "Status:"),
            statusBadge,
            uptime ? React.createElement("span", { className: "text-xs text-muted-foreground", style: { marginLeft: "8px" } }, "uptime: " + uptime) : null
          ),
          React.createElement(Button, { onClick: restartPipeline, disabled: status === "loading" },
            "Restart Pipeline"
          ),
          log ? React.createElement("pre", {
            style: { marginTop: "12px", padding: "8px", background: "var(--card-midground, rgba(0,0,0,0.3))",
                     borderRadius: "6px", fontSize: "11px", fontFamily: "monospace",
                     maxHeight: "150px", overflow: "auto", whiteSpace: "pre-wrap" }
          }, log) : null
        )
      ),

      // ── Config Card ──
      config ? React.createElement(Card, null,
        React.createElement(CardHeader, null,
          React.createElement(CardTitle, null, "Configuration")
        ),
        React.createElement(CardContent, null,
          React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: "12px" } },

            // TTS Voice
            React.createElement("label", { className: "text-sm" },
              "TTS Voice",
              React.createElement("select", {
                value: config.tts_voice,
                onChange: function(e) { setConfig(Object.assign({}, config, { tts_voice: e.target.value })); },
                style: { display: "block", marginTop: "4px", padding: "6px 8px", width: "100%",
                         borderRadius: "6px", background: "var(--card-midground, rgba(255,255,255,0.05))",
                         color: "var(--midground)", border: "1px solid var(--border-color, rgba(255,255,255,0.1))" }
              },
                React.createElement("option", { value: "en_US-lessac-medium" }, "lessac (female)"),
                React.createElement("option", { value: "en_US-ryan-high" }, "ryan (male)"),
                React.createElement("option", { value: "en_US-ryan-medium" }, "ryan (male, fast)"),
                React.createElement("option", { value: "en_US-amy-medium" }, "amy (female)")
              )
            ),

            // Wake Word
            React.createElement("label", { className: "text-sm" },
              "Wake Word",
              React.createElement("select", {
                value: config.wake_word,
                onChange: function(e) { setConfig(Object.assign({}, config, { wake_word: e.target.value })); },
                style: { display: "block", marginTop: "4px", padding: "6px 8px", width: "100%",
                         borderRadius: "6px", background: "var(--card-midground, rgba(255,255,255,0.05))",
                         color: "var(--midground)", border: "1px solid var(--border-color, rgba(255,255,255,0.1))" }
              },
                React.createElement("option", { value: "hey_bob" }, "Hey Bob"),
                React.createElement("option", { value: "hey_jarvis" }, "Hey Jarvis"),
                React.createElement("option", { value: "alexa" }, "Alexa")
              )
            ),

            // Wake Threshold
            React.createElement("label", { className: "text-sm" },
              "Wake Sensitivity: " + config.wake_threshold,
              React.createElement("input", {
                type: "range", min: "0.3", max: "0.9", step: "0.05",
                value: config.wake_threshold,
                onChange: function(e) { setConfig(Object.assign({}, config, { wake_threshold: parseFloat(e.target.value) })); },
                style: { display: "block", width: "100%", marginTop: "4px" }
              })
            ),

            // STT Provider
            React.createElement("label", { className: "text-sm" },
              "STT Provider",
              React.createElement("select", {
                value: config.stt_provider,
                onChange: function(e) { setConfig(Object.assign({}, config, { stt_provider: e.target.value })); },
                style: { display: "block", marginTop: "4px", padding: "6px 8px", width: "100%",
                         borderRadius: "6px", background: "var(--card-midground, rgba(255,255,255,0.05))",
                         color: "var(--midground)", border: "1px solid var(--border-color, rgba(255,255,255,0.1))" }
              },
                React.createElement("option", { value: "cloud" }, "Cloud (configurable endpoint)"),
                React.createElement("option", { value: "whisper" }, "whisper.cpp (offline)"),
                React.createElement("option", { value: "cloud+whisper" }, "Cloud + whisper fallback")
              )
            ),

            // STT Endpoint (only shown for cloud)
            config.stt_provider !== "whisper" ?
              React.createElement("label", { className: "text-sm" },
                "STT Endpoint URL",
                React.createElement("input", {
                  type: "text",
                  value: config.stt_endpoint || "",
                  placeholder: "https://your-stt-endpoint/v1/chat/completions",
                  onChange: function(e) { setConfig(Object.assign({}, config, { stt_endpoint: e.target.value })); },
                  style: { display: "block", marginTop: "4px", padding: "6px 8px", width: "100%",
                           borderRadius: "6px", background: "var(--card-midground, rgba(255,255,255,0.05))",
                           color: "var(--midground)", border: "1px solid var(--border-color, rgba(255,255,255,0.1))" }
                })
              ) : null,

            // Max tokens
            React.createElement("label", { className: "text-sm" },
              "Response Length (max tokens): " + config.max_tokens,
              React.createElement("input", {
                type: "range", min: "25", max: "200", step: "5",
                value: config.max_tokens,
                onChange: function(e) { setConfig(Object.assign({}, config, { max_tokens: parseInt(e.target.value) })); },
                style: { display: "block", width: "100%", marginTop: "4px" }
              })
            ),

            // Save button
            React.createElement("div", { style: { display: "flex", alignItems: "center", gap: "8px" } },
              React.createElement(Button, { onClick: saveConfig }, "Save Configuration"),
              saveMsg ? React.createElement("span", { className: "text-xs", style: { color: saveMsg.indexOf("Saved") === 0 ? "#22c55e" : "#ef4444" } }, saveMsg) : null
            ),

            React.createElement("p", { className: "text-xs text-muted-foreground", style: { marginTop: "4px" } },
              "API keys and secrets should be configured in ~/.hermes/.env or the pipeline script directly — not stored by this dashboard."
            )
          )
        )
      ) : null,

      // ── Quick Info Card ──
      React.createElement(Card, null,
        React.createElement(CardHeader, null,
          React.createElement(CardTitle, null, "Quick Info")
        ),
        React.createElement(CardContent, null,
          React.createElement("ul", { className: "text-sm text-muted-foreground", style: { lineHeight: "1.8", paddingLeft: "16px" } },
            React.createElement("li", null, "Wake word: configurable (default: \"Hey Bob\")"),
            React.createElement("li", null, "STT: Configurable cloud + offline fallback"),
            React.createElement("li", null, "TTS: Piper on-device (configurable voice)"),
            React.createElement("li", null, "Cycle time: ~10s from wake to response"),
            React.createElement("li", null, "API keys: stored in ~/.hermes/.env and pipeline script")
          )
        )
      )
    );
  }

  window.__HERMES_PLUGINS__.register("pihermes", PiHermesPage);
})();
