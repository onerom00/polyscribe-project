// frontend/src/pages/index.js
import React, { useEffect, useMemo, useRef, useState } from "react";
// frontend/src/pages/index.js
import SubscribeButton from "@/components/SubscribeButton";

export default function Home() {
  return (
    <main className="min-h-screen p-6">
      {/* ...tu UI... */}
      <div className="mt-6">
        <SubscribeButton />
      </div>
    </main>
  );
}

/**
 * Config
 * Cambia NEXT_PUBLIC_API_URL si expones Flask en otra URL/puerto.
 */
const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:5000";
const MAX_FILE_MB = 50;

/**
 * Catálogo de idiomas.
 * code: ISO aproximado
 * native: nombre nativo (fallback para mostrar)
 * label: nombres localizados (opcional); si falta para uiLang, usa native.
 */
const LANGS = [
  { code: "auto", native: "Auto (detectar)", label: { es: "Auto (detectar)", en: "Auto (detect)", pt: "Auto (detetar)", fr: "Auto (détecter)", de: "Auto (erkennen)" } },
  { code: "ar", native: "العربية", label: { en: "Arabic", es: "Árabe" } },
  { code: "bg", native: "Български", label: { en: "Bulgarian", es: "Búlgaro" } },
  { code: "ca", native: "Català", label: { en: "Catalan", es: "Catalán" } },
  { code: "cs", native: "Čeština", label: { en: "Czech", es: "Checo" } },
  { code: "da", native: "Dansk", label: { en: "Danish", es: "Danés" } },
  { code: "de", native: "Deutsch", label: { en: "German", es: "Alemán", de: "Deutsch" } },
  { code: "el", native: "Ελληνικά", label: { en: "Greek", es: "Griego" } },
  { code: "en", native: "English", label: { en: "English", es: "Inglés", pt: "Inglês", de: "Englisch", fr: "Anglais" } },
  { code: "es", native: "Español", label: { es: "Español", en: "Spanish", pt: "Espanhol", de: "Spanisch", fr: "Espagnol" } },
  { code: "et", native: "Eesti", label: { en: "Estonian", es: "Estonio" } },
  { code: "eu", native: "Euskara", label: { en: "Basque", es: "Euskera" } },
  { code: "fa", native: "فارسی", label: { en: "Persian (Farsi)", es: "Persa (Farsi)" } },
  { code: "fi", native: "Suomi", label: { en: "Finnish", es: "Finés" } },
  { code: "fr", native: "Français", label: { en: "French", es: "Francés", fr: "Français", de: "Französisch" } },
  { code: "gl", native: "Galego", label: { en: "Galician", es: "Gallego" } },
  { code: "he", native: "עברית", label: { en: "Hebrew", es: "Hebreo" } },
  { code: "hi", native: "हिन्दी", label: { en: "Hindi", es: "Hindi" } },
  { code: "hr", native: "Hrvatski", label: { en: "Croatian", es: "Croata" } },
  { code: "hu", native: "Magyar", label: { en: "Hungarian", es: "Húngaro" } },
  { code: "id", native: "Bahasa Indonesia", label: { en: "Indonesian", es: "Indonesio" } },
  { code: "is", native: "Íslenska", label: { en: "Icelandic", es: "Islandés" } },
  { code: "it", native: "Italiano", label: { en: "Italian", es: "Italiano", it: "Italiano" } },
  { code: "ja", native: "日本語", label: { en: "Japanese", es: "Japonés" } },
  { code: "ka", native: "ქართული", label: { en: "Georgian", es: "Georgiano" } },
  { code: "ko", native: "한국어", label: { en: "Korean", es: "Coreano" } },
  { code: "lt", native: "Lietuvių", label: { en: "Lithuanian", es: "Lituano" } },
  { code: "lv", native: "Latviešu", label: { en: "Latvian", es: "Letón" } },
  { code: "ms", native: "Bahasa Melayu", label: { en: "Malay", es: "Malayo" } },
  { code: "nb", native: "Norsk (Bokmål)", label: { en: "Norwegian (Bokmål)", es: "Noruego (Bokmål)" } },
  { code: "nl", native: "Nederlands", label: { en: "Dutch", es: "Neerlandés" } },
  { code: "pl", native: "Polski", label: { en: "Polish", es: "Polaco" } },
  { code: "pt", native: "Português", label: { en: "Portuguese", es: "Portugués", pt: "Português" } },
  { code: "ro", native: "Română", label: { en: "Romanian", es: "Rumano" } },
  { code: "ru", native: "Русский", label: { en: "Russian", es: "Ruso" } },
  { code: "sk", native: "Slovenčina", label: { en: "Slovak", es: "Eslovaco" } },
  { code: "sl", native: "Slovenščina", label: { en: "Slovene", es: "Esloveno" } },
  { code: "sr", native: "Српски", label: { en: "Serbian", es: "Serbio" } },
  { code: "sv", native: "Svenska", label: { en: "Swedish", es: "Sueco" } },
  { code: "th", native: "ไทย", label: { en: "Thai", es: "Tailandés" } },
  { code: "tr", native: "Türkçe", label: { en: "Turkish", es: "Turco" } },
  { code: "uk", native: "Українська", label: { en: "Ukrainian", es: "Ucraniano" } },
  { code: "ur", native: "اردو", label: { en: "Urdu", es: "Urdu" } },
  { code: "vi", native: "Tiếng Việt", label: { en: "Vietnamese", es: "Vietnamita" } },
  { code: "zh", native: "中文", label: { en: "Chinese", es: "Chino" } },
];

