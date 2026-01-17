// static/js/job_helpers.js
(function (global) {
  function pickTranscript(obj) {
    if (!obj) return "";
    return (
      obj.transcript ||
      obj.transcription ||
      obj.transcript_text ||
      ""
    );
  }

  function pickSummary(obj) {
    if (!obj) return "";
    if (typeof obj.summary_json === "object" && obj.summary_json) {
      try { return JSON.stringify(obj.summary_json, null, 2); } catch {}
    }
    return obj.summary || obj.summary_text || "";
  }

  global.PSJob = { pickTranscript, pickSummary };
})(window);