/** Textos de interfaz (los más usados). Fallback a 'en' y luego a la clave. */
const UI_TEXT = {
  es: {
    title: "PolyScribe · Transcriptor Global",
    uiLang: "🌍 Cambiar idioma:",
    reset: "🔄 Restablecer",
    resetNote: "(Tu preferencia se recordará en este navegador)",
    dropHere: "Arrastra tu archivo o haz clic aquí para seleccionar audio",
    formats: "(.mp3, .wav, .m4a…)",
    transcribe: "Transcribir",
    status_idle: "Listo",
    status_uploading: "Subiendo…",
    status_queued: "En cola…",
    status_working: "Procesando…",
    status_done: "Completado",
    status_error: "Error",
    transcript: "Transcripción:",
    copyText: "Copiar texto",
    downloadTxt: "Descargar TXT",
    smartSummary: "Resumen Inteligente:",
    copySummary: "Copiar resumen",
    summaryLang: "Idioma del resumen:",
    autoDetect: "Auto (detectar)",
    fileTooBig: `Archivo demasiado grande (máx. ${MAX_FILE_MB} MB).`,
    pickFile: "Selecciona un archivo de audio.",
  },
  en: {
    title: "PolyScribe · Global Transcriber",
    uiLang: "🌍 Change language:",
    reset: "🔄 Reset",
    resetNote: "(Your preference will be remembered in this browser)",
    dropHere: "Drag & drop or click to select audio",
    formats: "(.mp3, .wav, .m4a…)",
    transcribe: "Transcribe",
    status_idle: "Ready",
    status_uploading: "Uploading…",
    status_queued: "Queued…",
    status_working: "Processing…",
    status_done: "Completed",
    status_error: "Error",
    transcript: "Transcription:",
    copyText: "Copy text",
    downloadTxt: "Download TXT",
    smartSummary: "Smart Summary:",
    copySummary: "Copy summary",
    summaryLang: "Summary language:",
    autoDetect: "Auto (detect)",
    fileTooBig: `File too large (max ${MAX_FILE_MB} MB).`,
    pickFile: "Pick an audio file.",
  },
  pt: {
    title: "PolyScribe · Transcritor Global",
    uiLang: "🌍 Mudar idioma:",
    reset: "🔄 Redefinir",
    resetNote: "(Sua preferência será lembrada neste navegador)",
    dropHere: "Arraste ou clique para selecionar o áudio",
    formats: "(.mp3, .wav, .m4a…)",
    transcribe: "Transcrever",
    status_idle: "Pronto",
    status_uploading: "Enviando…",
    status_queued: "Em fila…",
    status_working: "Processando…",
    status_done: "Concluído",
    status_error: "Erro",
    transcript: "Transcrição:",
    copyText: "Copiar texto",
    downloadTxt: "Baixar TXT",
    smartSummary: "Resumo Inteligente:",
    copySummary: "Copiar resumo",
    summaryLang: "Idioma do resumo:",
    autoDetect: "Auto (detetar)",
    fileTooBig: `Arquivo muito grande (máx. ${MAX_FILE_MB} MB).`,
    pickFile: "Selecione um arquivo de áudio.",
  },
  fr: {
    title: "PolyScribe · Transcripteur Global",
    uiLang: "🌍 Changer de langue :",
    reset: "🔄 Réinitialiser",
    resetNote: "(Votre préférence sera mémorisée dans ce navigateur)",
    dropHere: "Glissez-déposez ou cliquez pour choisir un audio",
    formats: "(.mp3, .wav, .m4a…)",
    transcribe: "Transcrire",
    status_idle: "Prêt",
    status_uploading: "Téléversement…",
    status_queued: "En file…",
    status_working: "Traitement…",
    status_done: "Terminé",
    status_error: "Erreur",
    transcript: "Transcription :",
    copyText: "Copier le texte",
    downloadTxt: "Télécharger TXT",
    smartSummary: "Résumé intelligent :",
    copySummary: "Copier le résumé",
    summaryLang: "Langue du résumé :",
    autoDetect: "Auto (détecter)",
    fileTooBig: `Fichier trop volumineux (max ${MAX_FILE_MB} Mo).`,
    pickFile: "Sélectionnez un fichier audio.",
  },
  de: {
    title: "PolyScribe · Globaler Transkriptor",
    uiLang: "🌍 Sprache ändern:",
    reset: "🔄 Zurücksetzen",
    resetNote: "(Ihre Präferenz wird in diesem Browser gemerkt)",
    dropHere: "Ziehe oder klicke hier, um Audio auszuwählen",
    formats: "(.mp3, .wav, .m4a…)",
    transcribe: "Transkribieren",
    status_idle: "Bereit",
    status_uploading: "Wird hochgeladen…",
    status_queued: "In der Warteschlange…",
    status_working: "Verarbeitung…",
    status_done: "Abgeschlossen",
    status_error: "Fehler",
    transcript: "Transkription:",
    copyText: "Text kopieren",
    downloadTxt: "TXT herunterladen",
    smartSummary: "Intelligente Zusammenfassung:",
    copySummary: "Zusammenfassung kopieren",
    summaryLang: "Sprache der Zusammenfassung:",
    autoDetect: "Auto (erkennen)",
    fileTooBig: `Datei zu groß (max. ${MAX_FILE_MB} MB).`,
    pickFile: "Wähle eine Audiodatei.",
  },
};

function tFactory(uiLang) {
  const dict = UI_TEXT[uiLang] || UI_TEXT.en;
  return (key) => dict[key] || UI_TEXT.en[key] || key;
}

function langLabel(code, uiLang) {
  const l = LANGS.find((x) => x.code === code);
  if (!l) return code;
  const byUI = (l.label && l.label[uiLang]) || null;
  const byES = l.label && l.label.es;
  const byEN = l.label && l.label.en;
  return byUI || l.native || byES || byEN || l.code;
}

function sortLangsForUI(list, uiLang) {
  return [...list].sort((a, b) => {
    const la = (a.label && (a.label[uiLang] || a.label.es || a.label.en)) || a.native || a.code;
    const lb = (b.label && (b.label[uiLang] || b.label.es || b.label.en)) || b.native || b.code;
    return la.localeCompare(lb, uiLang);
  });
}

const UI_LANGS = LANGS.filter((l) => l.code !== "auto");
const SUMMARY_LANGS = [
  LANGS.find((l) => l.code === "auto"),
  ...LANGS.filter((l) => l.code !== "auto"),
].filter(Boolean);

export default function Home() {
  const [uiLang, setUiLang] = useState("es");
  const [summaryLang, setSummaryLang] = useState("auto");
  const [status, setStatus] = useState("idle"); // idle|uploading|queued|working|done|error
  const [error, setError] = useState("");
  const [transcript, setTranscript] = useState("");
  const [summary, setSummary] = useState("");
  const [fileName, setFileName] = useState("");
  const fileInputRef = useRef(null);
  const t = useMemo(() => tFactory(uiLang), [uiLang]);

  // Cargar preferencias guardadas
  useEffect(() => {
    try {
      const savedUI = localStorage.getItem("uiLang");
      const savedSum = localStorage.getItem("summaryLang");
      if (savedUI && LANGS.find((l) => l.code === savedUI)) setUiLang(savedUI);
      if (savedSum && LANGS.find((l) => l.code === savedSum)) setSummaryLang(savedSum);
    } catch (_) {}
  }, []);

  // Guardar preferencias
  useEffect(() => {
    try {
      localStorage.setItem("uiLang", uiLang);
      localStorage.setItem("summaryLang", summaryLang);
    } catch (_) {}
  }, [uiLang, summaryLang]);

  function resetAll() {
    setStatus("idle");
    setError("");
    setTranscript("");
    setSummary("");
    setFileName("");
    setSummaryLang("auto"); // volver a estado original
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleUpload(file) {
    if (!file) {
      setError(t("pickFile"));
      return;
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      setError(t("fileTooBig"));
      return;
    }
    setError("");
    setTranscript("");
    setSummary("");
    setFileName(file.name);
    setStatus("uploading");

    const fd = new FormData();
    fd.append("audio", file);
    fd.append("idioma", summaryLang); // lo usa el backend para resumen

    let jobId = null;
    try {
      const res = await fetch(`${API}/jobs`, {
        method: "POST",
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus("error");
        setError(typeof data === "object" ? data.error || JSON.stringify(data) : String(data));
        return;
      }
      jobId = data.job_id;
      setStatus("queued");
    } catch (e) {
      setStatus("error");
      setError(String(e));
      return;
    }

    // Sondeo del job
    let attempts = 0;
    const maxAttempts = 120; // ~2 min con 1s
    while (attempts < maxAttempts) {
      attempts++;
      try {
        const r = await fetch(`${API}/jobs/${jobId}`);
        const j = await r.json();
        if (!r.ok) {
          // seguir intentando unos segundos (puede tardar en persistir)
          await new Promise((s) => setTimeout(s, 1000));
          continue;
        }
        if (j.status === "done") {
          setStatus("done");
          setTranscript(j.transcript || "");

          // Elegir resumen:
          // 1) si se pidió un idioma específico, úsalo
          // 2) si no, intenta usar j.language (si el backend lo marca)
          // 3) o el primero disponible
          let chosen = "";
          if (j.summaries && typeof j.summaries === "object") {
            if (summaryLang !== "auto" && j.summaries[summaryLang]) {
              chosen = j.summaries[summaryLang];
            } else if (j.language && j.summaries[j.language]) {
              chosen = j.summaries[j.language];
            } else {
              const vals = Object.values(j.summaries);
              chosen = vals && vals.length ? vals[0] : "";
            }
          }
          setSummary(chosen || "");
          return;
        } else if (j.status === "error") {
          setStatus("error");
          setError(j.error || "Error");
          return;
        } else if (j.status === "queued") {
          setStatus("queued");
        } else {
          setStatus("working");
        }
      } catch (_) {
        // silencio y retry
      }
      await new Promise((s) => setTimeout(s, 1000));
    }
    setStatus("error");
    setError("Timeout al esperar el procesamiento.");
  }

  function onFileChange(e) {
    const f = e.target.files?.[0];
    if (f) handleUpload(f);
  }

  function onDrop(ev) {
    ev.preventDefault();
    const f = ev.dataTransfer?.files?.[0];
    if (f) handleUpload(f);
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-2xl font-semibold">{t("title")}</h1>

          <div className="flex flex-col items-end gap-2">
            <div className="text-sm">{t("uiLang")}</div>
            <div className="flex gap-2">
              <select
                className="border rounded px-2 py-1 bg-white"
                value={uiLang}
                onChange={(e) => setUiLang(e.target.value)}
                title="UI language"
              >
                {sortLangsForUI(UI_LANGS, uiLang).map((l) => (
                  <option key={l.code} value={l.code}>
                    {langLabel(l.code, uiLang)}
                  </option>
                ))}
              </select>

              <button
                type="button"
                className="border rounded px-3 py-1 bg-white hover:bg-gray-100"
                onClick={resetAll}
                title="Reset"
              >
                {t("reset")}
              </button>
            </div>
            <div className="text-xs text-gray-500">{t("resetNote")}</div>
          </div>
        </div>

        {/* Selector idioma de resumen */}
        <div className="mt-6">
          <label className="block text-sm mb-1">{t("summaryLang")}</label>
          <select
            className="border rounded px-2 py-1 bg-white"
            value={summaryLang}
            onChange={(e) => setSummaryLang(e.target.value)}
          >
            {sortLangsForUI(SUMMARY_LANGS, uiLang).map((l) => (
              <option key={l.code} value={l.code}>
                {l.code === "auto" ? t("autoDetect") : langLabel(l.code, uiLang)}
              </option>
            ))}
          </select>
        </div>

        {/* Zona de carga */}
        <div
          className="mt-6 p-6 border-2 border-dashed rounded-lg bg-white text-center cursor-pointer"
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          title="Select file"
        >
          <p className="font-medium">{t("dropHere")}</p>
          <p className="text-sm text-gray-500 mt-1">{t("formats")}</p>
          {fileName ? (
            <p className="text-sm text-gray-600 mt-2">📎 {fileName}</p>
          ) : null}
          <input
            ref={fileInputRef}
            type="file"
            accept=".mp3,.wav,.m4a,.mp4,.ogg,.webm,audio/*,video/mp4"
            className="hidden"
            onChange={onFileChange}
          />
        </div>

        {/* Acción */}
        <div className="mt-4">
          <button
            type="button"
            className="px-4 py-2 rounded bg-black text-white disabled:opacity-50"
            onClick={() => fileInputRef.current?.click()}
          >
            {t("transcribe")}
          </button>
          <span className="ml-3 text-sm text-gray-600">
            {status === "idle" && t("status_idle")}
            {status === "uploading" && t("status_uploading")}
            {status === "queued" && t("status_queued")}
            {status === "working" && t("status_working")}
            {status === "done" && t("status_done")}
            {status === "error" && t("status_error")}
          </span>
        </div>

        {/* Error */}
        {error ? (
          <div className="mt-4 p-3 rounded bg-red-50 text-red-700 text-sm whitespace-pre-wrap">
            {error}
          </div>
        ) : null}

        {/* Transcripción */}
        <div className="mt-8">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">{t("transcript")}</h2>
            <div className="flex gap-2">
              <button
                type="button"
                className="px-3 py-1 border rounded bg-white hover:bg-gray-100"
                onClick={() => {
                  if (!transcript) return;
                  navigator.clipboard.writeText(transcript).catch(() => {});
                }}
              >
                {t("copyText")}
              </button>
              <button
                type="button"
                className="px-3 py-1 border rounded bg-white hover:bg-gray-100"
                onClick={() => {
                  if (!transcript) return;
                  const blob = new Blob([transcript], { type: "text/plain;charset=utf-8" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "transcript.txt";
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                {t("downloadTxt")}
              </button>
            </div>
          </div>
          <textarea
            className="mt-2 w-full min-h-[180px] p-3 border rounded bg-white"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder=""
          />
        </div>

        {/* Resumen */}
        <div className="mt-6">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">{t("smartSummary")}</h2>
            <div className="flex gap-2">
              <button
                type="button"
                className="px-3 py-1 border rounded bg-white hover:bg-gray-100"
                onClick={() => {
                  if (!summary) return;
                  navigator.clipboard.writeText(summary).catch(() => {});
                }}
              >
                {t("copySummary")}
              </button>
              <button
                type="button"
                className="px-3 py-1 border rounded bg-white hover:bg-gray-100"
                onClick={() => {
                  if (!summary) return;
                  const blob = new Blob([summary], { type: "text/plain;charset=utf-8" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "summary.txt";
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                {t("downloadTxt")}
              </button>
            </div>
          </div>
          <textarea
            className="mt-2 w-full min-h-[140px] p-3 border rounded bg-white"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder=""
          />
        </div>
      </div>
    </div>
  );
}
