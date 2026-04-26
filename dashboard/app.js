/* ═══════════════════════════════════════════════════════
   PREMIERLEAGUEML — app.js v3
   Motor de datos + interacción visual premium
   ═══════════════════════════════════════════════════════ */

const DATA_CANDIDATES = [
    "./dashboard_data.json",
    "../outputs/dashboard_data.json",
    `${window.location.origin}/outputs/dashboard_data.json`,
    `${window.location.origin}/dashboard/dashboard_data.json`,
    `${window.location.origin}${window.location.pathname.replace(/\/dashboard\/$/, "")}/outputs/dashboard_data.json`,
];

const EDA_DATA_CANDIDATES = [
    "./dashboard_eda_data.json",
    `${window.location.origin}/dashboard/dashboard_eda_data.json`,
    `${window.location.origin}${window.location.pathname.replace(/\/dashboard\/$/, "")}/dashboard/dashboard_eda_data.json`,
];

const API_BASE_URL = window.PREMIER_API_BASE_URL || "http://127.0.0.1:8001";
const API_TIMEOUT_MS = 3500;

let dashboardData = null;
let dashboardEdaData = null;
let apiState = {
    connected: false,
    mode: "checking",
    health: null,
    modelInfo: null,
    error: null,
    activeBaseUrl: null,
};

const CSV_PREDICT_TASKS = [
    {
        value: "xg",
        label: "xG por tiro",
        help: "CSV mínimo requerido: x,y",
        example: "Ejemplo mínimo: x,y",
        requiredColumns: ["x", "y"],
    },
    {
        value: "match_result",
        label: "Resultado de partido H/D/A",
        help: "CSV mínimo requerido: home_team,away_team",
        example: "Ejemplo mínimo: home_team,away_team",
        requiredColumns: ["home_team", "away_team"],
    },
    {
        value: "match_goals",
        label: "Goles esperados del partido",
        help: "CSV mínimo requerido: home_team,away_team",
        example: "Ejemplo mínimo: home_team,away_team",
        requiredColumns: ["home_team", "away_team"],
    },
    {
        value: "match_full",
        label: "Predictor completo de partido",
        help: "CSV mínimo requerido: home_team,away_team",
        example: "Ejemplo mínimo: home_team,away_team",
        requiredColumns: ["home_team", "away_team"],
    },
];

const CSV_PREDICT_SUMMARY_LABELS = {
    avg_xg: "Promedio xG",
    max_xg: "Máximo xG",
    high_quality_shots: "Tiros de alta calidad",
    home_predictions: "Predicciones Home",
    draw_predictions: "Predicciones Draw",
    away_predictions: "Predicciones Away",
    avg_expected_goals: "Promedio goles esperados",
};

let csvPredictState = {
    loading: false,
    message: "",
    error: "",
    csvBase64: null,
    lastPreview: null,
};

let MATCH_PREDICTION_REQUEST_ID = 0;
const DEFERRED_RENDER_REGISTRY = new Set();
const SHOT_MAP_STATE = {
    viewMode: "all",
    showZones: true,
};
const GLOBAL_SHOT_EXPLORER_STATE = {
    mode: "goals",
};
const XG_DASHBOARD_STATE = {
    team: "all",
    player: "all",
    shotType: "all",
};
const XG_ZONE_DEFINITIONS = [
    { key: "small_box", label: "Área chica" },
    { key: "penalty_box", label: "Área grande" },
    { key: "outside_box", label: "Fuera del área" },
];
const XG_SHOT_TYPE_LABELS = {
    all: "Todos los tiros",
    foot: "Pie",
    header: "Cabeza",
    penalty: "Penal",
    other: "Otro",
};
const XG_DENSITY_COLORSCALE = [
    [0.00, "rgba(15,23,42,0.00)"],
    [0.15, "rgba(56,189,248,0.28)"],
    [0.45, "rgba(16,185,129,0.42)"],
    [0.72, "rgba(250,204,21,0.58)"],
    [1.00, "rgba(239,68,68,0.82)"],
];
const PITCH_THEME = {
    surface: "#0f4f33",
    surfaceDeep: "#0a3a25",
    surfaceTint: "rgba(8,36,23,0.14)",
    line: "rgba(245,250,247,0.92)",
    axisText: "rgba(232,245,237,0.82)",
    axisTextSoft: "rgba(232,245,237,0.58)",
    legendPanel: "rgba(5,24,15,0.74)",
    legendBorder: "rgba(230,244,238,0.18)",
    hoverPanel: "rgba(4,18,11,0.96)",
    hoverBorder: "rgba(167,243,208,0.22)",
};
const PITCH_BG_SRC = new URL("./assets/pitch-bg.png", window.location.href).href;
const PITCH_REAL_SRC = new URL("./assets/pitch-real.png", window.location.href).href;
const PITCH_TEXTURE = new Image();
PITCH_TEXTURE.src = PITCH_REAL_SRC;
const PITCH_CANVAS_INSTANCES = new Map();
PITCH_TEXTURE.addEventListener("load", () => {
    PITCH_CANVAS_INSTANCES.forEach(instance => drawCanvasPitch(instance, false));
});

const TEAM_LOGOS = {
    "Arsenal": "https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/512px-Arsenal_FC.svg.png",
    "Aston Villa": "https://upload.wikimedia.org/wikipedia/en/thumb/f/f9/Aston_Villa_FC_crest.svg/512px-Aston_Villa_FC_crest.svg.png",
    "Bournemouth": "https://upload.wikimedia.org/wikipedia/en/thumb/e/e5/AFC_Bournemouth_%282013%29.svg/512px-AFC_Bournemouth_%282013%29.svg.png",
    "Brentford": "https://upload.wikimedia.org/wikipedia/en/thumb/2/2a/Brentford_FC_crest.svg/512px-Brentford_FC_crest.svg.png",
    "Brighton": "https://upload.wikimedia.org/wikipedia/en/thumb/f/fd/Brighton_%26_Hove_Albion_logo.svg/512px-Brighton_%26_Hove_Albion_logo.svg.png",
    "Burnley": "https://upload.wikimedia.org/wikipedia/en/thumb/6/6d/Burnley_FC_Logo.svg/512px-Burnley_FC_Logo.svg.png",
    "Chelsea": "https://upload.wikimedia.org/wikipedia/en/thumb/c/cc/Chelsea_FC.svg/512px-Chelsea_FC.svg.png",
    "Crystal Palace": "https://upload.wikimedia.org/wikipedia/en/thumb/a/a2/Crystal_Palace_FC_logo_%282022%29.svg/512px-Crystal_Palace_FC_logo_%282022%29.svg.png",
    "Everton": "https://upload.wikimedia.org/wikipedia/en/thumb/7/7c/Everton_FC_logo.svg/512px-Everton_FC_logo.svg.png",
    "Fulham": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Fulham_FC_%28shield%29.svg/512px-Fulham_FC_%28shield%29.svg.png",
    "Luton": "https://upload.wikimedia.org/wikipedia/en/thumb/9/9d/Luton_Town_logo.svg/512px-Luton_Town_logo.svg.png",
    "Leeds": "https://upload.wikimedia.org/wikipedia/en/thumb/5/54/Leeds_United_F.C._logo.svg/512px-Leeds_United_F.C._logo.svg.png",
    "Liverpool": "https://upload.wikimedia.org/wikipedia/en/thumb/0/0c/Liverpool_FC.svg/512px-Liverpool_FC.svg.png",
    "Man City": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/512px-Manchester_City_FC_badge.svg.png",
    "Man United": "https://upload.wikimedia.org/wikipedia/en/thumb/7/7a/Manchester_United_FC_crest.svg/512px-Manchester_United_FC_crest.svg.png",
    "Newcastle": "https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Newcastle_United_Logo.svg/512px-Newcastle_United_Logo.svg.png",
    "Nottingham Forest": "https://upload.wikimedia.org/wikipedia/en/thumb/e/e5/Nottingham_Forest_F.C._logo.svg/512px-Nottingham_Forest_F.C._logo.svg.png",
    "Sheffield United": "https://upload.wikimedia.org/wikipedia/en/thumb/9/9c/Sheffield_United_FC_logo.svg/512px-Sheffield_United_FC_logo.svg.png",
    "Sunderland": "https://upload.wikimedia.org/wikipedia/en/thumb/7/77/SAFC_crest.svg/512px-SAFC_crest.svg.png",
    "Tottenham": "https://upload.wikimedia.org/wikipedia/en/thumb/b/b4/Tottenham_Hotspur.svg/512px-Tottenham_Hotspur.svg.png",
    "West Ham": "https://upload.wikimedia.org/wikipedia/en/thumb/c/c2/West_Ham_United_FC_logo.svg/512px-West_Ham_United_FC_logo.svg.png",
    "Wolves": "https://upload.wikimedia.org/wikipedia/en/thumb/f/fc/Wolverhampton_Wanderers.svg/512px-Wolverhampton_Wanderers.svg.png",
};

const TEAM_MAP = {
    "Man Utd": "Man United",
    "Man Utd.": "Man United",
    "Manchester United": "Man United",
    "Manchester City": "Man City",
    "Nott'm Forest": "Nottingham Forest",
    "Nottm Forest": "Nottingham Forest",
    "Notts Forest": "Nottingham Forest",
    "Spurs": "Tottenham",
    "Tottenham Hotspur": "Tottenham",
    "Wolverhampton": "Wolves",
    "Wolverhampton Wanderers": "Wolves",
    "Aston Villa FC": "Aston Villa",
    "AstonVilla": "Aston Villa",
    "Villa": "Aston Villa",
    "Sunderland AFC": "Sunderland",
};

const TEAM_LOGO_IDS = {
    "Arsenal": 57,
    "Aston Villa": 58,
    "Bournemouth": 1044,
    "Brentford": 402,
    "Brighton": 397,
    "Burnley": 328,
    "Chelsea": 61,
    "Crystal Palace": 354,
    "Everton": 62,
    "Fulham": 63,
    "Leeds": 341,
    "Liverpool": 64,
    "Luton": 389,
    "Man City": 65,
    "Man United": 66,
    "Newcastle": 67,
    "Nottingham Forest": 351,
    "Sheffield United": 356,
    "Tottenham": 73,
    "West Ham": 563,
    "Wolves": 76,
    "Sunderland": 338,
};

const LOGO_PLACEHOLDER = "https://via.placeholder.com/40?text=%3F";

const TEAM_STADIUMS = {
    "Arsenal": "Emirates Stadium",
    "Aston Villa": "Villa Park",
    "Bournemouth": "Vitality Stadium",
    "Brentford": "Gtech Community Stadium",
    "Brighton": "Amex Stadium",
    "Burnley": "Turf Moor",
    "Chelsea": "Stamford Bridge",
    "Crystal Palace": "Selhurst Park",
    "Everton": "Goodison Park",
    "Fulham": "Craven Cottage",
    "Leeds": "Elland Road",
    "Liverpool": "Anfield",
    "Man City": "Etihad Stadium",
    "Man United": "Old Trafford",
    "Newcastle": "St James' Park",
    "Nott'm Forest": "The City Ground",
    "Nottingham Forest": "The City Ground",
    "Sunderland": "Stadium of Light",
    "Tottenham": "Tottenham Hotspur Stadium",
    "West Ham": "London Stadium",
    "Wolves": "Molineux Stadium",
};

// ── ENTRY POINT ──────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    setupNavbar();
    setupCinemaIntro();
    setupHeroStagger();
    setupRevealAnimations();
    setupPipelineAnimations();
    setupPremiumVideoCards();
    setApiStatus("checking", "API verificando");
    const apiStatusPromise = checkApiStatus();

    try {
        dashboardData = await loadDashboardData();
        dashboardEdaData = await loadDashboardEdaData();

        safeCall("hydrateHero",       hydrateHero);
        safeCall("hydrateValueStrip", hydrateValueStrip);
        safeCall("setupDeferredRendering", setupDeferredRendering);
        scheduleIdleWork("setupGoalSimulation", setupGoalSimulation, 200);
        setupCsvPredictModal();

    } catch (err) {
        console.error("Error crítico:", err);
        document.body.innerHTML = `
            <main style="min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#040608;color:#fff;font-family:Inter,sans-serif;padding:2rem;text-align:center;">
                <h1 style="font-size:1.4rem;margin-bottom:1rem;">Error al cargar el dashboard</h1>
                <p style="color:rgba(255,255,255,.4);max-width:480px;">${err.message}</p>
                <p style="margin-top:.75rem;font-size:.8rem;color:rgba(255,255,255,.2);">
                    Verifica que <code>dashboard_data.js</code> esté correctamente generado.
                </p>
            </main>`;
    }

    apiStatusPromise.catch(() => {});
});

function safeCall(name, fn) {
    try { fn(); }
    catch (e) { console.error(`✗ ${name}:`, e.message); }
}

function scheduleIdleWork(name, fn, timeout = 400) {
    const runner = () => safeCall(name, fn);
    if (typeof window.requestIdleCallback === "function") {
        window.requestIdleCallback(runner, { timeout });
        return;
    }
    window.setTimeout(runner, Math.min(timeout, 220));
}

function runDeferredJobOnce(name, fn, timeout = 400) {
    if (DEFERRED_RENDER_REGISTRY.has(name)) return;
    DEFERRED_RENDER_REGISTRY.add(name);
    scheduleIdleWork(name, fn, timeout);
}

function observeSectionRender(selector, jobs = [], options = {}) {
    const target = document.querySelector(selector);
    if (!target || !jobs.length) return;

    const runJobs = () => {
        jobs.forEach((job, index) => {
            runDeferredJobOnce(job.name, job.fn, (options.timeout || 400) + (index * 80));
        });
    };

    if (typeof IntersectionObserver === "undefined") {
        runJobs();
        return;
    }

    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            observer.disconnect();
            runJobs();
        });
    }, {
        rootMargin: options.rootMargin || "320px 0px",
        threshold: options.threshold || 0.01,
    });

    observer.observe(target);
}

function setupDeferredRendering() {
    observeSectionRender("#match-cards", [
        { name: "renderFeaturedMatches", fn: renderFeaturedMatches },
    ], { rootMargin: "500px 0px" });

    observeSectionRender("#eda", [
        { name: "renderDashboardEdaSection", fn: renderDashboardEdaSection },
        { name: "setupGlobalShotExplorerControls", fn: setupGlobalShotExplorerControls },
        { name: "renderGlobalPitchShotMaps", fn: renderGlobalPitchShotMaps },
        { name: "renderEdaCharts", fn: renderEdaCharts },
        { name: "renderTeamFormTrend", fn: renderTeamFormTrend },
    ], { rootMargin: "260px 0px" });

    observeSectionRender("#xg", [
        { name: "hydrateXgSpotlight", fn: hydrateXgSpotlight },
        { name: "initializeXgExplorer", fn: initializeXgExplorer },
    ], { rootMargin: "260px 0px" });

    observeSectionRender("#modelos", [
        { name: "renderKpiCards", fn: renderKpiCards },
        { name: "renderXgPerformanceCharts", fn: renderXgPerformanceCharts },
        { name: "renderBaselineXg", fn: renderBaselineXg },
        { name: "renderCrossValComparison", fn: renderCrossValComparison },
        { name: "renderLinearResiduals", fn: renderLinearResiduals },
        { name: "renderModelMetricsComparison", fn: renderModelMetricsComparison },
        { name: "renderClassMetricsChart", fn: renderClassMetricsChart },
        { name: "renderAblationComparison", fn: renderAblationComparison },
        { name: "renderRfComparison", fn: renderRfComparison },
    ], { rootMargin: "300px 0px" });

    observeSectionRender("#predictor", [
        { name: "initializeSelectors", fn: initializeSelectors },
        { name: "setupShotMapControls", fn: setupShotMapControls },
        { name: "renderMatchPrediction", fn: renderMatchPrediction },
        { name: "renderConfusionMatrix", fn: renderConfusionMatrix },
    ], { rootMargin: "320px 0px" });

    observeSectionRender("#hallazgos", [
        { name: "hydrateFindings", fn: hydrateFindings },
        { name: "renderFindingComparison", fn: renderFindingComparison },
    ], { rootMargin: "280px 0px" });

    observeSectionRender("#pipeline", [
        { name: "renderNarrative", fn: renderNarrative },
    ], { rootMargin: "240px 0px" });

    observeSectionRender("#clustering", [
        { name: "renderClustering", fn: renderClustering },
    ], { rootMargin: "280px 0px" });
}

// ── DATA LOADING ─────────────────────────────────────────
async function loadDashboardData() {
    if (window.DASHBOARD_DATA) {
        console.log("✓ Data desde window.DASHBOARD_DATA");
        return window.DASHBOARD_DATA;
    }
    for (const url of DATA_CANDIDATES) {
        try {
            const r = await fetch(url);
            if (r.ok) { console.log("✓ Data desde:", url); return r.json(); }
        } catch (_) {}
    }
    throw new Error("No se pudo cargar dashboard_data.json ni window.DASHBOARD_DATA.");
}

async function loadDashboardEdaData() {
    if (window.DASHBOARD_EDA_DATA) {
        console.log("✓ EDA data desde window.DASHBOARD_EDA_DATA");
        return window.DASHBOARD_EDA_DATA;
    }
    for (const url of EDA_DATA_CANDIDATES) {
        try {
            const r = await fetch(url);
            if (r.ok) {
                console.log("✓ EDA data desde:", url);
                return r.json();
            }
        } catch (_) {}
    }
    console.warn("○ dashboard_eda_data.json no disponible; la seccion EDA avanzada mostrara un aviso.");
    return null;
}

function setApiStatus(mode, label, detail = "") {
    apiState.mode = mode;
    const status = document.getElementById("api-status");
    const statusLabel = document.getElementById("api-status-label");
    if (!status || !statusLabel) return;
    status.classList.remove("api-status--checking", "api-status--online", "api-status--offline");
    status.classList.add(`api-status--${mode}`);
    statusLabel.textContent = label;
    status.title = detail || `${label} (${getCurrentApiBaseUrl()})`;
}

function renderCsvPredictStatus(message, isError = false) {
    const el = document.getElementById("csv-predict-status");
    if (!el) return;
    el.textContent = message;
    el.style.color = isError ? "#fda4af" : "rgba(255,255,255,.75)";
}

function getCsvPredictTaskConfig(taskValue) {
    return CSV_PREDICT_TASKS.find(task => task.value === taskValue) || CSV_PREDICT_TASKS[0];
}

function setupCsvPredictTaskOptions() {
    const taskInput = document.getElementById("csv-predict-task");
    if (!taskInput) return;
    taskInput.innerHTML = CSV_PREDICT_TASKS
        .map(task => `<option value="${task.value}">${task.label}</option>`)
        .join("");
}

function updateCsvPredictTaskHelp() {
    const taskInput = document.getElementById("csv-predict-task");
    const helpEl = document.getElementById("csv-predict-help");
    const exampleEl = document.getElementById("csv-predict-example");
    if (!taskInput) return;
    const config = getCsvPredictTaskConfig(taskInput.value);
    if (helpEl) helpEl.textContent = config.help;
    if (exampleEl) exampleEl.textContent = config.example;
}

function setCsvPredictLoading(isLoading) {
    const submit = document.getElementById("csv-predict-submit");
    if (submit) {
        submit.disabled = isLoading;
        submit.textContent = isLoading ? "Procesando..." : "Predecir";
    }
    csvPredictState.loading = isLoading;
}

function toggleCsvPredictDownload(visible) {
    const download = document.getElementById("csv-predict-download");
    if (!download) return;
    download.classList.toggle("is-hidden", !visible);
}

function formatCsvSummaryValue(value) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
        if (Number.isInteger(numeric)) return String(numeric);
        return numeric.toFixed(Math.abs(numeric) < 1 ? 3 : 2);
    }
    return String(value ?? "-");
}

function csvSummaryLabel(key) {
    return CSV_PREDICT_SUMMARY_LABELS[key] || key
        .replace(/_/g, " ")
        .replace(/\b([a-z])/g, (match) => match.toUpperCase());
}

function renderCsvPredictSummary(summary) {
    const summaryEl = document.getElementById("csv-predict-summary");
    if (!summaryEl) return;
    if (!summary || typeof summary !== "object") {
        summaryEl.classList.add("is-hidden");
        summaryEl.innerHTML = "";
        return;
    }
    const fragments = Object.entries(summary).map(([key, value]) => {
        return `<div><strong>${csvSummaryLabel(key)}</strong><span>${formatCsvSummaryValue(value)}</span></div>`;
    });
    summaryEl.innerHTML = fragments.join("");
    summaryEl.classList.remove("is-hidden");
}

async function getMissingCsvColumns(file, requiredColumns) {
    if (!file || !requiredColumns?.length) return [];
    const head = await file.slice(0, 4096).text();
    const firstLine = head.split(/\r?\n/).find(line => line.trim());
    if (!firstLine) return requiredColumns;
    const delimiter = firstLine.includes(";") && !firstLine.includes(",") ? ";" : ",";
    const headers = firstLine
        .replace(/^\uFEFF/, "")
        .split(delimiter)
        .map(header => header.trim().replace(/^"|"$/g, "").toLowerCase());
    const headerSet = new Set(headers);
    return requiredColumns.filter(column => !headerSet.has(column.toLowerCase()));
}

function renderCsvPredictPreview(preview) {
    const previewEl = document.getElementById("csv-predict-preview");
    if (!previewEl) return;
    if (!Array.isArray(preview) || !preview.length) {
        previewEl.classList.add("is-hidden");
        previewEl.innerHTML = "";
        return;
    }
    const columns = Object.keys(preview[0]);
    const header = columns.map((column) => `<th>${column}</th>`).join("");
    const rows = preview.slice(0, 20).map((row) => {
        const cells = columns.map((column) => `<td>${row[column] ?? ""}</td>`).join("");
        return `<tr>${cells}</tr>`;
    }).join("");
    previewEl.innerHTML = `
        <table>
            <thead><tr>${header}</tr></thead>
            <tbody>${rows}</tbody>
        </table>
    `;
    previewEl.classList.remove("is-hidden");
}

function resetCsvPredictModal() {
    csvPredictState = { loading: false, message: "", error: "", csvBase64: null, lastPreview: null };
    renderCsvPredictStatus("");
    renderCsvPredictSummary(null);
    renderCsvPredictPreview(null);
    toggleCsvPredictDownload(false);
    updateCsvPredictTaskHelp();
    const fileInput = document.getElementById("csv-predict-file");
    if (fileInput) fileInput.value = "";
    const offlineNote = document.getElementById("csv-predict-offline-note");
    if (offlineNote) {
        offlineNote.classList.toggle("is-hidden", apiState.connected);
    }
}

function closeCsvPredictModal() {
    const overlay = document.getElementById("csv-predict-modal");
    if (!overlay) return;
    overlay.classList.add("is-hidden");
    document.body.style.overflow = "";
}

function openCsvPredictModal() {
    const overlay = document.getElementById("csv-predict-modal");
    if (!overlay) return;
    overlay.classList.remove("is-hidden");
    document.body.style.overflow = "hidden";
    resetCsvPredictModal();
    if (!apiState.connected) {
        renderCsvPredictStatus("Esta función requiere la API activa. Ejecuta run_all.bat o levanta la API en el puerto 8001.", true);
    }
}

function downloadCsvResult() {
    if (!csvPredictState.csvBase64) return;
    const link = document.createElement("a");
    link.href = `data:text/csv;base64,${csvPredictState.csvBase64}`;
    link.download = `predicciones_${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

async function submitCsvPrediction() {
    const taskInput = document.getElementById("csv-predict-task");
    const fileInput = document.getElementById("csv-predict-file");
    if (!taskInput || !fileInput) return;
    const file = fileInput.files?.[0];
    const task = taskInput.value;
    const taskConfig = getCsvPredictTaskConfig(task);
    if (!file) {
        renderCsvPredictStatus("Selecciona un archivo CSV antes de enviar.", true);
        return;
    }
    if (!apiState.connected) {
        renderCsvPredictStatus("Esta función requiere la API activa. Ejecuta run_all.bat o levanta la API en el puerto 8001.", true);
        return;
    }
    setCsvPredictLoading(true);
    renderCsvPredictStatus("Validando columnas del CSV...");
    try {
        const missingColumns = await getMissingCsvColumns(file, taskConfig.requiredColumns);
        if (missingColumns.length) {
            throw new Error(`Faltan columnas requeridas para ${taskConfig.label}: ${missingColumns.join(", ")}.`);
        }
        renderCsvPredictStatus("Enviando CSV a la API...");
        const formData = new FormData();
        formData.append("file", file);
        formData.append("task", task);
        const result = await fetchFormDataWithTimeout(`${getCurrentApiBaseUrl()}/predict/batch`, formData, 20000);
        csvPredictState.csvBase64 = result.csv_base64;
        csvPredictState.lastPreview = result.preview;
        renderCsvPredictSummary(result.summary);
        renderCsvPredictPreview(result.preview);
        toggleCsvPredictDownload(Boolean(result.csv_base64));
        const fallbackMessage = result.mode === "fallback"
            ? " Modo fallback: predicción basada en datos estáticos/reglas simples."
            : " Modo API: predicción desde endpoint real.";
        renderCsvPredictStatus(`Predicción completa: ${result.rows_processed} filas procesadas.${fallbackMessage}`);
    } catch (err) {
        renderCsvPredictStatus(`Error: ${err.message}`, true);
        console.error("Error predict batch CSV:", err);
        renderCsvPredictSummary(null);
        renderCsvPredictPreview(null);
        toggleCsvPredictDownload(false);
    } finally {
        setCsvPredictLoading(false);
    }
}

function setupCsvPredictModal() {
    const openButton = document.getElementById("csv-predict-button");
    const closeButton = document.getElementById("csv-predict-close");
    const overlay = document.getElementById("csv-predict-modal");
    const submitButton = document.getElementById("csv-predict-submit");
    const downloadButton = document.getElementById("csv-predict-download");
    const taskInput = document.getElementById("csv-predict-task");

    setupCsvPredictTaskOptions();
    updateCsvPredictTaskHelp();

    if (openButton) {
        openButton.addEventListener("click", openCsvPredictModal);
    }
    if (closeButton) {
        closeButton.addEventListener("click", closeCsvPredictModal);
    }
    if (overlay) {
        overlay.addEventListener("click", (event) => {
            if (event.target === overlay) {
                closeCsvPredictModal();
            }
        });
    }
    if (submitButton) {
        submitButton.addEventListener("click", submitCsvPrediction);
    }
    if (downloadButton) {
        downloadButton.addEventListener("click", downloadCsvResult);
    }
    if (taskInput) {
        taskInput.addEventListener("change", () => {
            updateCsvPredictTaskHelp();
            renderCsvPredictSummary(null);
            renderCsvPredictPreview(null);
            toggleCsvPredictDownload(false);
            csvPredictState.csvBase64 = null;
        });
    }
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeCsvPredictModal();
        }
    });
}

async function fetchJsonWithTimeout(url, options = {}, timeoutMs = API_TIMEOUT_MS) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal,
            headers: {
                "Content-Type": "application/json",
                ...(options.headers || {}),
            },
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    } finally {
        window.clearTimeout(timer);
    }
}

async function fetchFormDataWithTimeout(url, formData, timeoutMs = API_TIMEOUT_MS) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(url, {
            method: "POST",
            body: formData,
            signal: controller.signal,
        });
        if (!response.ok) {
            const payload = await response.text();
            throw new Error(`HTTP ${response.status}: ${payload || response.statusText}`);
        }
        return response.json();
    } finally {
        window.clearTimeout(timer);
    }
}

function getCurrentApiBaseUrl() {
    return window.API_BASE_URL || API_BASE_URL;
}

async function apiFetch(path, options = {}, timeoutMs = API_TIMEOUT_MS) {
    return fetchJsonWithTimeout(`${getCurrentApiBaseUrl()}${path}`, options, timeoutMs);
}

function apiPerformanceLabel(modelInfo) {
    const accuracy = Number(modelInfo?.performance?.test_accuracy);
    if (!Number.isFinite(accuracy)) return "";
    return ` · acc ${(accuracy * 100).toFixed(1)}%`;
}

async function checkApiStatus() {
    const apiHosts = ["http://127.0.0.1:8001", "http://localhost:8001"];

    for (const host of apiHosts) {
        try {
            console.log(`Probando conexión API en ${host}...`);

            let health = null;
            try {
                const response = await fetch(`${host}/health`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    signal: AbortSignal.timeout(2200)
                });
                if (response.ok) {
                    health = await response.json();
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            } catch (healthError) {
                console.warn(`Endpoint /health falló en ${host}:`, healthError.message);
                try {
                    const response = await fetch(`${host}/`, {
                        method: 'GET',
                        headers: { 'Content-Type': 'application/json' },
                        signal: AbortSignal.timeout(2200)
                    });
                    if (response.ok) {
                        health = await response.json();
                    } else {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                } catch (rootError) {
                    console.warn(`Endpoint raíz también falló en ${host}:`, rootError.message);
                    continue; // Probar siguiente host
                }
            }

            // Si llegamos aquí, la conexión funcionó
            console.log(`API conectada exitosamente en ${host}`);

            let modelInfo = null;
            try {
                const response = await fetch(`${host}/api/v1/model-info`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    signal: AbortSignal.timeout(2600)
                });
                if (response.ok) {
                    modelInfo = await response.json();
                }
            } catch (modelError) {
                console.warn("Modelo API no disponible:", modelError.message);
            }

            // Actualizar API_BASE_URL global y estado
            window.API_BASE_URL = host;
            apiState = {
                connected: true,
                mode: "online",
                health,
                modelInfo,
                error: null,
                activeBaseUrl: host,
            };

            const modelLabel = modelInfo?.name ? ` · ${modelInfo.name}` : "";
            setApiStatus("online", `Modo API${apiPerformanceLabel(modelInfo)}`, `API conectada en ${host}${modelLabel}`);
            updatePredictorModeNote("Modo API conectado. El predictor intenta la API primero y usa fallback estático si falla.");
            if (document.getElementById("home-team")?.value && document.getElementById("away-team")?.value) {
                renderMatchPrediction();
            }
            return apiState;

        } catch (err) {
            console.error(`Error probando ${host}:`, err.message);
            continue; // Probar siguiente host
        }
    }

    // Si ningún host funcionó
    apiState = {
        connected: false,
        mode: "offline",
        health: null,
        modelInfo: null,
        error: new Error("No se pudo conectar a ningún host API"),
        activeBaseUrl: null,
    };
    setApiStatus("offline", "Modo offline", `API no disponible. Probados: ${apiHosts.join(', ')}`);
    updatePredictorModeNote("Modo offline: usando predicciones estáticas del dashboard.");
    return apiState;
}

function updatePredictorModeNote(text, isError = false) {
    const note = document.getElementById("predictor-api-note");
    if (!note) return;
    note.textContent = text;
    note.classList.toggle("is-error", Boolean(isError));
}

function updateXgModeNote(text, isError = false) {
    const note = document.getElementById("xg-api-note");
    if (!note) return;
    note.textContent = text;
    note.classList.toggle("is-error", Boolean(isError));
}

// Función global para refrescar estado API (útil para debugging)
window.refreshApiStatus = async function() {
    console.log("Refrescando estado API...");
    await checkApiStatus();
    console.log("Estado API actualizado:", apiState);
};

// Auto-refresh cada 10 segundos (siempre, no solo cuando visible)
setInterval(async () => {
    await checkApiStatus();
}, 10000);
function setupCinemaIntro() {
    const video   = document.getElementById('cinema-video');
    const master  = document.querySelector('.intro-visual-master');
    const opening = document.querySelector('.cinema-opening');

    // — Video: activar hero.mp4 con manejo robusto para archivos locales y Netlify
    if (video) {
        const activateVideo = () => {
            video.classList.add('cinema-loaded');
            console.log('✓ Cinema: video hero.mp4 activo — ' + video.videoWidth + 'x' + video.videoHeight);
        };

        // Escuchar múltiples eventos para máxima compatibilidad
        video.addEventListener('canplay',    activateVideo, { once: true });
        video.addEventListener('loadeddata', activateVideo, { once: true });

        // Si ya está listo (p.ej. carga instantánea desde caché)
        if (video.readyState >= 2) activateVideo();

        // Forzar play() explícito (necesario en algunos browsers para archivos locales)
        const tryPlay = video.play();
        if (tryPlay !== undefined) {
            tryPlay.catch(err => {
                console.warn('○ Cinema autoplay bloqueado:', err.message, '— el video se activará en la próxima interacción.');
                // Fallback: activar en la primera interacción del usuario
                document.addEventListener('click',     () => video.play(), { once: true });
                document.addEventListener('touchstart', () => video.play(), { once: true });
                document.addEventListener('keydown',   () => video.play(), { once: true });
            });
        }

        video.addEventListener('error', (e) => {
            console.log('○ Cinema: error al cargar hero.mp4 —', e.message || 'aurora fallback activa');
        }, { once: true });
    }

    // — Scroll: fade suave del título "DEL DATO AL GOL" + parallax del fondo
    let ticking = false;
    window.addEventListener('scroll', () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
            const sy = window.scrollY;
            const vh = window.innerHeight;

            // 1. "DEL DATO AL GOL" desaparece suavemente con lift parallax
            if (opening) {
                if (sy < vh) {
                    const p    = Math.min(sy / (vh * 0.55), 1);
                    const ease = 1 - (1 - p) * (1 - p);   // ease-out cuadrático
                    opening.style.opacity       = String(Math.max(0, 1 - ease * 1.2));
                    opening.style.transform     = `translateY(${-sy * 0.18}px)`;
                    opening.style.pointerEvents = p >= 1 ? 'none' : '';
                } else {
                    opening.style.opacity   = '0';
                    opening.style.transform = `translateY(-${vh * 0.18}px)`;
                }
            }

            // 2. Parallax + micro-zoom del fondo visual
            if (master && sy < vh * 2) {
                const shift = sy * 0.12;
                const scale = 1 + (sy / vh) * 0.04;
                master.style.transform = `translateY(${-shift}px) scale(${scale})`;
            }

            // 3. Performance: ocultar cuando el usuario está lejos del hero
            if (master) {
                master.style.visibility = (sy > vh * 2.5) ? 'hidden' : 'visible';
            }

            ticking = false;
        });
    }, { passive: true });
}

// ── HERO STAGGER REVEAL ───────────────────────────────────
function setupHeroStagger() {
    const stagger = document.querySelector('.hero-stagger');
    if (!stagger) return;

    const io = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting) {
            // Un poco de delay para el feeling cinemático
            setTimeout(() => {
                stagger.classList.add('revealed');
                setupHeroTextReveal();
            }, 150);
            io.disconnect();
        }
    }, { threshold: 0.25 });

    io.observe(document.querySelector('.hero-reveal') || stagger);
}

// ── COUNT-UP ANIMATION ───────────────────────────────────
// ── HERO TEXT REVEAL ────────────────────────────────────────────────
function setupHeroTextReveal() {
    const words = document.querySelectorAll(".word");
    words.forEach((word, i) => {
        window.setTimeout(() => {
            word.classList.add("reveal");
        }, i * 150);
    });
}

function countUp(el, targetStr, duration = 1400) {
    if (!el) return;
    const m = String(targetStr).match(/^([+\-]?)(\d+\.?\d*)(.*)$/);
    if (!m) { el.textContent = targetStr; return; }
    const prefix  = m[1];
    const target  = parseFloat(m[2]);
    const suffix  = m[3];
    const decimals = m[2].includes('.') ? m[2].split('.')[1].length : 0;
    const t0 = performance.now();
    const tick = (now) => {
        const p = Math.min((now - t0) / duration, 1);
        const ease = 1 - Math.pow(1 - p, 3);
        el.textContent = prefix + (target * ease).toFixed(decimals) + suffix;
        if (p < 1) requestAnimationFrame(tick);
        else el.textContent = targetStr;
    };
    requestAnimationFrame(tick);
}

function animateBarWidth(el, pct, delay = 0) {
    if (!el) return;
    setTimeout(() => { el.style.width = pct + "%"; }, delay);
}

// ── NAVBAR ───────────────────────────────────────────────
function setupNavbar() {
    const navbar   = document.getElementById("navbar");
    const links    = document.querySelectorAll(".nav-link[data-section]");
    const sections = document.querySelectorAll("section[id],.conclusions-section[id],.xg-spotlight[id]");
    const burger   = document.getElementById("nav-burger");
    const navList  = document.getElementById("nav-links");

    window.addEventListener("scroll", () => {
        navbar.classList.toggle("scrolled", window.scrollY > 80);
    }, { passive: true });

    // Smooth scroll with nav offset
    document.querySelectorAll('a[href^="#"]').forEach(a => {
        a.addEventListener("click", e => {
            const target = document.querySelector(a.getAttribute("href"));
            if (!target) return;
            e.preventDefault();
            window.scrollTo({ top: target.getBoundingClientRect().top + scrollY - parseInt(getComputedStyle(document.documentElement).getPropertyValue("--nav-h") || "68"), behavior: "smooth" });
        });
    });

    // Active nav link
    const navObserver = new IntersectionObserver(entries => {
        entries.forEach(en => {
            if (!en.isIntersecting) return;
            links.forEach(l => l.classList.toggle("active", l.dataset.section === en.target.id));
        });
    }, { rootMargin: "-40% 0px -55% 0px", threshold: 0.15 });

    sections.forEach(s => navObserver.observe(s));

    // Burger
    if (burger && navList) {
        burger.addEventListener("click", () => {
            const open = navList.classList.toggle("nav-links--open");
            burger.setAttribute("aria-expanded", open);
        });
        navList.querySelectorAll(".nav-link").forEach(l => {
            l.addEventListener("click", () => navList.classList.remove("nav-links--open"));
        });
    }
}

// ── REVEAL ANIMATIONS ────────────────────────────────────
function setupRevealAnimations() {
    const io = new IntersectionObserver(entries => {
        entries.forEach(en => {
            if (en.isIntersecting) {
                en.target.classList.add("visible");
                io.unobserve(en.target);
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll("[data-reveal], .model-block, .eval-grid, .eda-row, .eda-full, .clustering-wrap").forEach(el => io.observe(el));
}

// ── PIPELINE STEP ANIMATIONS ─────────────────────────────
function setupPipelineAnimations() {
    const io = new IntersectionObserver(entries => {
        entries.forEach(en => {
            if (en.isIntersecting) {
                const steps = en.target.querySelectorAll(".pipeline-step");
                steps.forEach((s, i) => {
                    setTimeout(() => s.classList.add("visible"), i * 130);
                });
                io.unobserve(en.target);
            }
        });
    }, { threshold: 0.2 });
    const flow = document.querySelector(".pipeline-flow");
    if (flow) io.observe(flow);
}

function setupPremiumVideoCards() {
    const cards = document.querySelectorAll("[data-video-card]");
    cards.forEach(card => {
        const video = card.querySelector(".premium-video");
        const playBtn = card.querySelector(".premium-video-play");
        if (!video || !playBtn) return;

        const syncState = () => {
            const playing = !video.paused && !video.ended;
            card.classList.toggle("is-playing", playing);
        };

        playBtn.addEventListener("click", () => {
            if (video.paused || video.ended) {
                const playPromise = video.play();
                if (playPromise && typeof playPromise.catch === "function") {
                    playPromise.catch(() => {
                        // El navegador mostrará controles nativos si bloquea autoplay.
                    });
                }
            } else {
                video.pause();
            }
            syncState();
        });

        video.addEventListener("play", syncState);
        video.addEventListener("pause", syncState);
        video.addEventListener("ended", syncState);
        syncState();
    });
}


// ── HELPERS ───────────────────────────────────────────────
function clampValue(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

// Función logística (modelo xG simplificado)
function calculateXG(distance, angle) {
    const b0 = -1.5;
    const b1 = -0.08;   // distancia (más lejos = menor probabilidad)
    const b2 = 0.04;    // ángulo (más abierto = mayor probabilidad)

    const z = b0 + b1 * distance + b2 * angle;
    return 1 / (1 + Math.exp(-z));
}

// Generar variables realistas
function generateShot() {
    const distance = Math.random() * 30; // metros
    const angle = Math.random() * 90;    // grados
    return { distance, angle };
}

function buildXgApiPayload(shot) {
    const angleRad = (Number(shot.angle || 0) * Math.PI) / 180;
    const x = clampValue(100 - (Number(shot.distance || 0) / 105) * 100, 70, 99);
    const yDirection = Math.random() < 0.5 ? -1 : 1;
    const y = clampValue(50 + yDirection * Math.sin(angleRad) * 24, 8, 92);
    const isBigChance = shot.distance <= 13 && shot.angle <= 35 ? 1 : 0;
    const isPenalty = shot.distance <= 12 && shot.angle <= 8 && Math.random() < 0.08 ? 1 : 0;
    return {
        x,
        y,
        shot_distance: Number(shot.distance || 0),
        shot_angle: angleRad,
        is_big_chance: isBigChance,
        is_header: Math.random() < 0.16 ? 1 : 0,
        is_right_foot: Math.random() < 0.52 ? 1 : 0,
        is_left_foot: Math.random() < 0.35 ? 1 : 0,
        is_penalty: isPenalty,
        is_volley: Math.random() < 0.08 ? 1 : 0,
        first_touch: Math.random() < 0.18 ? 1 : 0,
        from_corner: Math.random() < 0.10 ? 1 : 0,
        is_counter: Math.random() < 0.12 ? 1 : 0,
    };
}

async function predictXgWithApiOrFallback(shot) {
    if (!apiState.connected) {
        updateXgModeNote("Modo offline: xG calculado con fallback local.");
        return calculateXG(shot.distance, shot.angle);
    }

    try {
        updateXgModeNote("Modo API: consultando /predict/xg...");
        const payload = buildXgApiPayload(shot);
        const result = await apiFetch("/predict/xg", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        const xg = Number(result?.xg);
        if (!Number.isFinite(xg)) throw new Error("Respuesta xG invalida.");
        const source = result.source === "heuristic_fallback" ? "fallback API" : "modelo API";
        updateXgModeNote(`Modo API: xG desde ${source}.`);
        return clampValue(xg, 0.001, 0.999);
    } catch (err) {
        updateXgModeNote("API xG no disponible: usando fallback local.", true);
        console.warn("Fallo /predict/xg:", err.message);
        return calculateXG(shot.distance, shot.angle);
    }
}



function setupGoalSimulation() {
    const shootBtn = document.getElementById("shoot-btn");
    const scoreEl = document.getElementById("score");
    const xgEl = document.getElementById("xg-value");
    const shotInfoEl = document.getElementById("shot-info");
    const ball = document.getElementById("ball");
    const pitch = document.querySelector(".pitch-container");

    if (!shootBtn || !scoreEl || !xgEl || !ball || !pitch) return;

    let home = 0;
    let busy = false;

    const resetBall = () => {
        ball.style.transition = "none";
        ball.style.top = "";
        ball.style.bottom = "22px";
        ball.style.left = "50%";
        ball.style.transform = "translateX(-50%) scale(1)";
        void ball.offsetHeight;
        ball.style.transition = "top .7s ease,left .7s ease,bottom .7s ease,transform .7s ease";
    };

    const flashPitch = () => {
        pitch.classList.add("pitch-goal-flash");
        window.setTimeout(() => pitch.classList.remove("pitch-goal-flash"), 750);
    };

    shootBtn.addEventListener("click", async () => {
        if (busy) return;
        busy = true;

        const { distance, angle } = generateShot();
        xgEl.textContent = "xG: ...";
        const xg = await predictXgWithApiOrFallback({ distance, angle });
        xgEl.textContent = `xG: ${xg.toFixed(2)}`;
        if (shotInfoEl) {
            const isCentral = angle > 30 ? 1 : 0;
            const interaction = distance * angle;
            shotInfoEl.innerHTML =
                `Distancia: ${distance.toFixed(1)}m | Ángulo: ${angle.toFixed(1)}°<br>` +
                `Tipo de tiro: ${isCentral ? "Central" : "Lateral"} | Interacción: ${interaction.toFixed(1)}`;
        }
        const targetLeft = clampValue(12 + (angle / 90) * 76, 12, 88);
        const targetTop = clampValue(12 + (distance / 30) * 12, 12, 24);

        ball.style.bottom = "auto";
        ball.style.top = `${targetTop}%`;
        ball.style.left = `${targetLeft}%`;
        ball.style.transform = "translate(-50%, -50%) scale(1.18)";

        window.setTimeout(() => {
            if (Math.random() < xg) {
                home += 1;
                scoreEl.textContent = `${home} - 0`;
                flashPitch();
            }

            resetBall();
            busy = false;
        }, 700);
    });
}

function setText(id, txt) { const el = document.getElementById(id); if (el) el.textContent = txt; }
function formatPct(v, d = 1) { return `${Number(v).toFixed(d)}%`; }
function formatDec(v, d = 3) { return Number(v).toFixed(d); }
function formatDate(date) {
    const parsed = new Date(date);
    if (Number.isNaN(parsed.getTime())) return date;
    return parsed.toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
    });
}

function normalizeTeamName(team) {
    const cleanTeam = String(team || "").trim();
    return TEAM_MAP[cleanTeam] || cleanTeam;
}

function slugifyTeam(team) {
    return String(team || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");
}

function getTeamLogo(team) {
    const normalizedTeam = normalizeTeamName(team);
    const teamId = TEAM_LOGO_IDS[normalizedTeam];
    if (!teamId) {
        console.warn("No ID for team:", team, "=> normalized as:", normalizedTeam);
        return LOGO_PLACEHOLDER;
    }
    return `https://crests.football-data.org/${teamId}.png`;
}

function validateLogo(team) {
    const normalizedTeam = normalizeTeamName(team);
    if (!TEAM_LOGO_IDS[normalizedTeam]) {
        console.warn("No logo ID found for:", team, "=> normalized as:", normalizedTeam);
        return false;
    }
    return true;
}

function getTeamStadium(team) {
    const normalizedTeam = normalizeTeamName(team);
    return TEAM_STADIUMS[normalizedTeam] || TEAM_STADIUMS[team] || "Premier League Stadium";
}

function buildFeaturedMatches() {
    const predictionMap = new Map(
        (dashboardData.predictions || []).map(match => [`${match.home}__${match.away}`, match])
    );

    const sourceMatches = (dashboardData.match_shot_options || [])
        .map(match => {
            const prediction = predictionMap.get(`${match.home_team}__${match.away_team}`);
            if (!prediction) return null;
            return {
                homeTeam: match.home_team,
                awayTeam: match.away_team,
                date: match.date,
                stadium: getTeamStadium(match.home_team),
                probabilities: {
                    home: Number(prediction.prob_home) / 100,
                    draw: Number(prediction.prob_draw) / 100,
                    away: Number(prediction.prob_away) / 100,
                },
                estimatedGoals: Number(prediction.est_goals),
                confidence: Math.max(
                    Number(prediction.prob_home),
                    Number(prediction.prob_draw),
                    Number(prediction.prob_away),
                ),
            };
        })
        .filter(Boolean)
        .sort((a, b) => new Date(a.date) - new Date(b.date));

    return sourceMatches.slice(-12).reverse();
}

function createProbabilityRow(label, className, value) {
    return `
        <div class="prob-row">
            <span class="prob-label ${className}">${label}</span>
            <div class="prob-bar">
                <div class="prob-bar-fill ${className}" style="width:${(value * 100).toFixed(1)}%"></div>
            </div>
            <span class="prob-value">${(value * 100).toFixed(0)}%</span>
        </div>
    `;
}

function setTeamLogo(imgId, teamName) {
    const image = document.getElementById(imgId);
    if (!image) return;

    const normalizedTeam = normalizeTeamName(teamName);
    const logoUrl = getTeamLogo(normalizedTeam);
    const hasKnownLogo = validateLogo(normalizedTeam);

    image.alt = `Logo ${normalizedTeam}`;
    image.classList.toggle("is-missing", !hasKnownLogo);
    image.onload = null;

    image.onerror = () => {
        console.warn("Logo failed to load for:", normalizedTeam, "using placeholder instead.");
        image.onerror = null;
        image.src = LOGO_PLACEHOLDER;
        image.classList.add("is-missing");
    };
    image.src = logoUrl;
}

function updateTeams(homeTeam, awayTeam) {
    const home = normalizeTeamName(homeTeam);
    const away = normalizeTeamName(awayTeam);

    console.log("HOME:", home, getTeamLogo(home));
    console.log("AWAY:", away, getTeamLogo(away));

    setText("home-team-name", home);
    setText("away-team-name", away);

    setTeamLogo("home-logo", home);
    setTeamLogo("away-logo", away);
}

function createMatchCard(match) {
    return `
        <article class="match-card" data-reveal>
            <div class="match-card-top">
                <div class="match-kickoff">
                    <span class="match-kicker">Matchday View</span>
                    <span class="match-date">${formatDate(match.date)}</span>
                </div>
                <span class="match-badge">
                    <span class="match-badge-dot"></span>
                    Modelo activo
                </span>
            </div>

            <div class="match-teams">
                <div class="team-face">
                    <div class="team-crest-wrap">
                        <img class="team-crest" src="${getTeamLogo(match.homeTeam) || ''}" alt="${normalizeTeamName(match.homeTeam)} logo" loading="lazy">
                    </div>
                    <span class="team-name">${match.homeTeam}</span>
                </div>

                <div class="match-versus">VS</div>

                <div class="team-face">
                    <div class="team-crest-wrap">
                        <img class="team-crest" src="${getTeamLogo(match.awayTeam) || ''}" alt="${normalizeTeamName(match.awayTeam)} logo" loading="lazy">
                    </div>
                    <span class="team-name">${match.awayTeam}</span>
                </div>
            </div>

            <div class="match-meta">
                <div class="match-meta-row">
                    <span class="match-meta-icon">📅</span>
                    <span>${formatDate(match.date)}</span>
                </div>
                <div class="match-meta-row">
                    <span class="match-meta-icon">🏟</span>
                    <span>${match.stadium}</span>
                </div>
            </div>

            <div class="probability-stack">
                ${createProbabilityRow("H", "home", match.probabilities.home)}
                ${createProbabilityRow("D", "draw", match.probabilities.draw)}
                ${createProbabilityRow("A", "away", match.probabilities.away)}
            </div>

            <div class="match-card-footer">
                <div>
                    <div class="match-goals-label">Goles esperados</div>
                    <div class="match-goals-value">${match.estimatedGoals.toFixed(2)}</div>
                </div>
                <div class="match-card-note">Fixture ${slugifyTeam(match.homeTeam)}-${slugifyTeam(match.awayTeam)}</div>
            </div>
        </article>
    `;
}

function renderFeaturedMatches() {
    const grid = document.getElementById("matches-grid");
    if (!grid || !dashboardData) return;

    const featuredMatches = buildFeaturedMatches();
    if (!featuredMatches.length) {
        grid.innerHTML = "<p class='match-card-note'>No hay partidos disponibles para mostrar.</p>";
        return;
    }

    grid.innerHTML = featuredMatches.map(createMatchCard).join("");
    grid.querySelectorAll(".match-card").forEach((card, index) => {
        window.setTimeout(() => card.classList.add("visible"), 80 * index);
    });
}

// ── HERO HYDRATION ────────────────────────────────────────
function hydrateHero() {
    const acc = dashboardData.match_accuracy;
    const gap = dashboardData.project_summary.ventaja_sobre_benchmark;

    const heroAcc = document.getElementById("hero-accuracy");
    const heroGap = document.getElementById("hero-gap");

    if (heroAcc) {
        // Watch hero-stats entering viewport to trigger count-up
        new IntersectionObserver(entries => {
            if (entries[0].isIntersecting) {
                countUp(heroAcc, formatPct(acc));
                if (heroGap) countUp(heroGap, `+${gap.toFixed(1)}pp`);
                entries[0].target._triggered = true;
            }
        }, { threshold: 0.5 }).observe(document.querySelector(".hero-stats") || heroAcc);
    }
}

// ── VALUE STRIP ───────────────────────────────────────────
function hydrateValueStrip() {
    const shots = dashboardData.shots ? dashboardData.shots.length : null;
    const auc   = dashboardData.xg_metrics.auc_roc;

    if (shots !== null) {
        const el = document.getElementById("val-shots");
        if (el) {
            const io = new IntersectionObserver(([en]) => {
                if (en.isIntersecting) { countUp(el, shots >= 1000 ? `${Math.round(shots/1000)}K` : String(shots)); io.disconnect(); }
            }, { threshold: .5 });
            io.observe(el);
        }
    }
    if (auc != null) {
        const el = document.getElementById("val-auc");
        if (el) {
            const io = new IntersectionObserver(([en]) => {
                if (en.isIntersecting) { countUp(el, auc.toFixed(3)); io.disconnect(); }
            }, { threshold: .5 });
            io.observe(el);
        }
    }
}

// ── xG SPOTLIGHT ──────────────────────────────────────────
function hydrateXgSpotlight() {
    const xg = dashboardData.xg_metrics;
    const fields = [
        ["xg-auc-display",       formatDec(xg.auc_roc)],
        ["xg-precision-display", formatPct(xg.precision * 100)],
        ["xg-recall-display",    formatPct(xg.recall * 100)],
        ["xg-f1-display",        formatPct(xg.f1 * 100)],
    ];
    fields.forEach(([id, val]) => {
        const el = document.getElementById(id);
        if (!el) return;
        const io = new IntersectionObserver(([en]) => {
            if (en.isIntersecting) { countUp(el, val); io.disconnect(); }
        }, { threshold: .5 });
        io.observe(el);
    });
}

function initializeXgExplorer() {
    const teamEl = document.getElementById("xg-team-filter");
    const playerEl = document.getElementById("xg-player-filter");
    const shotTypeEl = document.getElementById("xg-shot-type-filter");
    if (!teamEl || !playerEl || !shotTypeEl) return;

    populateXgTeamOptions(teamEl);
    teamEl.value = XG_DASHBOARD_STATE.team;
    shotTypeEl.value = XG_DASHBOARD_STATE.shotType;
    refreshXgPlayerOptions();

    if (!teamEl.dataset.bound) {
        teamEl.addEventListener("change", () => {
            XG_DASHBOARD_STATE.team = teamEl.value || "all";
            refreshXgPlayerOptions();
            renderXgExplorer();
        });
        teamEl.dataset.bound = "1";
    }

    if (!playerEl.dataset.bound) {
        playerEl.addEventListener("change", () => {
            XG_DASHBOARD_STATE.player = playerEl.value || "all";
            renderXgExplorer();
        });
        playerEl.dataset.bound = "1";
    }

    if (!shotTypeEl.dataset.bound) {
        shotTypeEl.addEventListener("change", () => {
            XG_DASHBOARD_STATE.shotType = shotTypeEl.value || "all";
            refreshXgPlayerOptions();
            renderXgExplorer();
        });
        shotTypeEl.dataset.bound = "1";
    }

    renderXgExplorer();
}

function populateXgTeamOptions(teamEl) {
    const teams = [...new Set(
        getPreparedXgShots()
            .map(shot => normalizeTeamName(shot.team_name))
            .filter(team => team && team !== "Equipo no disponible")
    )].sort((a, b) => a.localeCompare(b, "es"));

    teamEl.innerHTML = "";
    teamEl.add(new Option("Todos los equipos", "all"));
    teams.forEach(team => teamEl.add(new Option(team, team)));
}

function refreshXgPlayerOptions() {
    const playerEl = document.getElementById("xg-player-filter");
    if (!playerEl) return;

    const current = XG_DASHBOARD_STATE.player;
    const shots = getFilteredXgShots({ ...XG_DASHBOARD_STATE, player: "all" });
    const players = [...new Set(
        shots
            .map(shot => String(shot.player_name || "").trim())
            .filter(Boolean)
    )].sort((a, b) => a.localeCompare(b, "es"));

    playerEl.innerHTML = "";
    playerEl.add(new Option("Todos los jugadores", "all"));
    players.forEach(player => playerEl.add(new Option(player, player)));

    XG_DASHBOARD_STATE.player = players.includes(current) ? current : "all";
    playerEl.value = XG_DASHBOARD_STATE.player;
}

function getPreparedXgShots() {
    if (dashboardData._preparedXgShots) return dashboardData._preparedXgShots;

    const source = dashboardData.shots || dashboardData.shot_map_global || [];
    dashboardData._preparedXgShots = source
        .map(shot => normalizeXgShot(shot))
        .filter(Boolean);
    return dashboardData._preparedXgShots;
}

function normalizeXgShot(shot) {
    const x = Number(shot.x);
    const y = Number(shot.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;

    const shotTypeKey = String(shot.shot_type_key || inferShotTypeKey(shot));
    const zoneKey = String(shot.zone_key || classifyZoneKey(x, y));
    const teamName = normalizeTeamName(shot.team_name || "Equipo no disponible");
    const playerName = String(shot.player_name || "").trim() || "Jugador no identificado";
    const distanceMeters = Number(shot.distance_to_goal_m);
    const angleDegrees = Number(shot.angle_degrees);

    return {
        ...shot,
        x,
        y,
        is_goal: Number(shot.is_goal) === 1 ? 1 : 0,
        xg_probability: Number(shot.xg_probability) || 0,
        distance_to_goal_m: Number.isFinite(distanceMeters) ? distanceMeters : computeShotDistanceMeters(x, y),
        angle_degrees: Number.isFinite(angleDegrees) ? angleDegrees : computeShotAngleDegrees(x, y),
        team_name: teamName,
        player_name: playerName,
        shot_type_key: shotTypeKey,
        shot_type: shot.shot_type || XG_SHOT_TYPE_LABELS[shotTypeKey] || "Otro",
        zone_key: zoneKey,
        zone_name: shot.zone_name || zoneKeyToLabel(zoneKey),
    };
}

function inferShotTypeKey(shot) {
    if (Number(shot.is_penalty) === 1) return "penalty";
    if (Number(shot.is_header) === 1) return "header";
    if (Number(shot.is_left_foot) === 1 || Number(shot.is_right_foot) === 1) return "foot";
    return "other";
}

function classifyZoneKey(x, y) {
    if (x >= 94.5 && y >= 36.8 && y <= 63.2) return "small_box";
    if (x >= 83.5 && y >= 21.1 && y <= 78.9) return "penalty_box";
    return "outside_box";
}

function zoneKeyToLabel(zoneKey) {
    const hit = XG_ZONE_DEFINITIONS.find(zone => zone.key === zoneKey);
    return hit ? hit.label : "Fuera del área";
}

function computeShotDistanceMeters(x, y) {
    const longitudinal = ((100 - x) / 100) * 105;
    const lateral = (Math.abs(50 - y) / 100) * 68;
    return Math.sqrt((longitudinal ** 2) + (lateral ** 2));
}

function computeShotAngleDegrees(x, y) {
    const longitudinal = ((100 - x) / 100) * 105;
    const lateral = (Math.abs(50 - y) / 100) * 68;
    return Math.abs(Math.atan2(lateral, longitudinal) * (180 / Math.PI));
}

function getFilteredXgShots(filters = XG_DASHBOARD_STATE) {
    const { team = "all", player = "all", shotType = "all" } = filters;
    return getPreparedXgShots().filter(shot => {
        if (team !== "all" && shot.team_name !== team) return false;
        if (player !== "all" && shot.player_name !== player) return false;
        if (shotType !== "all" && shot.shot_type_key !== shotType) return false;
        return true;
    });
}

function renderXgExplorer() {
    if (!document.getElementById("xg-density-chart")) return;

    const shots = getFilteredXgShots();
    const goals = [];
    const misses = [];

    shots.forEach(shot => {
        if (Number(shot.is_goal) === 1) goals.push(shot);
        else misses.push(shot);
    });

    updateXgSummary(shots);
    renderXgDensityChart(shots);
    renderXgScatterChart(misses, goals);
    renderXgGoalsHeatmapChart(goals);

    const zoneSummary = computeXgZoneSummary(shots);
    renderXgZoneChart(zoneSummary);
    renderXgZoneTable(zoneSummary);
    renderXgCalibrationExplorerChart(shots);
}

function updateXgSummary(shots) {
    const totalShots = shots.length;
    const totalGoals = shots.reduce((acc, shot) => acc + Number(shot.is_goal || 0), 0);
    const avgXg = totalShots
        ? shots.reduce((acc, shot) => acc + Number(shot.xg_probability || 0), 0) / totalShots
        : 0;
    const conversion = totalShots ? totalGoals / totalShots : 0;

    const summaryEl = document.getElementById("xg-filter-summary");
    const summaryParts = [];
    summaryParts.push(XG_DASHBOARD_STATE.team === "all" ? "todos los equipos" : XG_DASHBOARD_STATE.team);
    if (XG_DASHBOARD_STATE.player !== "all") summaryParts.push(XG_DASHBOARD_STATE.player);
    summaryParts.push(
        XG_DASHBOARD_STATE.shotType === "all"
            ? "todos los tipos de tiro"
            : XG_SHOT_TYPE_LABELS[XG_DASHBOARD_STATE.shotType].toLowerCase()
    );

    if (summaryEl) {
        summaryEl.textContent = totalShots
            ? `Mostrando ${totalShots.toLocaleString("es-CO")} tiros filtrados para ${summaryParts.join(" · ")}.`
            : `No hay tiros disponibles para ${summaryParts.join(" · ")}.`;
    }

    setText("xg-filter-shots", totalShots.toLocaleString("es-CO"));
    setText("xg-filter-goals", totalGoals.toLocaleString("es-CO"));
    setText("xg-filter-avgxg", formatPct(avgXg * 100));
    setText("xg-filter-conv", formatPct(conversion * 100));
}

function renderXgDensityChart(shots) {
    const targetId = "xg-density-chart";
    if (!shots.length) {
        renderEmptyPitchChart(targetId, "No hay tiros para construir el heatmap de densidad.");
        return;
    }

    Plotly.react(targetId, [{
        type: "histogram2d",
        x: shots.map(shot => shot.x),
        y: shots.map(shot => shot.y),
        histnorm: "probability",
        nbinsx: 18,
        nbinsy: 12,
        colorscale: XG_DENSITY_COLORSCALE,
        zsmooth: "best",
        opacity: 0.82,
        colorbar: {
            title: { text: "% tiros", font: { color: PITCH_THEME.axisText, size: 11 } },
            tickformat: ".1%",
            thickness: 12,
            len: 0.72,
            x: 1.02,
            bgcolor: "rgba(5,24,15,0.55)",
            bordercolor: "rgba(241,245,249,0.16)",
            tickcolor: PITCH_THEME.axisTextSoft,
            tickfont: { color: PITCH_THEME.axisText, size: 10 },
        },
        hovertemplate: "Profundidad: %{x:.1f}<br>Amplitud: %{y:.1f}<br>Densidad: %{z:.2%}<extra></extra>",
        showscale: true,
    }], buildXgPitchLayout({ margin: { t: 12, r: 62, b: 12, l: 12 } }), { responsive: true, displayModeBar: false });
}

function renderXgScatterChart(misses, goals) {
    const targetId = "xg-scatter-chart";
    if (!misses.length && !goals.length) {
        renderEmptyPitchChart(targetId, "No hay tiros para mostrar en el scatter plot.");
        return;
    }

    Plotly.react(targetId, [
        buildXgScatterTrace("No gol", misses, "rgba(248,113,113,.82)", "rgba(255,255,255,.22)"),
        buildXgScatterTrace("Gol", goals, "rgba(52,211,153,.92)", "rgba(255,255,255,.32)"),
    ], buildXgPitchLayout({
        showlegend: true,
        legend: {
            orientation: "h",
            x: 0,
            y: 1.08,
            xanchor: "left",
            bgcolor: "rgba(2,6,23,.62)",
        },
    }), { responsive: true, displayModeBar: false });
}

function buildXgScatterTrace(name, shots, color, lineColor) {
    return {
        type: "scatter",
        mode: "markers",
        name,
        x: shots.map(shot => shot.x),
        y: shots.map(shot => shot.y),
        marker: {
            size: shots.map(shot => Math.max(8, 7 + (Number(shot.xg_probability || 0) * 26))),
            color,
            opacity: 0.72,
            line: { color: lineColor, width: 1.1 },
        },
        customdata: shots.map(shot => ([
            shot.player_name,
            shot.team_name,
            shot.shot_type,
            Number(shot.distance_to_goal_m || 0),
            Number(shot.angle_degrees || 0),
            Number(shot.xg_probability || 0),
            Number(shot.is_goal) === 1 ? "Gol" : "No gol",
        ])),
        hovertemplate: "<b>%{customdata[6]}</b><br>%{customdata[0]} · %{customdata[1]}<br>Tipo: %{customdata[2]}<br>Distancia: %{customdata[3]:.1f} m<br>Ángulo: %{customdata[4]:.1f}°<br>xG: %{customdata[5]:.3f}<extra></extra>",
    };
}

function renderXgGoalsHeatmapChart(goals) {
    const targetId = "xg-goals-heatmap-chart";
    if (!goals.length) {
        renderEmptyPitchChart(targetId, "No hay goles con el filtro actual.");
        return;
    }

    Plotly.react(targetId, [{
        type: "histogram2d",
        x: goals.map(shot => shot.x),
        y: goals.map(shot => shot.y),
        histnorm: "probability",
        nbinsx: 16,
        nbinsy: 10,
        colorscale: [
            [0.00, "rgba(15,23,42,0.00)"],
            [0.18, "rgba(56,189,248,0.24)"],
            [0.52, "rgba(250,204,21,0.52)"],
            [1.00, "rgba(16,185,129,0.84)"],
        ],
        zsmooth: "best",
        opacity: 0.76,
        colorbar: {
            title: { text: "% goles", font: { color: PITCH_THEME.axisText, size: 11 } },
            tickformat: ".1%",
            thickness: 12,
            len: 0.72,
            x: 1.02,
            bgcolor: "rgba(5,24,15,0.55)",
            bordercolor: "rgba(241,245,249,0.16)",
            tickcolor: PITCH_THEME.axisTextSoft,
            tickfont: { color: PITCH_THEME.axisText, size: 10 },
        },
        hovertemplate: "Profundidad: %{x:.1f}<br>Amplitud: %{y:.1f}<br>Densidad de gol: %{z:.2%}<extra></extra>",
        showscale: true,
    }], buildXgPitchLayout({ margin: { t: 12, r: 62, b: 12, l: 12 } }), { responsive: true, displayModeBar: false });
}

function computeXgZoneSummary(shots) {
    return XG_ZONE_DEFINITIONS.map(zone => {
        const zoneShots = shots.filter(shot => shot.zone_key === zone.key);
        const shotCount = zoneShots.length;
        const goals = zoneShots.reduce((acc, shot) => acc + Number(shot.is_goal || 0), 0);
        const avgXg = shotCount
            ? zoneShots.reduce((acc, shot) => acc + Number(shot.xg_probability || 0), 0) / shotCount
            : 0;
        const conversion = shotCount ? goals / shotCount : 0;

        return {
            ...zone,
            shots: shotCount,
            goals,
            avgXg,
            conversion,
        };
    });
}

function renderXgZoneChart(summary) {
    const targetId = "xg-zone-chart";
    const totalShots = summary.reduce((acc, zone) => acc + zone.shots, 0);
    if (!totalShots) {
        renderEmptyDarkChart(targetId, "No hay datos suficientes para comparar zonas.");
        return;
    }

    const labels = summary.map(zone => zone.label);
    const counts = summary.map(zone => [zone.shots, zone.goals]);
    const maxPct = Math.max(
        12,
        ...summary.map(zone => Math.max(zone.avgXg * 100, zone.conversion * 100))
    );

    Plotly.react(targetId, [
        {
            type: "bar",
            x: labels,
            y: summary.map(zone => zone.avgXg * 100),
            name: "xG promedio",
            marker: {
                color: "rgba(56,189,248,.86)",
                line: { color: "rgba(186,230,253,.82)", width: 1 },
            },
            customdata: counts,
            hovertemplate: "Zona: %{x}<br>xG promedio: %{y:.1f}%<br>Tiros: %{customdata[0]}<br>Goles: %{customdata[1]}<extra></extra>",
        },
        {
            type: "bar",
            x: labels,
            y: summary.map(zone => zone.conversion * 100),
            name: "Conversión real",
            marker: {
                color: "rgba(16,185,129,.88)",
                line: { color: "rgba(167,243,208,.8)", width: 1 },
            },
            customdata: counts,
            hovertemplate: "Zona: %{x}<br>Conversión: %{y:.1f}%<br>Tiros: %{customdata[0]}<br>Goles: %{customdata[1]}<extra></extra>",
        },
    ], darkBaseLayout("Porcentaje (%)", {
        height: 340,
        barmode: "group",
        xaxis: { title: { text: "Zona de finalización" } },
        yaxis: { range: [0, Math.ceil((maxPct + 5) / 5) * 5] },
        legend: { orientation: "h", x: 0, y: 1.12, xanchor: "left" },
    }), { responsive: true, displayModeBar: false });
}

function renderXgZoneTable(summary) {
    const body = document.getElementById("xg-zone-table-body");
    if (!body) return;

    const totalShots = summary.reduce((acc, zone) => acc + zone.shots, 0);
    if (!totalShots) {
        body.innerHTML = '<tr><td colspan="5">No hay tiros disponibles con el filtro actual.</td></tr>';
        return;
    }

    const bestZone = summary.reduce((best, current) => (
        current.shots > 0 && current.conversion > (best?.conversion ?? -1) ? current : best
    ), null);

    body.innerHTML = summary.map(zone => `
        <tr class="${bestZone && bestZone.key === zone.key ? "is-best" : ""}">
            <td>${zone.label}</td>
            <td>${zone.shots.toLocaleString("es-CO")}</td>
            <td>${zone.goals.toLocaleString("es-CO")}</td>
            <td>${formatPct(zone.avgXg * 100)}</td>
            <td>${formatPct(zone.conversion * 100)}</td>
        </tr>
    `).join("");
}

function renderXgCalibrationExplorerChart(shots) {
    const targetId = "xg-calibration-explorer-chart";
    const bins = computeCalibrationBins(shots, 8);
    if (!bins.length) {
        renderEmptyDarkChart(targetId, "No hay suficientes tiros para evaluar calibración.");
        return;
    }

    Plotly.react(targetId, [
        {
            x: [0, 100],
            y: [0, 100],
            mode: "lines",
            name: "Calibración perfecta",
            line: { color: "rgba(148,163,184,.82)", width: 2, dash: "dash" },
            hoverinfo: "skip",
        },
        {
            x: bins.map(bin => bin.predicted * 100),
            y: bins.map(bin => bin.observed * 100),
            mode: "lines+markers",
            name: "Modelo xG",
            marker: {
                size: bins.map(bin => Math.max(8, Math.sqrt(bin.count) * 3.4)),
                color: "rgba(16,185,129,.94)",
                line: { color: "#ffffff", width: 1.1 },
            },
            line: { color: "#34d399", width: 3, shape: "spline" },
            customdata: bins.map(bin => [bin.count, bin.label]),
            hovertemplate: "Bin: %{customdata[1]}<br>xG predicho: %{x:.1f}%<br>Gol real: %{y:.1f}%<br>Tiros: %{customdata[0]}<extra></extra>",
        },
    ], darkBaseLayout("Frecuencia real de gol (%)", {
        height: 340,
        xaxis: { title: { text: "Probabilidad predicha (xG)" }, range: [0, 100] },
        yaxis: { title: { text: "Frecuencia real de gol" }, range: [0, 100] },
        legend: { orientation: "h", x: 0, y: 1.12, xanchor: "left" },
    }), { responsive: true, displayModeBar: false });
}

function computeCalibrationBins(shots, binCount = 8) {
    const validShots = shots.filter(shot => Number.isFinite(shot.xg_probability) && Number.isFinite(shot.is_goal));
    const bins = [];

    for (let index = 0; index < binCount; index += 1) {
        const low = index / binCount;
        const high = (index + 1) / binCount;
        const bucket = validShots.filter(shot => (
            shot.xg_probability >= low &&
            (index === binCount - 1 ? shot.xg_probability <= high : shot.xg_probability < high)
        ));
        if (!bucket.length) continue;

        const predicted = bucket.reduce((acc, shot) => acc + shot.xg_probability, 0) / bucket.length;
        const observed = bucket.reduce((acc, shot) => acc + shot.is_goal, 0) / bucket.length;
        bins.push({
            label: `${Math.round(low * 100)}-${Math.round(high * 100)}%`,
            predicted,
            observed,
            count: bucket.length,
        });
    }

    return bins;
}

function buildXgPitchLayout(extra = {}) {
    return pitchLayout("", "", {
        showZones: true,
        showAnnotations: false,
        pitchImageOpacity: 0.58,
        margin: { t: 10, r: 20, b: 10, l: 20 },
        ...extra,
    });
}

function renderEmptyPitchChart(targetId, message) {
    const layout = buildXgPitchLayout({
        annotations: [{
            x: 50,
            y: 50,
            xref: "x",
            yref: "y",
            text: message,
            showarrow: false,
            font: { color: "#f8fafc", size: 13, family: "Inter, sans-serif" },
            bgcolor: "rgba(4,18,11,0.72)",
            bordercolor: "rgba(241,245,249,0.22)",
            borderwidth: 1,
            borderpad: 10,
        }],
    });
    Plotly.react(targetId, [], layout, { responsive: true, displayModeBar: false });
}

function renderEmptyDarkChart(targetId, message) {
    Plotly.react(targetId, [], darkBaseLayout("", {
        height: 340,
        annotations: [{
            x: 0.5,
            y: 0.5,
            xref: "paper",
            yref: "paper",
            text: message,
            showarrow: false,
            font: { color: "rgba(226,232,240,.78)", size: 13, family: "Inter, sans-serif" },
            bgcolor: "rgba(2,6,23,.58)",
            bordercolor: "rgba(255,255,255,.08)",
            borderwidth: 1,
            borderpad: 10,
        }],
        xaxis: { visible: false },
        yaxis: { visible: false },
    }), { responsive: true, displayModeBar: false });
}

// ── FINDINGS ──────────────────────────────────────────────
function hydrateFindings() {
    const acc   = dashboardData.match_accuracy;
    const gap   = dashboardData.project_summary.ventaja_sobre_benchmark;
    const gapLabel = `${gap >= 0 ? "+" : ""}${gap.toFixed(1)}pp`;

    setText("finding-accuracy", formatPct(acc));

    const gapEl = document.getElementById("finding-gap");
    if (gapEl) countUp(gapEl, gapLabel);
}

function renderFindingComparison() {
    if (!document.getElementById("market-comparison-chart")) return;
    const comparison = dashboardData.benchmark_comparison || {};
    const [acc, bench] = comparison.values || [dashboardData.match_accuracy, dashboardData.project_summary.benchmark_bet365];
    const beats = comparison.model_beats_bet365 ?? (acc > bench);
    const gap = comparison.gap_vs_bet365 ?? (acc - bench);
    const chartConfig = {
        labels: comparison.labels || ["Modelo", "Bet365"],
        series: [{
            name: "Accuracy",
            values: [acc, bench],
            color: ["#14b8a6", "#fb7185"],
        }],
        title: "Modelo vs Bet365",
        subtitle: `${beats ? "El modelo supera" : "El modelo no supera"} el baseline de Bet365 por ${Math.abs(gap).toFixed(1)} pp`,
        yTitle: "Accuracy (%)",
        ySuffix: "%",
        surface: "dark",
        height: 280,
        yMax: 100,
        fallback: {
            layout: baseLayout("Accuracy (%)", { height: 280, yaxis: { range: [0, 105] } }),
            extra: { showlegend: false, bargap: 0.24 }
        }
    };

    if (!renderPremiumBarComparisonChart("market-comparison-chart", chartConfig)) {
        const chart = buildPremiumBarComparison({
            labels: comparison.labels || ["Modelo", "Bet365"],
            series: [{
                name: "Accuracy",
                values: [acc, bench],
                color: ["#14b8a6", "#fb7185"],
                capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                shadowColor: "rgba(2,6,23,.28)",
                text: [`${acc.toFixed(1)}%`, `${bench.toFixed(1)}%`],
                textposition: "auto",
                hovertemplate: "%{x}<br>Accuracy: %{y:.1f}%<extra></extra>",
            }],
            layout: baseLayout("Accuracy (%)", { height: 280, yaxis: { range: [0, 105] } }),
            extra: { showlegend: false, bargap: 0.24 }
        });
        Plotly.newPlot("market-comparison-chart", chart.data, chart.layout, { responsive: true, displayModeBar: false });
    }
}

// ── KPI CARDS ─────────────────────────────────────────────
function renderKpiCards() {
    const mm    = dashboardData.match_metrics;
    const xg    = dashboardData.xg_metrics;
    const sum   = dashboardData.project_summary;
    const bench = sum.benchmark_bet365;

    const setKpi = (id, val, accent = false) => {
        const el = document.getElementById(id);
        if (!el) return;
        const card = el.closest(".kpi-card");
        const io = new IntersectionObserver(([en]) => {
            if (en.isIntersecting) { countUp(el, val); io.disconnect(); }
        }, { threshold: .5 });
        io.observe(el);
        if (card) card.classList.toggle("kpi-accent", accent);
    };

    setKpi("kpi-match-accuracy", formatPct(dashboardData.match_accuracy), dashboardData.match_accuracy > bench);
    setKpi("kpi-bet365-accuracy", `${bench.toFixed(1)}%`, false);
    setKpi("kpi-gap",    `+${sum.ventaja_sobre_benchmark.toFixed(1)}pp`, sum.ventaja_sobre_benchmark > 0);
    setKpi("kpi-match-f1", formatPct(mm.f1_weighted * 100), mm.f1_weighted >= 0.45);
    setText("kpi-match-accuracy-note", `vs ${bench.toFixed(1)}% mercado`);

    setKpi("kpi-xg-auc",       formatDec(xg.auc_roc),           xg.auc_roc >= 0.70);
    setKpi("kpi-xg-precision", formatPct(xg.precision * 100),   xg.precision >= 0.20);
    setKpi("kpi-xg-recall",    formatPct(xg.recall * 100),      xg.recall >= 0.50);
    setKpi("kpi-xg-f1",        formatPct(xg.f1 * 100),          xg.f1 >= 0.28);

    // Clustering silhouette
    const silEl = document.getElementById("kpi-sil");
    if (silEl && dashboardData.clustering_metrics) {
        silEl.textContent = dashboardData.clustering_metrics.silhouette_score.toFixed(3);
    }
}

// ── SELECTORS ─────────────────────────────────────────────
function initializeSelectors() {
    const homeEl = document.getElementById("home-team");
    const awayEl = document.getElementById("away-team");
    if (!homeEl || !awayEl) return;

    const fixtures = dashboardData.predictions || [];
    const homes = [...new Set(fixtures.map(p => p.home))].sort();
    const latest = fixtures[fixtures.length - 1];

    const populateAwayOptions = (selectedHome, preferredAway = null) => {
        const awayTeams = fixtures
            .filter(p => p.home === selectedHome)
            .map(p => p.away)
            .sort();

        awayEl.innerHTML = "";
        awayTeams.forEach(team => awayEl.add(new Option(team, team)));

        if (preferredAway && awayTeams.includes(preferredAway)) awayEl.value = preferredAway;
        else if (awayTeams.length) awayEl.value = awayTeams[0];
    };

    homeEl.innerHTML = "";
    homes.forEach(team => homeEl.add(new Option(team, team)));

    if (latest) {
        homeEl.value = latest.home;
        populateAwayOptions(latest.home, latest.away);
    } else if (homes.length) {
        homeEl.value = homes[0];
        populateAwayOptions(homes[0]);
    }

    homeEl.addEventListener("change", () => {
        populateAwayOptions(homeEl.value);
        renderMatchPrediction();
    });
    awayEl.addEventListener("change", renderMatchPrediction);
    updateTeams(homeEl.value, awayEl.value);
}

function setupShotMapControls() {
    const modeEl = document.getElementById("shot-view-mode");
    const zonesEl = document.getElementById("shot-show-zones");
    if (!modeEl || !zonesEl) return;

    modeEl.value = SHOT_MAP_STATE.viewMode;
    zonesEl.checked = SHOT_MAP_STATE.showZones;

    if (!modeEl.dataset.bound) {
        modeEl.addEventListener("change", () => {
            SHOT_MAP_STATE.viewMode = modeEl.value || "all";
            const meta = getSelectedMatchMeta();
            renderMatchShotMap(meta ? Number(meta.match_id) : null);
            renderMatchGoalsShotMap(meta ? Number(meta.match_id) : null);
            renderGlobalPitchShotMaps();
        });
        modeEl.dataset.bound = "1";
    }

    if (!zonesEl.dataset.bound) {
        zonesEl.addEventListener("change", () => {
            SHOT_MAP_STATE.showZones = Boolean(zonesEl.checked);
            const meta = getSelectedMatchMeta();
            renderMatchShotMap(meta ? Number(meta.match_id) : null);
            renderMatchGoalsShotMap(meta ? Number(meta.match_id) : null);
            renderGlobalPitchShotMaps();
        });
        zonesEl.dataset.bound = "1";
    }
}

function filterShotsByMode(shots, mode) {
    if (mode === "goals") return shots.filter(shot => Number(shot.is_goal) === 1);
    if (mode === "highxg") return shots.filter(shot => Number(shot.xg_probability) >= 0.3);
    return shots;
}

function shotViewLabel(mode) {
    if (mode === "goals") return "solo goles";
    if (mode === "highxg") return "solo xG alto (>= 0.30)";
    return "todos los tiros";
}

function setupGlobalShotExplorerControls() {
    const buttons = document.querySelectorAll("[data-global-shot-mode]");
    if (!buttons.length) return;

    buttons.forEach(button => {
        button.classList.toggle("active", button.dataset.globalShotMode === GLOBAL_SHOT_EXPLORER_STATE.mode);
        if (button.dataset.bound) return;
        button.addEventListener("click", () => {
            GLOBAL_SHOT_EXPLORER_STATE.mode = button.dataset.globalShotMode || "goals";
            buttons.forEach(btn => btn.classList.toggle("active", btn === button));
            renderGlobalPitchShotMaps();
        });
        button.dataset.bound = "1";
    });
}

function filterGlobalShotsByMode(shots, mode) {
    if (mode === "goals") return shots.filter(shot => Number(shot.is_goal) === 1);
    if (mode === "misses") return shots.filter(shot => Number(shot.is_goal) !== 1);
    if (mode === "highxg") return shots.filter(shot => Number(shot.xg_probability) >= 0.3);
    return shots;
}

function globalShotModeLabel(mode) {
    if (mode === "goals") return "Goles";
    if (mode === "misses") return "Tiros sin gol";
    if (mode === "highxg") return "Ocasiones de xG alto";
    return "Todos los tiros";
}

function classifyGlobalShotZone(shot) {
    const x = Number(shot.x || 0);
    const y = Number(shot.y || 0);
    const centeredY = Math.abs(y - 50);

    if (x >= 94 && centeredY <= 10) return "Área chica";
    if (x >= 84 && centeredY <= 20) return "Zona de penal";
    if (x >= 76 && centeredY <= 28) return "Frontal del área";
    return "Media distancia";
}

function summarizeGlobalShots(shots) {
    const count = shots.length;
    if (!count) {
        return { count: 0, conversion: 0, avgXg: 0, dominantZone: "Sin datos" };
    }

    const goals = shots.filter(shot => Number(shot.is_goal) === 1).length;
    const avgXg = shots.reduce((acc, shot) => acc + Number(shot.xg_probability || 0), 0) / count;
    const zoneCounts = shots.reduce((acc, shot) => {
        const zone = classifyGlobalShotZone(shot);
        acc[zone] = (acc[zone] || 0) + 1;
        return acc;
    }, {});
    const dominantZone = Object.entries(zoneCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || "Sin datos";

    return {
        count,
        conversion: (goals / count) * 100,
        avgXg,
        dominantZone,
    };
}

function updateGlobalShotExplorerStats(shots) {
    const summary = summarizeGlobalShots(shots);
    setText("global-shot-count", String(summary.count));
    setText("global-shot-conv", `${summary.conversion.toFixed(1)}%`);
    setText("global-shot-xg", summary.avgXg.toFixed(3));
    setText("global-shot-zone", summary.dominantZone);
}

function describeShotType(shot) {
    if (shot?.shot_type) return shot.shot_type;
    if (Number(shot.is_penalty) === 1) return "Penal";
    if (Number(shot.is_header) === 1) return "Cabezazo";
    if (Number(shot.is_right_foot) === 1) return "Pie derecho";
    if (Number(shot.is_left_foot) === 1) return "Pie izquierdo";
    return "Otro";
}

// ── MATCH PREDICTION ──────────────────────────────────────
function getStaticMatchPrediction(home, away) {
    const match = dashboardData.predictions.find(p => p.home === home && p.away === away);
    if (!match) return null;
    return {
        prob_home: Number(match.prob_home),
        prob_draw: Number(match.prob_draw),
        prob_away: Number(match.prob_away),
        est_goals: Number(match.est_goals),
        predicted_result: ["H", "D", "A"][
            [Number(match.prob_home), Number(match.prob_draw), Number(match.prob_away)]
                .indexOf(Math.max(Number(match.prob_home), Number(match.prob_draw), Number(match.prob_away)))
        ],
        source: "static_dashboard",
        fallback_reason: null,
    };
}

function normalizeApiMatchPrediction(response) {
    const home = Number(response?.home_win_probability);
    const draw = Number(response?.draw_probability);
    const away = Number(response?.away_win_probability);
    if (![home, draw, away].every(Number.isFinite)) {
        throw new Error("Respuesta de partido invalida.");
    }
    const scale = Math.max(home, draw, away) <= 1 ? 100 : 1;
    return {
        prob_home: clampValue(home * scale, 0, 100),
        prob_draw: clampValue(draw * scale, 0, 100),
        prob_away: clampValue(away * scale, 0, 100),
        est_goals: Number.isFinite(Number(response.expected_goals)) ? Number(response.expected_goals) : 0,
        predicted_result: response.predicted_result || "H",
        source: response.source || "api",
        model: response.model || null,
        fallback_reason: response.fallback_reason || null,
    };
}

async function fetchApiMatchPrediction(home, away) {
    const response = await apiFetch("/predict/match", {
        method: "POST",
        body: JSON.stringify({ home_team: home, away_team: away }),
    });
    return normalizeApiMatchPrediction(response);
}

function renderMatchPredictionValues(match, home, away) {
    setText("prob-home", formatPct(match.prob_home));
    setText("prob-draw", formatPct(match.prob_draw));
    setText("prob-away", formatPct(match.prob_away));
    setText("est-goals", Number(match.est_goals || 0).toFixed(2));

    animateBarWidth(document.getElementById("pbar-home"), match.prob_home, 100);
    animateBarWidth(document.getElementById("pbar-draw"), match.prob_draw, 150);
    animateBarWidth(document.getElementById("pbar-away"), match.prob_away, 200);

    const sourceLabel = match.source === "api_model"
        ? `Modo API: ${match.model || "modelo activo"}`
        : match.source && match.source.includes("fallback")
            ? `Modo API con fallback: ${match.fallback_reason || "prediccion estatica"}`
            : "Modo offline: usando predicciones estaticas del dashboard.";
    updatePredictorModeNote(sourceLabel, Boolean(match.fallback_reason && match.source !== "static_dashboard"));

    const chartConfig = {
        labels: ["Local", "Empate", "Visitante"],
        series: [{
            name: "Probabilidad",
            values: [match.prob_home, match.prob_draw, match.prob_away],
            color: ["#14b8a6", "#f59e0b", "#fb7185"],
        }],
        title: "Probabilidad del partido",
        subtitle: `${normalizeTeamName(home)} vs ${normalizeTeamName(away)}`,
        yTitle: "Probabilidad (%)",
        ySuffix: "%",
        surface: "light",
        height: 420,
        yMax: 100,
        fallback: {
            layout: baseLayout("Probabilidad (%)", {
                height: 400,
                yaxis: { range: [0, 105] },
            }),
            extra: { showlegend: false, bargap: 0.2 }
        }
    };

    if (!renderPremiumBarComparisonChart("match-chart", chartConfig)) {
        const chart = buildPremiumBarComparison({
            labels: chartConfig.labels,
            series: [{
                name: "Probabilidad",
                values: [match.prob_home, match.prob_draw, match.prob_away],
                color: ["#14b8a6", "#f59e0b", "#fb7185"],
                capColor: ["rgba(255,255,255,.25)", "rgba(255,255,255,.22)", "rgba(255,255,255,.22)"],
                shadowColor: "rgba(2,6,23,.24)",
                text: [match.prob_home, match.prob_draw, match.prob_away].map(v => formatPct(v)),
                textposition: "outside",
                hovertemplate: "%{x}: %{text}<extra></extra>",
            }],
            layout: baseLayout("Probabilidad (%)", {
                height: 400,
                yaxis: { range: [0, 105] },
            }),
            extra: { showlegend: false, bargap: 0.2 }
        });
        Plotly.newPlot("match-chart", chart.data, chart.layout, { responsive: true, displayModeBar: false });
    }
}

async function renderMatchPrediction() {
    const home = document.getElementById("home-team").value;
    const away = document.getElementById("away-team").value;
    if (!home || !away || home === away) return;

    updateTeams(home, away);

    const meta = getSelectedMatchMeta();
    renderMatchShotMap(meta ? Number(meta.match_id) : null);
    renderMatchGoalsShotMap(meta ? Number(meta.match_id) : null);

    const requestId = ++MATCH_PREDICTION_REQUEST_ID;
    const staticMatch = getStaticMatchPrediction(home, away);
    if (!staticMatch) return;

    renderMatchPredictionValues(staticMatch, home, away);

    if (!apiState.connected) return;

    try {
        updatePredictorModeNote("Modo API: consultando /predict/match...");
        const apiMatch = await fetchApiMatchPrediction(home, away);
        if (requestId !== MATCH_PREDICTION_REQUEST_ID) return;
        renderMatchPredictionValues(apiMatch, home, away);
    } catch (err) {
        if (requestId !== MATCH_PREDICTION_REQUEST_ID) return;
        console.warn("Fallo /predict/match:", err.message);
        updatePredictorModeNote("API no disponible para este partido: usando fallback estatico.", true);
    }
}

function getSelectedMatchMeta() {
    const home = document.getElementById("home-team").value;
    const away = document.getElementById("away-team").value;
    return (dashboardData.match_shot_options || []).find(m => m.home_team === home && m.away_team === away) || null;
}

// ── SHOT MAPS ─────────────────────────────────────────────
function renderMatchShotMap(matchId) {
    const shots = dashboardData.shots || [];
    const matchShots = matchId === null ? [] : shots.filter(s => Number(s.match_id) === matchId);
    const filtered = filterShotsByMode(matchShots, SHOT_MAP_STATE.viewMode);
    const meta     = (dashboardData.match_shot_options || []).find(m => Number(m.match_id) === matchId) || null;
    renderCanvasPitch("pitch-match-map", {
        shots: filtered,
        mode: "shots",
        title: "Shot map del partido",
        subtitle: meta
            ? `${meta.date} | ${meta.home_team} ${meta.fthg}-${meta.ftag} ${meta.away_team} | Vista: ${shotViewLabel(SHOT_MAP_STATE.viewMode)}`
            : "Sin partido exportado para este matchup",
        showZones: SHOT_MAP_STATE.showZones,
        animate: true,
        legend: [
            { label: "Gol", color: "#00ff96" },
            { label: "Tiro", color: "#ffd54a" },
        ],
    });
}

function renderMatchGoalsShotMap(matchId) {
    const shots = dashboardData.shots || [];
    const matchShots = matchId === null ? [] : shots.filter(s => Number(s.match_id) === matchId);
    const filtered = filterShotsByMode(matchShots, SHOT_MAP_STATE.viewMode);
    const goals = filtered.filter(s => Number(s.is_goal) === 1);
    const meta  = (dashboardData.match_shot_options || []).find(m => Number(m.match_id) === matchId) || null;
    renderCanvasPitch("pitch-selected-goals-map", {
        shots: goals,
        mode: "shots",
        title: "Mapa de goles",
        subtitle: meta
            ? `${meta.home_team} vs ${meta.away_team} | Vista: ${shotViewLabel(SHOT_MAP_STATE.viewMode)}`
            : "Sin goles disponibles",
        showZones: SHOT_MAP_STATE.showZones,
        animate: true,
        legend: [
            { label: "Gol + glow", color: "#00ff96" },
        ],
    });
}

function renderGlobalPitchShotMaps() {
    const gs = dashboardData.shot_map_global || [];
    if (!document.getElementById("pitch-shot-map")) return;
    const filtered = filterGlobalShotsByMode(gs, GLOBAL_SHOT_EXPLORER_STATE.mode);
    const labels = {
        goals: "Dónde sí termina en gol",
        misses: "Dónde se remata pero no se convierte",
        highxg: "Dónde nacen las ocasiones más claras",
        all: "Panorama completo de finalización",
    };
    const legends = {
        goals: [{ label: "Gol", color: "#00ff96" }],
        misses: [{ label: "Tiro sin gol", color: "#ffd54a" }],
        highxg: [
            { label: "Gol xG alto", color: "#00ff96" },
            { label: "No gol xG alto", color: "#ffd54a" },
        ],
        all: [
            { label: "Goles", color: "#00ff96" },
            { label: "Tiros sin gol", color: "#ffd54a" },
        ],
    };

    updateGlobalShotExplorerStats(filtered);
    renderCanvasPitch("pitch-shot-map", {
        shots: filtered,
        mode: "shots",
        title: globalShotModeLabel(GLOBAL_SHOT_EXPLORER_STATE.mode),
        subtitle: `${labels[GLOBAL_SHOT_EXPLORER_STATE.mode]} | Todos los partidos normalizados hacia el arco rival (100,50)`,
        showZones: true,
        animate: true,
        legend: legends[GLOBAL_SHOT_EXPLORER_STATE.mode] || legends.all,
    });
}

function goalGlowTrace(pts) {
    return {
        x: pts.map(s => Number(s.x)),
        y: pts.map(s => Number(s.y)),
        mode: "markers",
        name: "Glow goles",
        showlegend: false,
        hoverinfo: "skip",
        marker: {
            size: pts.map(s => Math.max(10, 8 + (Number(s.xg_probability) || 0) * 16)),
            color: "rgba(0,255,150,.16)",
            line: { color: "rgba(0,255,150,.22)", width: 0 },
        },
    };
}

function shotTrace(pts, name, color, minSize, outline = false) {
    return {
        x: pts.map(s => Number(s.x)),
        y: pts.map(s => Number(s.y)),
        mode: "markers", name,
        marker: {
            size: pts.map(s => Math.max(minSize, 4 + (Number(s.xg_probability) || 0) * 10)),
            color,
            opacity: 0.95,
            line: outline ? { color: "rgba(255,255,255,.95)", width: 1.2 } : { color: "rgba(255,255,255,.40)", width: 0.9 },
        },
        customdata: pts.map(s => ([
            Number(s.xg_probability || 0),
            Number(s.is_goal || 0) === 1 ? "Gol" : "No gol",
            describeShotType(s),
            Number(s.is_big_chance || 0) === 1 ? "Sí" : "No",
            Number(s.distance_to_goal || 0),
            Number(s.angle_to_goal || 0),
        ])),
        hovertemplate: "<b>%{name}</b><br>xG: %{customdata[0]:.3f}<br>Resultado: %{customdata[1]}<br>Tipo: %{customdata[2]}<br>Big chance: %{customdata[3]}<br>Distancia: %{customdata[4]:.1f}<br>Ángulo: %{customdata[5]:.3f}<extra></extra>",
    };
}

// ── DENSITY HEATMAP (xG SPOTLIGHT) ───────────────────────
function renderPitchDensityMap() {
    const el = document.getElementById("pitch-density-map");
    if (!el) return;
    const src = dashboardData.shot_map_global || dashboardData.shots || [];
    if (!src.length) return;
    renderCanvasPitch("pitch-density-map", {
        shots: src,
        mode: "heatmap",
        title: "Mapa de densidad de disparos",
        subtitle: "Heatmap ofensivo con hotspots de peligro y overlay táctico tipo broadcast",
        showZones: true,
        animate: false,
        legend: [
            { label: "Alta densidad", color: "#ef4444" },
            { label: "Media", color: "#f59e0b" },
            { label: "Baja", color: "#38bdf8" },
        ],
    });
}

function renderCanvasPitch(containerId, options = {}) {
    const instance = getOrCreatePitchCanvas(containerId);
    if (!instance) return;
    instance.config = {
        shots: options.shots || [],
        mode: options.mode || "shots",
        title: options.title || "",
        subtitle: options.subtitle || "",
        showZones: options.showZones !== false,
        animate: options.animate !== false,
        legend: options.legend || [],
    };
    instance.titleEl.textContent = instance.config.title;
    instance.subtitleEl.textContent = instance.config.subtitle;
    instance.legendEl.innerHTML = instance.config.legend
        .map(item => `<span class="pitch-canvas-chip" style="color:${item.color}">${item.label}</span>`)
        .join("");
    instance.animationStart = performance.now();
    drawCanvasPitch(instance);
}

function getOrCreatePitchCanvas(containerId) {
    const host = document.getElementById(containerId);
    if (!host) return null;
    host.classList.add("pitch-chart-host");
    if (PITCH_CANVAS_INSTANCES.has(containerId)) return PITCH_CANVAS_INSTANCES.get(containerId);

    host.innerHTML = "";
    const shell = document.createElement("div");
    shell.className = "pitch-canvas-shell";

    const canvas = document.createElement("canvas");
    const meta = document.createElement("div");
    meta.className = "pitch-canvas-meta";
    const titleEl = document.createElement("div");
    titleEl.className = "pitch-canvas-title";
    const subtitleEl = document.createElement("div");
    subtitleEl.className = "pitch-canvas-subtitle";
    meta.append(titleEl, subtitleEl);

    const legendEl = document.createElement("div");
    legendEl.className = "pitch-canvas-legend";

    const tooltip = document.createElement("div");
    tooltip.className = "pitch-tooltip";

    shell.append(canvas, meta, legendEl, tooltip);
    host.appendChild(shell);

    const instance = {
        id: containerId,
        host,
        shell,
        canvas,
        ctx: canvas.getContext("2d"),
        titleEl,
        subtitleEl,
        legendEl,
        tooltip,
        config: null,
        hoveredShot: null,
        animationStart: 0,
        rafId: 0,
    };

    const resize = () => resizePitchCanvas(instance);
    if (typeof ResizeObserver !== "undefined") {
        const observer = new ResizeObserver(resize);
        observer.observe(host);
        instance.resizeObserver = observer;
    } else {
        window.addEventListener("resize", resize);
    }

    canvas.addEventListener("mousemove", event => handlePitchPointer(instance, event));
    canvas.addEventListener("mouseleave", () => hidePitchTooltip(instance));

    resizePitchCanvas(instance);
    PITCH_CANVAS_INSTANCES.set(containerId, instance);
    return instance;
}

function resizePitchCanvas(instance) {
    const rect = instance.host.getBoundingClientRect();
    const width = Math.max(320, Math.round(rect.width || instance.host.clientWidth || 320));
    const height = Math.max(280, Math.round(rect.height || instance.host.clientHeight || 320));
    const dpr = window.devicePixelRatio || 1;
    instance.width = width;
    instance.height = height;
    instance.canvas.width = Math.round(width * dpr);
    instance.canvas.height = Math.round(height * dpr);
    instance.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (instance.config) drawCanvasPitch(instance, false);
}

function drawCanvasPitch(instance, allowAnimation = true) {
    if (!instance?.config) return;
    if (instance.rafId) cancelAnimationFrame(instance.rafId);
    const { ctx, width, height, config } = instance;
    if (!ctx || !width || !height) return;

    ctx.clearRect(0, 0, width, height);
    drawPitchSurface(ctx, width, height);
    drawPitchLinesCanvas(ctx, width, height, config.showZones);

    if (!config.shots.length) {
        ctx.fillStyle = "rgba(248,250,252,.92)";
        ctx.font = "700 16px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("Sin datos de disparos disponibles", width / 2, height / 2);
        return;
    }

    if (config.mode === "heatmap") {
        drawHeatmapCanvas(ctx, config.shots, width, height);
        drawShotsCanvas(ctx, config.shots.slice(0, Math.min(config.shots.length, 36)), width, height, 0.45);
        return;
    }

    const progress = config.animate && allowAnimation
        ? Math.min(1, (performance.now() - instance.animationStart) / 950)
        : 1;
    const visibleCount = Math.max(1, Math.round(config.shots.length * progress));
    drawShotsCanvas(ctx, config.shots.slice(0, visibleCount), width, height, 1);

    if (progress < 1 && config.animate && allowAnimation) {
        instance.rafId = requestAnimationFrame(() => drawCanvasPitch(instance, true));
    }
}

function drawPitchSurface(ctx, width, height) {
    if (PITCH_TEXTURE.complete && PITCH_TEXTURE.naturalWidth) {
        ctx.drawImage(PITCH_TEXTURE, 0, 0, width, height);
    } else {
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, "#1d7b35");
        gradient.addColorStop(1, "#0d4720");
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);
    }

    ctx.fillStyle = "rgba(0,0,0,0.22)";
    ctx.fillRect(0, 0, width, height);

    const stripeHeight = height / 8;
    for (let index = 0; index < 8; index += 1) {
        ctx.fillStyle = index % 2 === 0 ? "rgba(255,255,255,0.035)" : "rgba(0,0,0,0.02)";
        ctx.fillRect(0, index * stripeHeight, width, stripeHeight);
    }
}

function drawPitchLinesCanvas(ctx, width, height, showZones) {
    const lineColor = "rgba(255,255,255,0.96)";
    const padX = width * 0.03;
    const padY = height * 0.035;
    const innerW = width - (padX * 2);
    const innerH = height - (padY * 2);
    const centerX = width / 2;
    const centerY = height / 2;

    ctx.save();
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = Math.max(1.6, width * 0.0032);
    ctx.shadowColor = "rgba(255,255,255,.18)";
    ctx.shadowBlur = 5;

    ctx.strokeRect(padX, padY, innerW, innerH);
    ctx.beginPath();
    ctx.moveTo(centerX, padY);
    ctx.lineTo(centerX, height - padY);
    ctx.stroke();

    const circleRadius = Math.min(innerW, innerH) * 0.14;
    ctx.beginPath();
    ctx.arc(centerX, centerY, circleRadius, 0, Math.PI * 2);
    ctx.stroke();

    drawPenaltyAreas(ctx, padX, padY, innerW, innerH);

    ctx.fillStyle = lineColor;
    [padX + innerW * 0.11, centerX, padX + innerW * 0.89].forEach(x => {
        ctx.beginPath();
        ctx.arc(x, centerY, Math.max(2.4, width * 0.003), 0, Math.PI * 2);
        ctx.fill();
    });

    if (showZones) {
        ctx.setLineDash([8, 8]);
        ctx.lineWidth = 1;
        ctx.strokeStyle = "rgba(110,231,183,.32)";
        ctx.strokeRect(padX + innerW * 0.68, padY + innerH * 0.2, innerW * 0.2, innerH * 0.6);
        ctx.strokeRect(padX + innerW * 0.82, padY + innerH * 0.33, innerW * 0.1, innerH * 0.34);
        ctx.strokeRect(padX + innerW * 0.52, padY + innerH * 0.18, innerW * 0.16, innerH * 0.64);
        ctx.setLineDash([]);
    }
    ctx.restore();
}

function drawPenaltyAreas(ctx, padX, padY, innerW, innerH) {
    const penaltyDepth = innerW * 0.16;
    const sixDepth = innerW * 0.055;
    const boxHeight = innerH * 0.4;
    const sixHeight = innerH * 0.2;
    const boxY = padY + (innerH - boxHeight) / 2;
    const sixY = padY + (innerH - sixHeight) / 2;

    ctx.strokeRect(padX, boxY, penaltyDepth, boxHeight);
    ctx.strokeRect(padX, sixY, sixDepth, sixHeight);
    ctx.strokeRect(padX + innerW - penaltyDepth, boxY, penaltyDepth, boxHeight);
    ctx.strokeRect(padX + innerW - sixDepth, sixY, sixDepth, sixHeight);

    ctx.beginPath();
    ctx.arc(padX + penaltyDepth, padY + innerH / 2, innerH * 0.1, -Math.PI / 2, Math.PI / 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(padX + innerW - penaltyDepth, padY + innerH / 2, innerH * 0.1, Math.PI / 2, (Math.PI * 3) / 2);
    ctx.stroke();
}

function drawHeatmapCanvas(ctx, shots, width, height) {
    shots.forEach(shot => {
        const x = scalePitchX(Number(shot.x || 0), width);
        const y = scalePitchY(Number(shot.y || 0), height);
        const xg = Number(shot.xg_probability || 0);
        const radius = 24 + (xg * 56);
        const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
        gradient.addColorStop(0, "rgba(239,68,68,0.34)");
        gradient.addColorStop(0.45, "rgba(245,158,11,0.18)");
        gradient.addColorStop(0.75, "rgba(56,189,248,0.11)");
        gradient.addColorStop(1, "rgba(56,189,248,0)");
        ctx.fillStyle = gradient;
        ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
    });
}

function drawShotsCanvas(ctx, shots, width, height, alpha = 1) {
    shots.forEach(shot => {
        const x = scalePitchX(Number(shot.x || 0), width);
        const y = scalePitchY(Number(shot.y || 0), height);
        const xg = Number(shot.xg_probability || 0);
        const radius = 4 + (xg * 12);
        const isGoal = Number(shot.is_goal) === 1;

        ctx.save();
        ctx.globalAlpha = alpha;
        if (isGoal) {
            ctx.fillStyle = "rgba(0,255,150,0.9)";
            ctx.shadowBlur = 14;
            ctx.shadowColor = "rgba(0,255,150,0.9)";
        } else {
            ctx.fillStyle = "rgba(255,200,0,0.72)";
            ctx.shadowBlur = 0;
        }

        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,.92)";
        ctx.lineWidth = 1.1;
        ctx.stroke();
        ctx.restore();
    });
}

function scalePitchX(x, width) {
    return (x / 100) * width;
}

function scalePitchY(y, height) {
    return height - ((y / 100) * height);
}

function handlePitchPointer(instance, event) {
    const shots = instance.config?.shots || [];
    if (!shots.length) return;
    const rect = instance.canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    let hit = null;
    for (const shot of shots) {
        const shotX = scalePitchX(Number(shot.x || 0), instance.width);
        const shotY = scalePitchY(Number(shot.y || 0), instance.height);
        const radius = 8 + (Number(shot.xg_probability || 0) * 12);
        if (Math.hypot(mouseX - shotX, mouseY - shotY) <= radius) {
            hit = shot;
            break;
        }
    }

    if (!hit) {
        hidePitchTooltip(instance);
        return;
    }

    instance.tooltip.innerHTML = `
        <strong>${Number(hit.is_goal) === 1 ? "Gol" : "No gol"}</strong>
        <div>xG: ${(Number(hit.xg_probability || 0)).toFixed(2)}</div>
        <div class="muted">${describeShotType(hit)} · Distancia ${(Number(hit.distance_to_goal || 0)).toFixed(1)}</div>
    `;
    instance.tooltip.style.left = `${Math.min(instance.width - 150, mouseX + 16)}px`;
    instance.tooltip.style.top = `${Math.max(14, mouseY - 12)}px`;
    instance.tooltip.classList.add("visible");
}

function hidePitchTooltip(instance) {
    if (!instance?.tooltip) return;
    instance.tooltip.classList.remove("visible");
}

// ── EDA CHARTS ────────────────────────────────────────────
function getAdvancedEdaData() {
    return dashboardEdaData || null;
}

function formatCount(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "-";
    return number.toLocaleString("es-CO");
}

function formatRate(value, decimals = 1) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "-";
    return `${(number * 100).toFixed(decimals)}%`;
}

function renderDashboardEdaSection() {
    const data = getAdvancedEdaData();
    if (!data) {
        showEdaDataLoadError();
        return;
    }

    hydrateEdaSummaryCards(data.summary_cards || {});
    renderEdaFeatureBlocks(data.feature_engineering || {});
    renderEdaLeakageTable(data.feature_engineering?.data_leakage_table || []);
    renderEdaInsights(data.insights || []);
    renderAdvancedShotEdaCharts(data.shot_eda || {});
    renderAdvancedMatchEdaCharts(data.match_eda || {}, data.summary_cards || {});
}

function showEdaDataLoadError() {
    const summaryTarget = document.getElementById("eda-summary-cards");
    if (summaryTarget) {
        summaryTarget.innerHTML = `
            <article class="eda-load-error" role="alert">
                <strong>No se pudieron cargar los datos EDA avanzados.</strong>
                <span>Ejecuta python scripts/build_dashboard_eda_data.py para generar dashboard_eda_data.json y dashboard_eda_data_embedded.js. En modo file:// se usa el archivo embebido.</span>
            </article>
        `;
    }

    const baseline = document.getElementById("eda-xg-baseline-note");
    if (baseline) {
        baseline.textContent = "EDA avanzado no disponible. El resto del dashboard sigue funcionando con sus datos base.";
    }

    [
        "eda-goals-vs-no-goals-chart",
        "eda-conversion-bigchance-chart",
        "eda-conversion-penalty-chart",
        "eda-body-part-chart",
        "eda-distance-bins-chart",
        "eda-top-qualifiers-chart",
        "eda-match-results-chart",
        "eda-total-goals-chart",
        "eda-over-under-chart",
        "eda-bet365-favorite-chart",
    ].forEach(id => renderEmptyDarkChart(id, "Datos EDA no disponibles"));
}

function hydrateEdaSummaryCards(summary) {
    const target = document.getElementById("eda-summary-cards");
    if (!target) return;
    const cards = [
        { label: "Partidos", value: formatCount(summary.total_matches), note: "Muestra Match Predictor" },
        { label: "Eventos", value: formatCount(summary.total_events), note: "Base WhoScored" },
        { label: "Tiros", value: formatCount(summary.total_shots), note: "Eventos is_shot" },
        { label: "Goles", value: formatCount(summary.total_goals), note: "Targets xG y partidos" },
        { label: "Conversion tiro", value: formatRate(summary.shot_conversion_rate), note: "Goles / tiros" },
        { label: "Accuracy Bet365", value: formatRate(summary.bet365_accuracy), note: "Benchmark H/D/A" },
    ];
    target.innerHTML = cards.map(card => `
        <article class="eda-summary-card">
            <span>${card.label}</span>
            <strong>${card.value}</strong>
            <small>${card.note}</small>
        </article>
    `).join("");

    const baseline = document.getElementById("eda-xg-baseline-note");
    if (baseline && Number.isFinite(Number(summary.xg_naive_baseline_accuracy))) {
        baseline.textContent = `Baseline naive xG: predecir siempre "no gol" alcanza ${formatRate(summary.xg_naive_baseline_accuracy)} de accuracy, por eso se evalua con precision, recall, F1 y AUC.`;
    }
}

function renderEdaFeatureBlocks(featureEngineering) {
    const xgTarget = document.getElementById("eda-xg-features");
    const matchTarget = document.getElementById("eda-match-features");
    if (xgTarget) {
        const features = featureEngineering.xg_features || [];
        xgTarget.innerHTML = features.map(feature => `<span class="eda-feature-pill">${feature}</span>`).join("");
    }
    if (matchTarget) {
        const features = featureEngineering.match_predictor_features || [];
        matchTarget.innerHTML = features.map(feature => `<span class="eda-feature-pill">${feature}</span>`).join("");
    }
}

function renderEdaLeakageTable(rows) {
    const target = document.getElementById("eda-leakage-table-body");
    if (!target) return;
    if (!rows.length) {
        target.innerHTML = `<tr><td colspan="3">No hay tabla de leakage disponible.</td></tr>`;
        return;
    }
    target.innerHTML = rows.map(row => {
        const isLeak = String(row.tipo || "").toLowerCase().includes("leakage");
        return `
            <tr>
                <td>${row.feature || "-"}</td>
                <td><span class="eda-leakage-badge ${isLeak ? "is-leak" : "is-valid"}">${row.tipo || "-"}</span></td>
                <td>${row.razon || row["razón"] || "-"}</td>
            </tr>
        `;
    }).join("");
}

function renderEdaInsights(insights) {
    const target = document.getElementById("eda-insights-list");
    if (!target) return;
    if (!insights.length) {
        target.innerHTML = `<article class="eda-insight-card">Sin insights exportados.</article>`;
        return;
    }
    target.innerHTML = insights.map((insight, index) => `
        <article class="eda-insight-card">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <p>${insight}</p>
        </article>
    `).join("");
}

function renderAdvancedShotEdaCharts(shotEda) {
    renderSimpleBarChart("eda-goals-vs-no-goals-chart", shotEda.goals_vs_no_goals || [], {
        labelKey: "label",
        valueKey: "value",
        yTitle: "Tiros",
        colors: ["#64748b", "#10b981"],
        valueFormatter: value => formatCount(value),
        hoverSuffix: "tiros",
    });

    renderConversionBarChart("eda-conversion-bigchance-chart", shotEda.conversion_by_big_chance || [], "BigChance");
    renderConversionBarChart("eda-conversion-penalty-chart", shotEda.conversion_by_penalty || [], "Penal");
    renderConversionBarChart("eda-body-part-chart", shotEda.conversion_by_body_part || [], "Parte del cuerpo");
    renderConversionLineChart("eda-distance-bins-chart", shotEda.conversion_by_shot_distance_bins || [], "Distancia media al arco", "Distancia", "mean_value");
    renderSimpleBarChart("eda-top-qualifiers-chart", shotEda.top_qualifiers_frequency || [], {
        labelKey: "qualifier",
        valueKey: "shots",
        yTitle: "Tiros",
        orientation: "h",
        colors: ["#38bdf8"],
        valueFormatter: value => formatCount(value),
        hoverSuffix: "tiros",
    });
}

function renderAdvancedMatchEdaCharts(matchEda, summary) {
    renderSimpleBarChart("eda-match-results-chart", matchEda.result_distribution_HDA || [], {
        labelKey: "label",
        valueKey: "value",
        yTitle: "Partidos",
        colors: ["#10b981", "#f59e0b", "#6366f1"],
        valueFormatter: value => formatCount(value),
        hoverSuffix: "partidos",
    });
    renderSimpleBarChart("eda-total-goals-chart", matchEda.total_goals_distribution || [], {
        labelKey: "label",
        valueKey: "value",
        yTitle: "Partidos",
        colors: ["#14b8a6"],
        valueFormatter: value => formatCount(value),
        hoverSuffix: "partidos",
    });
    renderSimpleBarChart("eda-over-under-chart", matchEda.over_under_2_5 || [], {
        labelKey: "label",
        valueKey: "value",
        yTitle: "Partidos",
        colors: ["#3b82f6", "#f43f5e"],
        valueFormatter: value => formatCount(value),
        hoverSuffix: "partidos",
    });
    renderBet365FavoriteHeatmap("eda-bet365-favorite-chart", matchEda.bet365_favorite_vs_actual || []);

    const benchmark = document.getElementById("eda-bet365-benchmark");
    const accuracy = Number(matchEda.bet365_accuracy ?? summary.bet365_accuracy);
    if (benchmark && Number.isFinite(accuracy)) {
        benchmark.innerHTML = `<strong>${formatRate(accuracy)}</strong><span>Accuracy Bet365 como benchmark de mercado</span>`;
    }
}

function renderSimpleBarChart(domId, rows, config) {
    const target = document.getElementById(domId);
    if (!target) return;
    if (!rows.length) {
        renderEmptyDarkChart(domId, "Sin datos disponibles");
        return;
    }
    const labels = rows.map(row => String(row[config.labelKey]));
    const values = rows.map(row => Number(row[config.valueKey] || 0));
    const colors = values.map((_, index) => config.colors[index % config.colors.length]);
    const orientation = config.orientation || "v";
    const trace = orientation === "h"
        ? {
            y: labels.slice().reverse(),
            x: values.slice().reverse(),
            type: "bar",
            orientation: "h",
            marker: { color: colors.slice().reverse(), line: { color: "rgba(255,255,255,.18)", width: 1 } },
            text: values.slice().reverse().map(value => config.valueFormatter ? config.valueFormatter(value) : String(value)),
            textposition: "outside",
            hovertemplate: `%{y}: %{x}<extra></extra>`,
        }
        : {
            x: labels,
            y: values,
            type: "bar",
            marker: { color: colors, line: { color: "rgba(255,255,255,.18)", width: 1 } },
            text: values.map(value => config.valueFormatter ? config.valueFormatter(value) : String(value)),
            textposition: "outside",
            hovertemplate: `%{x}: %{y} ${config.hoverSuffix || ""}<extra></extra>`,
        };
    Plotly.newPlot(domId, [trace], darkBaseLayout(config.yTitle || "", {
        height: config.height || 340,
        margin: orientation === "h" ? { t: 42, r: 26, b: 48, l: 128, pad: 8 } : { t: 42, r: 24, b: 58, l: 58, pad: 8 },
        xaxis: orientation === "h" ? { title: { text: config.yTitle || "" } } : { title: { text: "" } },
        yaxis: orientation === "h" ? { title: { text: "" }, automargin: true } : { title: { text: config.yTitle || "" } },
        showlegend: false,
    }), { responsive: true, displayModeBar: false });
}

function renderConversionBarChart(domId, rows, title) {
    const target = document.getElementById(domId);
    if (!target) return;
    if (!rows.length) {
        renderEmptyDarkChart(domId, "Sin datos disponibles");
        return;
    }
    const labels = rows.map(row => row.label);
    const values = rows.map(row => Number(row.conversion_rate || 0) * 100);
    const custom = rows.map(row => [row.shots, row.goals]);
    Plotly.newPlot(domId, [{
        x: labels,
        y: values,
        type: "bar",
        marker: {
            color: labels.map((_, index) => index === labels.length - 1 ? "#10b981" : "#64748b"),
            line: { color: "rgba(255,255,255,.2)", width: 1 },
        },
        customdata: custom,
        text: values.map(value => `${value.toFixed(1)}%`),
        textposition: "outside",
        hovertemplate: `${title}: %{x}<br>Conversion: %{y:.1f}%<br>Tiros: %{customdata[0]}<br>Goles: %{customdata[1]}<extra></extra>`,
    }], darkBaseLayout("Conversion (%)", {
        height: 330,
        yaxis: { title: { text: "Conversion (%)" }, range: [0, Math.max(12, Math.max(...values) * 1.22)] },
        showlegend: false,
    }), { responsive: true, displayModeBar: false });
}

function renderConversionLineChart(domId, rows, xTitle, hoverTitle, xKey) {
    const target = document.getElementById(domId);
    if (!target) return;
    if (!rows.length) {
        renderEmptyDarkChart(domId, "Sin datos disponibles");
        return;
    }
    const x = rows.map(row => Number(row[xKey] || 0));
    const y = rows.map(row => Number(row.conversion_rate || 0) * 100);
    const custom = rows.map(row => [row.shots, row.goals, row.label]);
    Plotly.newPlot(domId, [{
        x,
        y,
        type: "scatter",
        mode: "lines+markers",
        marker: { color: "#34d399", size: 9, line: { color: "#ffffff", width: 1 } },
        line: { color: "#10b981", width: 3, shape: "spline" },
        customdata: custom,
        hovertemplate: `${hoverTitle}: %{x:.2f}<br>Conversion: %{y:.1f}%<br>Tiros: %{customdata[0]}<br>Goles: %{customdata[1]}<br>Bin: %{customdata[2]}<extra></extra>`,
    }], darkBaseLayout("Conversion (%)", {
        height: 340,
        xaxis: { title: { text: xTitle } },
        yaxis: { title: { text: "Conversion (%)" }, rangemode: "tozero" },
        showlegend: false,
    }), { responsive: true, displayModeBar: false });
}

function renderBet365FavoriteHeatmap(domId, rows) {
    const target = document.getElementById(domId);
    if (!target) return;
    if (!rows.length) {
        renderEmptyDarkChart(domId, "Sin datos Bet365 disponibles");
        return;
    }
    const labels = ["H", "D", "A"];
    const z = labels.map(fav => labels.map(actual => {
        const hit = rows.find(row => row.favorite === fav && row.actual === actual);
        return hit ? Number(hit.matches || 0) : 0;
    }));
    Plotly.newPlot(domId, [{
        z,
        x: labels.map(label => `Real ${label}`),
        y: labels.map(label => `Favorito ${label}`),
        type: "heatmap",
        colorscale: [
            [0, "rgba(15,23,42,.15)"],
            [0.45, "rgba(56,189,248,.58)"],
            [1, "rgba(16,185,129,.96)"],
        ],
        showscale: false,
        text: z,
        texttemplate: "%{text}",
        textfont: { color: "#f8fafc", size: 14, family: "Inter, sans-serif" },
        hovertemplate: "%{y}<br>%{x}<br>Partidos: %{z}<extra></extra>",
    }], darkBaseLayout("Partidos", {
        height: 350,
        margin: { t: 36, r: 26, b: 60, l: 92, pad: 8 },
        xaxis: { title: { text: "Resultado real" } },
        yaxis: { title: { text: "Favorito Bet365" } },
    }), { responsive: true, displayModeBar: false });
}

function renderEdaCharts() {
    const eda = dashboardData?.eda || null;
    
    if (!eda) {
        console.warn("⚠ renderEdaCharts: No se encontraron datos en dashboardData.eda. Verifica que dashboard_data.json esté cargado correctamente.");
        // Mostrar mensaje visible en el dashboard en lugar de romper
        const chartsToEmpty = [
            "results-distribution-chart",
            "distance-goal-chart",
            "angle-goal-chart",
            "goals-per-match-chart",
            "xg-probability-distribution-chart",
            "xg-calibration-chart",
        ];
        chartsToEmpty.forEach(chartId => {
            const el = document.getElementById(chartId);
            if (el) {
                el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:360px;color:#94a3b8;font-size:13px;background:rgba(15,23,42,.5);border-radius:6px;">Datos EDA no disponibles — verifica dashboard_data.json</div>';
            }
        });
        return;
    }

    if (document.getElementById("results-distribution-chart")) {
        const chartConfig = {
            labels: eda.result_distribution?.labels || [],
            series: [{
                name: "Partidos",
                values: eda.result_distribution.values,
                color: ["#14b8a6", "#f59e0b", "#fb7185"],
                labelFormatter: (value) => `${Math.round(value)}`,
            }],
            title: "Distribución de resultados",
            subtitle: "Lectura rápida del equilibrio de partidos",
            yTitle: "Partidos",
            ySuffix: "",
            surface: "dark",
            height: 380,
            valueFormatter: (value) => `${Math.round(value)}`,
            fallback: {
                layout: darkBaseLayout("Partidos", { height: 360, xaxis: { title: { text: "Resultado" } } }),
                extra: { showlegend: false, bargap: 0.22 }
            }
        };

        if (!renderPremiumBarComparisonChart("results-distribution-chart", chartConfig)) {
            const chart = buildPremiumBarComparison({
                labels: eda.result_distribution?.labels || [],
                series: [{
                    name: "Partidos",
                    values: eda.result_distribution?.values || [],
                    color: ["#14b8a6", "#f59e0b", "#fb7185"],
                    capColor: ["rgba(255,255,255,.16)", "rgba(255,255,255,.14)", "rgba(255,255,255,.14)"],
                    shadowColor: "rgba(2,6,23,.34)",
                    text: (eda.result_distribution?.values || []).map(v => String(v)),
                    textposition: "outside",
                    hovertemplate: "%{x}: %{y} partidos<extra></extra>",
                }],
                layout: darkBaseLayout("Partidos", { height: 360, xaxis: { title: { text: "Resultado" } } }),
                extra: { showlegend: false, bargap: 0.22 }
            });
            Plotly.newPlot("results-distribution-chart", chart.data, chart.layout, { responsive: true, displayModeBar: false });
        }
    }

    if (document.getElementById("distance-goal-chart")) {
        const distData = eda.distance_to_goal || {};
        if (distData.no_gol && distData.gol) {
            Plotly.newPlot("distance-goal-chart", [
                { y: distData.no_gol, type: "box", name: "No gol", marker: { color: "#f59e0b" }, line: { color: "#f59e0b" }, fillcolor: "rgba(245,158,11,.25)", boxmean: true, jitter: .1, pointpos: 0, opacity: .85 },
                { y: distData.gol,    type: "box", name: "Gol",    marker: { color: "#10b981" }, line: { color: "#10b981" }, fillcolor: "rgba(16,185,129,.24)", boxmean: true, jitter: .1, pointpos: 0, opacity: .85 },
            ], darkBaseLayout("Distancia al arco", { height: 360, xaxis: { title: { text: "Desenlace" } } }), { responsive: true, displayModeBar: false });
        } else {
            renderEmptyDarkChart("distance-goal-chart", "Datos de distancia al arco no disponibles");
        }
    }

    if (document.getElementById("angle-goal-chart")) {
        const angleData = eda.angle_vs_goal || {};
        if (angleData.mean_angle && angleData.conversion_rate && angleData.shot_count) {
            Plotly.newPlot("angle-goal-chart", [{
                x: angleData.mean_angle,
                y: angleData.conversion_rate.map(v => v * 100),
                mode: "lines+markers", type: "scatter",
                marker: { color: "#7dd3fc", size: 9, line: { color: "#ffffff", width: 1 } },
                line: { color: "#10b981", width: 3, shape: "spline" },
                customdata: angleData.shot_count,
            hovertemplate: "Ángulo: %{x:.3f}<br>Tasa: %{y:.2f}%<br>Tiros: %{customdata}<extra></extra>",
            }], darkBaseLayout("Tasa de gol (%)", { height: 360, xaxis: { title: { text: "Ángulo medio (rad)" } } }), { responsive: true, displayModeBar: false });
        } else {
            renderEmptyDarkChart("angle-goal-chart", "Datos de ángulo no disponibles");
        }
    }

    if (document.getElementById("goals-per-match-chart")) {
        const goals = (eda.total_goals_per_match || []).map(Number).filter(Number.isFinite);
        if (goals && goals.length) {
            const meanGoals = goals.reduce((acc, val) => acc + val, 0) / goals.length;
            Plotly.newPlot("goals-per-match-chart", [{
                x: goals,
                type: "histogram",
                nbinsx: 16,
                marker: {
                    color: "rgba(16,185,129,.75)",
                    line: { color: "rgba(5,150,105,.95)", width: 1 },
                },
                hovertemplate: "Goles: %{x:.1f}<br>Frecuencia: %{y}<extra></extra>",
                name: "Partidos",
            }], darkBaseLayout("Frecuencia", {
                height: 360,
                xaxis: { title: { text: "Goles totales por partido" } },
                yaxis: { title: { text: "Número de partidos" } },
                shapes: [{
                    type: "line",
                    x0: meanGoals,
                    x1: meanGoals,
                    y0: 0,
                    y1: 1,
                    xref: "x",
                    yref: "paper",
                    line: { color: "#f59e0b", width: 2, dash: "dash" },
                }],
                annotations: [{
                    xref: "x",
                    yref: "paper",
                    x: meanGoals,
                    y: 0.98,
                    text: `Media: ${meanGoals.toFixed(2)}`,
                    showarrow: false,
                    xanchor: "left",
                    font: { color: "#fbbf24", size: 11 },
                    bgcolor: "rgba(15,23,42,.65)",
                    bordercolor: "rgba(245,158,11,.35)",
                    borderwidth: 1,
                }],
            }), { responsive: true, displayModeBar: false });
        } else {
            renderEmptyDarkChart("goals-per-match-chart", "Datos de goles por partido no disponibles");
        }
    }

    if (document.getElementById("xg-probability-distribution-chart")) {
        const probs = (eda.xg_probability_distribution || []).map(Number).filter(Number.isFinite);
        if (probs && probs.length) {
            const sorted = [...probs].sort((a, b) => a - b);
            const median = sorted[Math.floor(sorted.length * 0.5)] || 0;
            Plotly.newPlot("xg-probability-distribution-chart", [{
                x: probs,
                type: "histogram",
                nbinsx: 20,
                marker: {
                    color: "rgba(99,102,241,.72)",
                    line: { color: "rgba(67,56,202,.95)", width: 1 },
                },
                hovertemplate: "xG: %{x:.3f}<br>Frecuencia: %{y}<extra></extra>",
                name: "Tiros",
            }], darkBaseLayout("Frecuencia", {
                height: 360,
                xaxis: { title: { text: "Probabilidad xG del tiro" }, range: [0, 1] },
                yaxis: { title: { text: "Número de tiros" } },
                shapes: [{
                    type: "line",
                    x0: median,
                    x1: median,
                    y0: 0,
                    y1: 1,
                    xref: "x",
                    yref: "paper",
                    line: { color: "#fb7185", width: 2, dash: "dash" },
                }],
                annotations: [{
                    xref: "x",
                    yref: "paper",
                    x: median,
                    y: 0.98,
                    text: `Mediana: ${median.toFixed(3)}`,
                    showarrow: false,
                    xanchor: "left",
                    font: { color: "#fda4af", size: 11 },
                    bgcolor: "rgba(15,23,42,.65)",
                    bordercolor: "rgba(251,113,133,.35)",
                    borderwidth: 1,
                }],
            }), { responsive: true, displayModeBar: false });
        } else {
            renderEmptyDarkChart("xg-probability-distribution-chart", "Datos de distribución xG no disponibles");
        }
    }

    if (document.getElementById("xg-calibration-chart")) {
        const shots = (dashboardData.shot_map_global || dashboardData.shots || [])
            .map(shot => ({
                xg: Number(shot.xg_probability),
                goal: Number(shot.is_goal),
            }))
            .filter(shot => Number.isFinite(shot.xg) && Number.isFinite(shot.goal));

        if (shots.length) {
            const bins = 10;
            const observedX = [];
            const observedY = [];
            const counts = [];
            for (let i = 0; i < bins; i += 1) {
                const low = i / bins;
                const high = (i + 1) / bins;
                const inBin = shots.filter(shot => shot.xg >= low && (i === bins - 1 ? shot.xg <= high : shot.xg < high));
                if (!inBin.length) continue;
                const meanPred = inBin.reduce((acc, shot) => acc + shot.xg, 0) / inBin.length;
                const meanObs = inBin.reduce((acc, shot) => acc + shot.goal, 0) / inBin.length;
                observedX.push(meanPred * 100);
                observedY.push(meanObs * 100);
                counts.push(inBin.length);
            }

            Plotly.newPlot("xg-calibration-chart", [
                {
                    x: [0, 100],
                    y: [0, 100],
                    mode: "lines",
                    name: "Calibración perfecta",
                    line: { color: "rgba(148,163,184,.75)", width: 2, dash: "dash" },
                    hoverinfo: "skip",
                },
                {
                    x: observedX,
                    y: observedY,
                    mode: "lines+markers",
                    name: "Modelo xG",
                    marker: {
                        size: counts.map(count => Math.max(7, Math.sqrt(count) * 1.6)),
                        color: "rgba(16,185,129,.95)",
                        line: { color: "#ffffff", width: 1 },
                    },
                    line: { color: "#10b981", width: 3, shape: "spline" },
                    customdata: counts,
                    hovertemplate: "xG medio: %{x:.2f}%<br>Gol real: %{y:.2f}%<br>Tiros en bin: %{customdata}<extra></extra>",
                },
            ], darkBaseLayout("Frecuencia real de gol (%)", {
                height: 360,
                xaxis: { title: { text: "Probabilidad xG media por bin (%)" }, range: [0, 100] },
                yaxis: { title: { text: "Tasa real de gol por bin (%)" }, range: [0, 100] },
            }), { responsive: true, displayModeBar: false });
        }
    }
}

// ── TEAM FORM TREND (ROLLING GOALS) ─────────────────────
function renderTeamFormTrend() {
    const chartId = "team-form-trend-chart";
    const primaryId = "team-form-primary";
    const compareId = "team-form-compare";
    const indicatorId = "team-form-indicator";
    const chartEl = document.getElementById(chartId);
    const primaryEl = document.getElementById(primaryId);
    const compareEl = document.getElementById(compareId);
    if (!chartEl || !primaryEl || !compareEl) return;

    const source = (dashboardData.match_shot_options || []).map(match => ({
        date: match.date,
        home_team: normalizeTeamName(match.home_team),
        away_team: normalizeTeamName(match.away_team),
        home_goals: Number(match.fthg),
        away_goals: Number(match.ftag),
    }));
    if (!source.length) return;

    const teams = [...new Set(source.flatMap(match => [match.home_team, match.away_team]))].sort();
    if (!teams.length) return;

    const fillSelect = () => {
        primaryEl.innerHTML = "";
        compareEl.innerHTML = "";

        teams.forEach(team => {
            primaryEl.add(new Option(team, team));
            compareEl.add(new Option(team, team));
        });
        compareEl.add(new Option("Sin comparar", ""), 0);

        primaryEl.value = teams.includes("Arsenal") ? "Arsenal" : teams[0];
        const fallbackCompare = teams.find(team => team !== primaryEl.value) || "";
        compareEl.value = teams.includes("Man City") && "Man City" !== primaryEl.value ? "Man City" : fallbackCompare;
    };

    const buildTeamSeries = (team, windowSize = 5) => {
        const teamMatches = source
            .filter(match => match.home_team === team || match.away_team === team)
            .map(match => {
                const isHome = match.home_team === team;
                const goalsFor = isHome ? match.home_goals : match.away_goals;
                const goalsAgainst = isHome ? match.away_goals : match.home_goals;
                const result = goalsFor > goalsAgainst ? "W" : goalsFor < goalsAgainst ? "L" : "D";
                const parsedDate = new Date(match.date);
                return {
                    date: match.date,
                    parsedDate,
                    goalsFor,
                    goalsAgainst,
                    result,
                    opponent: isHome ? match.away_team : match.home_team,
                };
            })
            .filter(row => !Number.isNaN(row.parsedDate.getTime()))
            .sort((a, b) => a.parsedDate - b.parsedDate);

        const rolling = teamMatches.map((_, idx) => {
            if (idx + 1 < windowSize) return null;
            const slice = teamMatches.slice(idx - windowSize + 1, idx + 1);
            return slice.reduce((acc, row) => acc + row.goalsFor, 0) / slice.length;
        });

        return teamMatches.map((row, idx) => ({ ...row, rollingGoals: rolling[idx] }));
    };

    const render = () => {
        const primaryTeam = primaryEl.value;
        const compareTeam = compareEl.value;
        if (!primaryTeam) return;

        const primarySeries = buildTeamSeries(primaryTeam, 5);
        if (!primarySeries.length) return;
        const primaryRolling = primarySeries.filter(row => row.rollingGoals !== null);
        if (!primaryRolling.length) return;

        const traces = [
            {
                x: primaryRolling.map(row => row.date),
                y: primaryRolling.map(row => row.rollingGoals),
                mode: "lines+markers",
                name: `${primaryTeam} rolling x5`,
                line: { color: "#38bdf8", width: 3, shape: "spline" },
                fill: "tozeroy",
                fillcolor: "rgba(56,189,248,.12)",
                marker: {
                    size: 2,
                    color: "rgba(255,255,255,.35)",
                    line: { color: "rgba(255,255,255,.2)", width: 1 },
                },
                customdata: primaryRolling.map(row => [row.goalsFor, row.result, row.goalsAgainst, row.opponent]),
                hovertemplate: "Fecha: %{x}<br>Goles partido: %{customdata[0]}<br>Rolling(5): %{y:.2f}<br>Resultado: %{customdata[1]}<br>Rival: %{customdata[3]}<br>GC: %{customdata[2]}<extra></extra>",
            },
        ];

        let compareLatest = null;
        if (compareTeam && compareTeam !== primaryTeam) {
            const compareSeries = buildTeamSeries(compareTeam, 5);
            const compareRolling = compareSeries.filter(row => row.rollingGoals !== null);
            if (compareRolling.length) {
                compareLatest = compareRolling[compareRolling.length - 1].rollingGoals;
                traces.push({
                    x: compareRolling.map(row => row.date),
                    y: compareRolling.map(row => row.rollingGoals),
                    mode: "lines+markers",
                    name: `${compareTeam} rolling x5`,
                    line: { color: "#a78bfa", width: 3, shape: "spline", dash: "dot" },
                    fill: "tozeroy",
                    fillcolor: "rgba(167,139,250,.10)",
                    marker: {
                        size: 2,
                        color: "rgba(255,255,255,.30)",
                        line: { color: "rgba(255,255,255,.2)", width: 1 },
                    },
                    customdata: compareRolling.map(row => [row.goalsFor, row.result, row.goalsAgainst, row.opponent]),
                    hovertemplate: "Fecha: %{x}<br>Goles partido: %{customdata[0]}<br>Rolling(5): %{y:.2f}<br>Resultado: %{customdata[1]}<br>Rival: %{customdata[3]}<br>GC: %{customdata[2]}<extra></extra>",
                });
            }
        }

        const primaryLatest = primaryRolling[primaryRolling.length - 1].rollingGoals;
        if (compareLatest !== null) {
            const diff = primaryLatest - compareLatest;
            if (diff > 0) {
                setText(indicatorId, `Equipo en mejor forma → ${primaryTeam} (+${diff.toFixed(2)} goles rolling vs ${compareTeam})`);
            } else if (diff < 0) {
                setText(indicatorId, `Equipo en mejor forma → ${compareTeam} (+${Math.abs(diff).toFixed(2)} goles rolling vs ${primaryTeam})`);
            } else {
                setText(indicatorId, `Forma reciente pareja → ${primaryTeam} y ${compareTeam} (empate en rolling: ${primaryLatest.toFixed(2)})`);
            }
        } else {
            setText(indicatorId, `Forma reciente actual → ${primaryTeam} (${primaryLatest.toFixed(2)} goles rolling en los últimos 5 partidos)`);
        }

        Plotly.newPlot(chartId, traces, darkBaseLayout("Goles (rolling x5)", {
            height: 360,
            xaxis: { title: { text: "Fecha" } },
            yaxis: { title: { text: "Goles / rolling promedio" } },
            legend: { orientation: "h", y: 1.12, x: 0, xanchor: "left" },
        }), { responsive: true, displayModeBar: false });
    };

    fillSelect();
    if (!primaryEl.dataset.bound) {
        primaryEl.addEventListener("change", () => {
            if (compareEl.value === primaryEl.value) compareEl.value = "";
            render();
        });
        compareEl.addEventListener("change", () => {
            if (compareEl.value === primaryEl.value) compareEl.value = "";
            render();
        });
        primaryEl.dataset.bound = "1";
    }
    render();
}

// ── xG PERFORMANCE CHARTS ────────────────────────────────
function renderXgPerformanceCharts() {
    const roc = dashboardData.xg_roc_curve;

    if (document.getElementById("xg-roc-chart")) {
        Plotly.newPlot("xg-roc-chart", [
            { x: roc.fpr, y: roc.tpr, mode: "lines", name: `ROC (AUC=${dashboardData.xg_metrics.auc_roc.toFixed(3)})`, line: { color: "#10b981", width: 3, shape: "spline" }, fill: "tozeroy", fillcolor: "rgba(16,185,129,.12)" },
            { x: [0,1],   y: [0,1],   mode: "lines", name: "Azar", line: { color: "rgba(107,117,133,.5)", width: 1.5, dash: "dash" }, hoverinfo: "skip" },
        ], baseLayout("TPR", { height: 360, xaxis: { title: { text: "FPR" }, range: [0,1] }, yaxis: { range: [0,1] } }), { responsive: true, displayModeBar: false });
    }
}

// ── CONFUSION MATRIX ──────────────────────────────────────
function renderConfusionMatrix() {
    if (!document.getElementById("confusion-chart")) return;
    const m = dashboardData.confusion_matrix.values;
    Plotly.newPlot("confusion-chart", [{
        z: m, x: dashboardData.confusion_matrix.labels, y: dashboardData.confusion_matrix.labels,
        type: "heatmap",
        colorscale: [[0,"#eef2ff"],[.45,"#86efac"],[1,"#059669"]],
        showscale: false, text: m, texttemplate: "%{text}",
        hovertemplate: "Real: %{y}<br>Pred: %{x}<br>Partidos: %{z}<extra></extra>",
    }], {
        paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(15,23,42,.28)",
        margin: { t: 10, r: 10, b: 54, l: 72 },
        font: { color: PLOTLY_READABLE_TEXT, family: "Inter, sans-serif", size: 13 },
        xaxis: ensurePlotlyAxisContrast({ title: { text: "Predicción" } }),
        yaxis: ensurePlotlyAxisContrast({ title: { text: "Valor real" } }),
        height: 360,
        hoverlabel: ensurePlotlyHoverContrast({
            bordercolor: "rgba(255,255,255,.18)",
            font: { family: "Inter, sans-serif", size: 12 },
        }),
    }, { responsive: true, displayModeBar: false });
}

// ── NARRATIVE ─────────────────────────────────────────────
function renderNarrative() {
    const sum = dashboardData.project_summary;
    const xg  = dashboardData.xg_metrics;
    const acc = dashboardData.match_accuracy;
    const gap = sum.ventaja_sobre_benchmark;
    const benchmarkVerdict = sum.modelo_supera_benchmark
        ? `superando el benchmark de Bet365 (${sum.benchmark_bet365.toFixed(1)}%) por ${gap.toFixed(1)} pp`
        : `sin superar el benchmark de Bet365 (${sum.benchmark_bet365.toFixed(1)}%), quedando a ${Math.abs(gap).toFixed(1)} pp`;

    const body = `El predictor logístico alcanza un ${formatPct(acc)} de accuracy, ${benchmarkVerdict}. ` +
        `La ventaja es sistemática a través de k=5 folds de validación cruzada. ` +
        `El modelo xG valida que ángulo y distancia proveen señal discriminativa firme (AUC: ${xg.auc_roc.toFixed(3)}). ` +
        `En conjunto, el pipeline demuestra que existe señal predictiva medible en los datos pre-partido de la Premier League.`;

    setText("metrics-synthesis", body);

    const silEl = document.getElementById("kpi-sil");
    if (silEl && dashboardData.clustering_metrics) {
        silEl.textContent = dashboardData.clustering_metrics.silhouette_score.toFixed(3);
    }

    const list = document.getElementById("limitations-list");
    if (list && sum.limitaciones) {
        list.innerHTML = "";
        sum.limitaciones.forEach(lim => {
            const li = document.createElement("li");
            li.textContent = lim;
            list.appendChild(li);
        });
    }

    const workshopList = document.getElementById("workshop-list");
    const workshopChecklist = dashboardData.workshop_checklist || {};
    if (workshopList) {
        workshopList.innerHTML = "";
        Object.entries(workshopChecklist).forEach(([key, ok]) => {
            const li = document.createElement("li");
            const label = key.replaceAll("_", " ").replace(/\b\w/g, chr => chr.toUpperCase());
            li.textContent = `${ok ? "Cumple" : "Pendiente"}: ${label}`;
            workshopList.appendChild(li);
        });
    }
}

// ── CROSS-VAL ─────────────────────────────────────────────
function renderCrossValComparison() {
    if (!document.getElementById("cv-comparison-chart")) return;
    const mm = dashboardData.match_metrics;
    const chartConfig = {
        labels: ["Holdout Test Set", "Validación Cruzada 5F"],
        series: [{
            name: "Accuracy",
            values: [mm.accuracy * 100, mm.cv_mean_accuracy * 100],
            color: ["#14b8a6", "#6366f1"],
        }],
        title: "Holdout vs validación cruzada",
        subtitle: `Desvío CV: ±${(mm.cv_std_accuracy * 100).toFixed(1)} pp`,
        yTitle: "Accuracy (%)",
        ySuffix: "%",
        surface: "light",
        height: 380,
        yMax: 100,
        fallback: {
            layout: baseLayout("Accuracy (%)", { height: 360 }),
            extra: { showlegend: false, bargap: 0.24 }
        }
    };

    if (!renderPremiumBarComparisonChart("cv-comparison-chart", chartConfig)) {
        const chart = buildPremiumBarComparison({
            labels: ["Holdout Test Set", "Validación Cruzada 5F"],
            series: [{
                name: "Accuracy",
                values: [mm.accuracy * 100, mm.cv_mean_accuracy * 100],
                color: ["#14b8a6", "#6366f1"],
                capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                shadowColor: "rgba(2,6,23,.28)",
                text: [`${(mm.accuracy*100).toFixed(1)}%`,`${(mm.cv_mean_accuracy*100).toFixed(1)}%`],
                textposition: "auto",
                hovertemplate: "%{x}<br>Accuracy: %{y:.1f}%<extra></extra>",
                errorY: { type:"data", array:[0, mm.cv_std_accuracy*100], visible:true, color:"#10b981", thickness:2 },
            }],
            layout: baseLayout("Accuracy (%)", { height: 360 }),
            extra: { showlegend: false, bargap: 0.24 }
        });
        Plotly.newPlot("cv-comparison-chart", chart.data, chart.layout, { responsive:true, displayModeBar:false });
    }
}

// ── LINEAR RESIDUALS ─────────────────────────────────────
function renderLinearResiduals() {
    if (!document.getElementById("linear-residuals-chart")) return;
    const residuals = (dashboardData.eda?.linear_residuals || [])
        .map(Number)
        .filter(Number.isFinite);
    if (!residuals.length) return;

    const meanResidual = residuals.reduce((acc, value) => acc + value, 0) / residuals.length;
    const rmseResidual = Math.sqrt(residuals.reduce((acc, value) => acc + (value ** 2), 0) / residuals.length);

    Plotly.newPlot(
        "linear-residuals-chart",
        [{
            x: residuals,
            type: "histogram",
            nbinsx: 24,
            marker: {
                color: "rgba(99,102,241,.72)",
                line: { color: "rgba(79,70,229,.95)", width: 1 },
            },
            hovertemplate: "Residual: %{x:.3f}<br>Frecuencia: %{y}<extra></extra>",
            name: "Residuos",
        }],
        baseLayout("Frecuencia", {
            height: 360,
            xaxis: { title: { text: "Residual (goles reales - goles predichos)" } },
            yaxis: { title: { text: "Frecuencia" } },
            shapes: [{
                type: "line",
                x0: 0,
                x1: 0,
                y0: 0,
                y1: 1,
                xref: "x",
                yref: "paper",
                line: { color: "#ef4444", width: 2, dash: "dash" },
            }],
            annotations: [{
                xref: "paper",
                yref: "paper",
                x: 0.98,
                y: 0.98,
                xanchor: "right",
                yanchor: "top",
                showarrow: false,
                align: "right",
                text: `media: ${meanResidual.toFixed(3)}<br>RMSE: ${rmseResidual.toFixed(3)}`,
                font: { size: 11, color: "#334155" },
                bgcolor: "rgba(255,255,255,.92)",
                bordercolor: "rgba(15,23,42,.12)",
                borderwidth: 1,
            }],
        }),
        { responsive: true, displayModeBar: false }
    );
}

// ── MODEL METRICS COMPARISON ─────────────────────────────
function renderModelMetricsComparison() {
    if (!document.getElementById("model-metrics-comparison-chart")) return;

    const mm = dashboardData.match_metrics || {};
    const xg = dashboardData.xg_metrics || {};
    const labels = ["Accuracy", "Precision", "Recall", "F1"];
    const matchValues = [
        Number(mm.accuracy || 0) * 100,
        Number(mm.precision_weighted || 0) * 100,
        Number(mm.recall_weighted || 0) * 100,
        Number(mm.f1_weighted || 0) * 100,
    ];
    const xgValues = [
        Number(xg.accuracy || 0) * 100,
        Number(xg.precision || 0) * 100,
        Number(xg.recall || 0) * 100,
        Number(xg.f1 || 0) * 100,
    ];

    const chartConfig = {
        labels,
        series: [
            {
                name: "Match Predictor (weighted)",
                values: matchValues,
                color: ["#6366f1", "#6366f1", "#6366f1", "#6366f1"],
            },
            {
                name: "xG Model",
                values: xgValues,
                color: ["#10b981", "#10b981", "#10b981", "#10b981"],
            },
        ],
        title: "xG vs Match Predictor",
        subtitle: "Comparación de métricas en escala común",
        yTitle: "Valor (%)",
        ySuffix: "%",
        surface: "light",
        height: 380,
        yMax: 100,
        fallback: {
            layout: baseLayout("Valor (%)", { height: 360, yaxis: { range: [0, 105] } }),
            extra: { showlegend: true, bargap: 0.2, bargroupgap: 0.12 },
        },
    };

    if (!renderPremiumBarComparisonChart("model-metrics-comparison-chart", chartConfig)) {
        const chart = buildPremiumBarComparison({
            labels,
            series: [
                {
                    name: "Match Predictor (weighted)",
                    values: matchValues,
                    color: ["#6366f1", "#6366f1", "#6366f1", "#6366f1"],
                    capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)", "rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: matchValues.map(v => `${v.toFixed(1)}%`),
                    textposition: "outside",
                    hovertemplate: "%{x}<br>Match: %{y:.1f}%<extra></extra>",
                },
                {
                    name: "xG Model",
                    values: xgValues,
                    color: ["#10b981", "#10b981", "#10b981", "#10b981"],
                    capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)", "rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: xgValues.map(v => `${v.toFixed(1)}%`),
                    textposition: "outside",
                    hovertemplate: "%{x}<br>xG: %{y:.1f}%<extra></extra>",
                },
            ],
            layout: baseLayout("Valor (%)", { height: 360, yaxis: { range: [0, 105] } }),
            extra: { showlegend: true, bargap: 0.2, bargroupgap: 0.12 },
        });
        Plotly.newPlot("model-metrics-comparison-chart", chart.data, chart.layout, { responsive: true, displayModeBar: false });
    }
}

// ── CLASS METRICS (H/D/A) ───────────────────────────────
function renderClassMetricsChart() {
    if (!document.getElementById("class-metrics-chart")) return;
    const classMetrics = dashboardData.match_metrics?.class_metrics || [];
    if (!classMetrics.length) return;

    const labels = classMetrics.map(row => row.result);
    const precisionValues = classMetrics.map(row => Number(row.precision || 0) * 100);
    const recallValues = classMetrics.map(row => Number(row.recall || 0) * 100);
    const f1Values = classMetrics.map(row => Number(row.f1 || 0) * 100);

    const chartConfig = {
        labels,
        series: [
            { name: "Precision", values: precisionValues, color: ["#3b82f6", "#3b82f6", "#3b82f6"] },
            { name: "Recall", values: recallValues, color: ["#14b8a6", "#14b8a6", "#14b8a6"] },
            { name: "F1", values: f1Values, color: ["#f59e0b", "#f59e0b", "#f59e0b"] },
        ],
        title: "Métricas por clase (H/D/A)",
        subtitle: "Evaluación detallada para Local, Empate y Visitante",
        yTitle: "Valor (%)",
        ySuffix: "%",
        surface: "light",
        height: 380,
        yMax: 100,
        fallback: {
            layout: baseLayout("Valor (%)", { height: 360, yaxis: { range: [0, 105] } }),
            extra: { showlegend: true, bargap: 0.2, bargroupgap: 0.12 },
        },
    };

    if (!renderPremiumBarComparisonChart("class-metrics-chart", chartConfig)) {
        const chart = buildPremiumBarComparison({
            labels,
            series: [
                {
                    name: "Precision",
                    values: precisionValues,
                    color: ["#3b82f6", "#3b82f6", "#3b82f6"],
                    capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: precisionValues.map(v => `${v.toFixed(1)}%`),
                    textposition: "outside",
                    hovertemplate: "%{x}<br>Precision: %{y:.1f}%<extra></extra>",
                },
                {
                    name: "Recall",
                    values: recallValues,
                    color: ["#14b8a6", "#14b8a6", "#14b8a6"],
                    capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: recallValues.map(v => `${v.toFixed(1)}%`),
                    textposition: "outside",
                    hovertemplate: "%{x}<br>Recall: %{y:.1f}%<extra></extra>",
                },
                {
                    name: "F1",
                    values: f1Values,
                    color: ["#f59e0b", "#f59e0b", "#f59e0b"],
                    capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: f1Values.map(v => `${v.toFixed(1)}%`),
                    textposition: "outside",
                    hovertemplate: "%{x}<br>F1: %{y:.1f}%<extra></extra>",
                },
            ],
            layout: baseLayout("Valor (%)", { height: 360, yaxis: { range: [0, 105] } }),
            extra: { showlegend: true, bargap: 0.2, bargroupgap: 0.12 },
        });
        Plotly.newPlot("class-metrics-chart", chart.data, chart.layout, { responsive: true, displayModeBar: false });
    }
}

// ── ABLATION (ODDS VS ODDS+FORM / HISTORICAL / BENCHMARK) ────────────────────────
function renderAblationComparison() {
    if (!document.getElementById("ablation-comparison-chart")) return;
    const comparison = dashboardData.advanced_metrics?.model_comparison || null;
    const bet365Cv = Number(dashboardData.match_metrics?.bet365_cv_accuracy || 0) * 100;
    const bet365Holdout = Number(dashboardData.match_metrics?.bet365_holdout_accuracy || 0) * 100;
    if (!comparison) return;

    const oddsOnlyCv = Number(comparison.odds_only_cv_accuracy || 0) * 100;
    const historicalOnlyCv = Number(comparison.historical_only_cv_accuracy || 0) * 100;
    const combinedCv = Number(comparison.combined_cv_accuracy || 0) * 100;
    const oddsOnlyHoldout = Number(comparison.odds_only_holdout_accuracy || 0) * 100;
    const historicalOnlyHoldout = Number(comparison.historical_only_holdout_accuracy || 0) * 100;
    const combinedHoldout = Number(comparison.combined_holdout_accuracy || 0) * 100;

    const chartConfig = {
        labels: ["CV (k=5)", "Holdout"],
        series: [
            {
                name: "Odds only",
                values: [oddsOnlyCv, oddsOnlyHoldout],
                color: ["#14B8A6", "#14B8A6"],
            },
            {
                name: "Historical only",
                values: [historicalOnlyCv, historicalOnlyHoldout],
                color: ["#F59E0B", "#F59E0B"],
            },
            {
                name: "Combined",
                values: [combinedCv, combinedHoldout],
                color: ["#2563EB", "#2563EB"],
            },
            {
                name: "Bet365 benchmark",
                values: [bet365Cv, bet365Holdout],
                color: ["#0F172A", "#0F172A"],
            },
        ],
        title: "Comparación pre-partido: odds / histórico / combinado / Bet365",
        subtitle: "Accuracy en CV y holdout para las estrategias estudiadas",
        yTitle: "Accuracy (%)",
        ySuffix: "%",
        surface: "light",
        height: 380,
        yMax: 100,
        fallback: {
            layout: baseLayout("Accuracy (%)", { height: 360, yaxis: { range: [0, 105] } }),
            extra: { showlegend: true, bargap: 0.2, bargroupgap: 0.12 },
        },
    };

    if (!renderPremiumBarComparisonChart("ablation-comparison-chart", chartConfig)) {
        const chart = buildPremiumBarComparison({
            labels: ["CV (k=5)", "Holdout"],
            series: [
                {
                    name: "Odds only",
                    values: [oddsOnlyCv, oddsOnlyHoldout],
                    color: ["#fb7185", "#fb7185"],
                    capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: [oddsOnlyCv, oddsOnlyHoldout].map(v => `${v.toFixed(1)}%`),
                    textposition: "outside",
                    hovertemplate: "%{x}<br>Odds only: %{y:.1f}%<extra></extra>",
                },
                {
                    name: "Historical only",
                    values: [historicalOnlyCv, historicalOnlyHoldout],
                    color: ["#f59e0b", "#f59e0b"],
                    capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: [historicalOnlyCv, historicalOnlyHoldout].map(v => `${v.toFixed(1)}%`),
                    textposition: "outside",
                    hovertemplate: "%{x}<br>Historical only: %{y:.1f}%<extra></extra>",
                },
                {
                    name: "Combined",
                    values: [combinedCv, combinedHoldout],
                    color: ["#10b981", "#10b981"],
                    capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: [combinedCv, combinedHoldout].map(v => `${v.toFixed(1)}%`),
                    textposition: "outside",
                    hovertemplate: "%{x}<br>Combined: %{y:.1f}%<extra></extra>",
                },
                {
                    name: "Bet365 benchmark",
                    values: [bet365Cv, bet365Holdout],
                    color: ["#3b82f6", "#3b82f6"],
                    capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: [bet365Cv, bet365Holdout].map(v => `${v.toFixed(1)}%`),
                    textposition: "outside",
                    hovertemplate: "%{x}<br>Bet365: %{y:.1f}%<extra></extra>",
                },
            ],
            layout: baseLayout("Accuracy (%)", { height: 360, yaxis: { range: [0, 105] } }),
            extra: { showlegend: true, bargap: 0.2, bargroupgap: 0.12 },
        });
        Plotly.newPlot("ablation-comparison-chart", chart.data, chart.layout, { responsive: true, displayModeBar: false });
    }
}

// ── BASELINE XG ───────────────────────────────────────────
function renderBaselineXg() {
    if (!document.getElementById("xg-baseline-chart")) return;
    const xg = dashboardData.xg_metrics;
    const d = [
        { label:"Baseline (Naïve)", accuracy: xg.naive_accuracy*100, auc:50 },
        { label:"Modelo xG",        accuracy: xg.accuracy*100,       auc: xg.auc_roc*100 },
    ];
    const chartConfig = {
        labels: d.map(r => r.label),
        series: [
            {
                name: "Accuracy",
                values: d.map(r => r.accuracy),
                color: ["#f59e0b", "#14b8a6"],
            },
            {
                name: "AUC ROC",
                values: d.map(r => r.auc),
                color: ["#10b981", "#6366f1"],
            }
        ],
        title: "Baseline ingenuo vs modelo xG",
        subtitle: "Comparación de desempeño del modelo frente a una referencia trivial",
        yTitle: "Métrica (%)",
        ySuffix: "%",
        surface: "light",
        height: 380,
        yMax: 100,
        fallback: {
            layout: baseLayout("Métrica (%)", { height: 360 }),
            extra: { showlegend: true, bargap: 0.22, bargroupgap: 0.15 }
        }
    };

    if (!renderPremiumBarComparisonChart("xg-baseline-chart", chartConfig)) {
        const chart = buildPremiumBarComparison({
            labels: d.map(r => r.label),
            series: [
                {
                    name: "Accuracy",
                    values: d.map(r => r.accuracy),
                    color: ["#f59e0b", "#14b8a6"],
                    capColor: ["rgba(255,255,255,.16)", "rgba(255,255,255,.16)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: d.map(r => `${r.accuracy.toFixed(1)}%`),
                    textposition: "auto",
                    hovertemplate: "%{x}<br>Accuracy: %{y:.1f}%<extra></extra>",
                },
                {
                    name: "AUC ROC",
                    values: d.map(r => r.auc),
                    color: ["#10b981", "#6366f1"],
                    capColor: ["rgba(255,255,255,.16)", "rgba(255,255,255,.16)"],
                    shadowColor: "rgba(2,6,23,.28)",
                    text: d.map(r => `${r.auc.toFixed(1)}`),
                    textposition: "auto",
                    hovertemplate: "%{x}<br>AUC: %{y:.1f}<extra></extra>",
                }
            ],
            layout: baseLayout("Métrica (%)", { height: 360 }),
            extra: { showlegend: true, bargap: 0.22, bargroupgap: 0.15 }
        });
        Plotly.newPlot("xg-baseline-chart", chart.data, chart.layout, { responsive:true, displayModeBar:false });
    }
}

// ── RF COMPARISON ─────────────────────────────────────────
function renderRfComparison() {
    if (!document.getElementById("rf-comparison-chart")) return;
    const mm  = dashboardData.match_metrics;
    const adv = dashboardData.advanced_metrics || {};
    const chartConfig = {
        labels: ["Regresión Logística", "Random Forest"],
        series: [{
            name: "Accuracy",
            values: [mm.accuracy*100, (adv.random_forest_accuracy||0)*100],
            color: ["#6366f1","#10b981"],
        }],
        title: "Regresión logística vs Random Forest",
        subtitle: "Comparativa entre el modelo base y el modelo no lineal",
        yTitle: "Accuracy (%)",
        ySuffix: "%",
        surface: "light",
        height: 380,
        yMax: 100,
        fallback: {
            layout: baseLayout("Accuracy (%)", { height: 360 }),
            extra: { showlegend: false, bargap: 0.26 }
        }
    };

    if (!renderPremiumBarComparisonChart("rf-comparison-chart", chartConfig)) {
        const chart = buildPremiumBarComparison({
            labels: ["Regresión Logística", "Random Forest"],
            series: [{
                name: "Accuracy",
                values: [mm.accuracy*100, (adv.random_forest_accuracy||0)*100],
                color: ["#6366f1","#10b981"],
                capColor: ["rgba(255,255,255,.18)", "rgba(255,255,255,.18)"],
                shadowColor: "rgba(2,6,23,.28)",
                text: [`${(mm.accuracy*100).toFixed(1)}%`,`${((adv.random_forest_accuracy||0)*100).toFixed(1)}%`],
                textposition: "auto",
                hovertemplate: "%{x}<br>Acc: %{y:.1f}%<extra></extra>",
            }],
            layout: baseLayout("Accuracy (%)", { height: 360 }),
            extra: { showlegend: false, bargap: 0.26 }
        });
        Plotly.newPlot("rf-comparison-chart", chart.data, chart.layout, { responsive:true, displayModeBar:false });
    }
}

// ── CLUSTERING ────────────────────────────────────────────
function renderClustering() {
    if (!document.getElementById("clustering-team-chart")) return;
    const pts = dashboardData.clustering_metrics.points || [];
    if (!pts.length) return;
    const COLORS = ["#10b981","#6366f1","#f59e0b"];
    const attackMean = pts.reduce((acc, point) => acc + Number(point.goals_scored_avg || 0), 0) / pts.length;
    const defenseMean = pts.reduce((acc, point) => acc + Number(point.goals_conceded_avg || 0), 0) / pts.length;

    const profileTitle = (attack, defense) => {
        if (attack >= attackMean && defense <= defenseMean) return "Balance competitivo";
        if (attack >= attackMean && defense > defenseMean) return "Ataque fuerte, defensa abierta";
        if (attack < attackMean && defense <= defenseMean) return "Bloque sólido, ataque corto";
        return "Perfil reactivo";
    };

    [0,1,2].forEach(clusterId => {
        const group = pts.filter(point => point.cluster === clusterId);
        if (!group.length) return;
        const attack = group.reduce((acc, point) => acc + Number(point.goals_scored_avg || 0), 0) / group.length;
        const defense = group.reduce((acc, point) => acc + Number(point.goals_conceded_avg || 0), 0) / group.length;
        const examples = group
            .slice()
            .sort((a, b) => Number(b.goals_scored_avg || 0) - Number(a.goals_scored_avg || 0))
            .slice(0, 3)
            .map(point => point.team)
            .join(", ");

        setText(`cluster-summary-${clusterId}-title`, profileTitle(attack, defense));
        setText(
            `cluster-summary-${clusterId}-body`,
            `${group.length} equipos · GF ${attack.toFixed(2)} · GC ${defense.toFixed(2)}. Referentes: ${examples}.`
        );
    });

    const traces = [0,1,2].map(c => {
        const g = pts.filter(p => p.cluster === c);
        const centroidX = g.reduce((acc, point) => acc + Number(point.goals_scored_avg || 0), 0) / g.length;
        const centroidY = g.reduce((acc, point) => acc + Number(point.goals_conceded_avg || 0), 0) / g.length;
        return {
            x: g.map(p=>p.goals_scored_avg), y: g.map(p=>p.goals_conceded_avg),
            text: g.map(p=>p.team), mode:"markers+text", textposition:"top center",
            name:`Cluster ${c+1}`,
            marker: { size:16, color:COLORS[c], opacity:.92, line:{color:"#fff",width:1.5} },
            textfont: { size:10, color: PLOTLY_READABLE_TEXT },
            customdata: g.map(() => [centroidX, centroidY, profileTitle(centroidX, centroidY)]),
            hovertemplate:"<b>%{text}</b><br>GF/partido: %{x:.2f}<br>GC/partido: %{y:.2f}<br>Perfil: %{customdata[2]}<extra></extra>",
        };
    }).concat([0,1,2].map(c => {
        const g = pts.filter(p => p.cluster === c);
        const centroidX = g.reduce((acc, point) => acc + Number(point.goals_scored_avg || 0), 0) / g.length;
        const centroidY = g.reduce((acc, point) => acc + Number(point.goals_conceded_avg || 0), 0) / g.length;
        return {
            x: [centroidX],
            y: [centroidY],
            mode: "markers",
            name: `Centro cluster ${c+1}`,
            showlegend: false,
            marker: {
                size: 24,
                color: COLORS[c],
                symbol: "diamond",
                line: { color: "rgba(15,23,42,.85)", width: 2.5 },
            },
            hovertemplate: `<b>Centro Cluster ${c+1}</b><br>GF: %{x:.2f}<br>GC: %{y:.2f}<extra></extra>`,
        };
    }));

    Plotly.newPlot("clustering-team-chart", traces, {
        ...baseLayout("Goles recibidos/partido", {
            height: 520,
            xaxis:{title:{text:"Goles anotados/partido"}},
            legend:{orientation:"h",y:-0.18},
            shapes: [
                {
                    type: "line",
                    x0: attackMean,
                    x1: attackMean,
                    y0: 0,
                    y1: 1,
                    xref: "x",
                    yref: "paper",
                    line: { color: "rgba(59,130,246,.35)", width: 1.5, dash: "dot" },
                },
                {
                    type: "line",
                    x0: 0,
                    x1: 1,
                    y0: defenseMean,
                    y1: defenseMean,
                    xref: "paper",
                    yref: "y",
                    line: { color: "rgba(16,185,129,.35)", width: 1.5, dash: "dot" },
                },
            ],
            annotations: [
                {
                    xref: "paper",
                    yref: "paper",
                    x: 0.99,
                    y: 0.03,
                    text: "Más gol a favor →",
                    showarrow: false,
                    xanchor: "right",
                    font: { size: 11, color: PLOTLY_READABLE_TEXT },
                },
                {
                    xref: "paper",
                    yref: "paper",
                    x: 0.01,
                    y: 0.03,
                    text: "Mejor defensa",
                    showarrow: false,
                    xanchor: "left",
                    font: { size: 11, color: PLOTLY_READABLE_TEXT },
                },
            ],
        }),
    }, { responsive:true, displayModeBar:false });
}

// ── LAYOUT HELPERS ────────────────────────────────────────
// ── ECHARTS HELPERS ───────────────────────────────────────
const DASHBOARD_ECHARTS = new Map();
let dashboardEchartsResizeBound = false;

function bindDashboardEchartsResize() {
    if (dashboardEchartsResizeBound) return;
    dashboardEchartsResizeBound = true;
    window.addEventListener("resize", () => {
        DASHBOARD_ECHARTS.forEach(chart => {
            try { chart.resize(); } catch (_) {}
        });
    });
}

function disposeDashboardChart(domId) {
    const existing = DASHBOARD_ECHARTS.get(domId);
    if (existing) {
        try { existing.dispose(); } catch (_) {}
        DASHBOARD_ECHARTS.delete(domId);
    }
}

function renderPremiumBarComparisonChart(domId, config = {}) {
    const el = document.getElementById(domId);
    if (!el || !window.echarts) return false;

    bindDashboardEchartsResize();
    disposeDashboardChart(domId);

    const echarts = window.echarts;
    const palette = ["#14b8a6", "#6366f1", "#f59e0b", "#fb7185", "#22c55e", "#38bdf8"];
    const paletteAlt = ["#2563EB", "#0F172A", "#14B8A6", "#F59E0B", "#4338ca", "#0ea5e9"];
    const surface = "light";
    const isLight = false;
    const theme = {
        title: "#E2E8F0",
        subtitle: "rgba(226,232,240,.72)",
        axis: "#E2E8F0",
        axisSoft: "rgba(226,232,240,.62)",
        grid: "rgba(255,255,255,.10)",
        labelText: "#FFFFFF",
        labelBg: "rgba(15,23,42,.78)",
        labelBorder: "rgba(255,255,255,.16)",
        tooltipBg: "#0F172A",
        tooltipText: "#FFFFFF",
        legend: "#E2E8F0",
    };
    const ySuffix = config.ySuffix ?? "%";
    const title = config.title || "";
    const subtitle = config.subtitle || "";
    const labels = config.labels || [];
    const series = config.series || [];

    const chart = echarts.init(el, null, { renderer: "canvas" });
    const option = {
        backgroundColor: "transparent",
        title: title ? {
            text: title,
            subtext: subtitle,
            left: 16,
            top: 10,
            textStyle: {
                color: theme.title,
                fontSize: 17,
                fontWeight: 800,
                fontFamily: "Inter, sans-serif",
            },
            subtextStyle: {
                color: theme.subtitle,
                fontSize: 12,
                fontFamily: "Inter, sans-serif",
            }
        } : undefined,
        legend: series.length > 1 ? {
            show: true,
            bottom: 8,
            left: "center",
            itemWidth: 14,
            itemHeight: 10,
            textStyle: {
                color: theme.legend,
                fontFamily: "Inter, sans-serif",
                fontSize: 12,
                fontWeight: 600,
            }
        } : { show: false },
        tooltip: {
            trigger: "axis",
            axisPointer: { type: "shadow" },
            backgroundColor: theme.tooltipBg,
            borderColor: isLight ? "rgba(15,23,42,.08)" : "rgba(255,255,255,.08)",
            borderWidth: 1,
            padding: [12, 14],
            textStyle: {
                color: theme.tooltipText,
                fontFamily: "Inter, sans-serif",
                fontSize: 12,
                fontWeight: 600,
            },
            extraCssText: isLight
                ? "box-shadow:0 18px 50px rgba(15,23,42,.14);border-radius:14px;backdrop-filter:blur(10px);"
                : "box-shadow:0 18px 50px rgba(2,6,23,.35);border-radius:14px;backdrop-filter:blur(10px);",
            formatter: (params) => {
                const items = Array.isArray(params) ? params : [params];
                if (!items.length) return "";
                const header = `<div style=\"font-weight:800;font-size:13px;margin-bottom:8px;color:${theme.title};\">${items[0].axisValueLabel}</div>`;
                const body = items.map(item => {
                    const value = Number(item.value ?? 0);
                    const label = config.valueFormatter ? config.valueFormatter(value, item.seriesIndex, item.dataIndex) : `${value.toFixed(1)}${ySuffix}`;
                    return `<div style=\"display:flex;align-items:center;justify-content:space-between;gap:16px;margin:4px 0;\"><span style=\"display:flex;align-items:center;gap:8px;\"><span style=\"width:8px;height:8px;border-radius:50%;background:${item.color};box-shadow:0 0 12px ${item.color};\"></span>${item.seriesName}</span><strong style=\"font-weight:800;color:${theme.title};\">${label}</strong></div>`;
                }).join("");
                return `${header}${body}`;
            }
        },
        grid: {
            left: 22,
            right: 20,
            top: title ? 92 : 24,
            bottom: series.length > 1 ? 58 : 34,
            containLabel: true
        },
        xAxis: {
            type: "category",
            data: labels,
            boundaryGap: true,
            axisLine: { lineStyle: { color: theme.axis, width: 1.1 } },
            axisTick: { show: false },
            axisLabel: {
                color: theme.axis,
                fontFamily: "Inter, sans-serif",
                fontSize: 13,
                fontWeight: 700,
                interval: 0,
                rotate: config.xAxisRotate || 0,
                margin: 15,
            },
            splitLine: { show: false }
        },
        yAxis: {
            type: "value",
            min: config.yMin ?? 0,
            max: config.yMax ?? undefined,
            splitNumber: 4,
            axisLine: { show: true, lineStyle: { color: theme.axis, width: 1.1 } },
            axisTick: { show: true, alignWithLabel: true, lineStyle: { color: theme.axisSoft } },
            axisLabel: {
                color: theme.axis,
                fontFamily: "Inter, sans-serif",
                fontSize: 13,
                fontWeight: 700,
                formatter: (value) => ySuffix ? `${value}${ySuffix}` : `${value}`,
            },
            splitLine: {
                lineStyle: {
                    color: theme.grid,
                    width: 1,
                    type: "dashed"
                }
            }
        },
        series: series.map((s, idx) => {
            const values = s.values || [];
            const c1 = Array.isArray(s.color) ? s.color[0] : (s.color || palette[idx % palette.length]);
            const c2 = Array.isArray(s.color) ? (s.color[1] || paletteAlt[idx % paletteAlt.length]) : (s.altColor || paletteAlt[idx % paletteAlt.length]);
            const isGrouped = series.length > 1;
            return {
                name: s.name || `Serie ${idx + 1}`,
                type: "bar",
                data: values,
                barWidth: s.barWidth || (isGrouped ? 30 : 42),
                barGap: s.barGap || (isGrouped ? "12%" : "28%"),
                barCategoryGap: s.barCategoryGap || (isGrouped ? "22%" : "28%"),
                barMinHeight: 4,
                showBackground: true,
                backgroundStyle: {
                    color: "rgba(255,255,255,.05)",
                    borderRadius: [14, 14, 6, 6],
                },
                label: {
                    show: true,
                    position: s.labelPosition || "top",
                    color: theme.labelText,
                    backgroundColor: theme.labelBg,
                    borderColor: theme.labelBorder,
                    borderWidth: 1,
                    borderRadius: 6,
                    padding: [4, 7],
                    fontFamily: "Inter, sans-serif",
                    fontWeight: 800,
                    fontSize: 12,
                    lineHeight: 16,
                    shadowBlur: 10,
                    shadowColor: "rgba(15,23,42,.18)",
                    formatter: (p) => {
                        const raw = Number(p.value ?? 0);
                        if (s.labelFormatter) return s.labelFormatter(raw, p.dataIndex);
                        return ySuffix ? `${raw.toFixed(1)}${ySuffix}` : `${raw.toFixed(1)}`;
                    }
                },
                emphasis: {
                    focus: "series",
                    itemStyle: {
                        shadowBlur: 24,
                        shadowColor: "rgba(15,23,42,.42)",
                    }
                },
                itemStyle: {
                    borderRadius: [14, 14, 6, 6],
                    borderColor: "rgba(255,255,255,.18)",
                    borderWidth: 1,
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: c1 },
                        { offset: 1, color: c2 },
                    ]),
                    shadowBlur: 18,
                    shadowColor: s.shadowColor || "rgba(2,6,23,.30)",
                    shadowOffsetY: 8,
                },
                animationDuration: 900 + idx * 120,
                animationEasing: "cubicOut",
            };
        })
    };

    chart.setOption(option, true);
    DASHBOARD_ECHARTS.set(domId, chart);
    return true;
}

function buildPremiumBarComparison({ labels, series, layout, extra = {} }) {
    const count = series.length;
    const barWidth = count === 1 ? 0.42 : Math.max(0.24, Math.min(0.34, 0.28 / count + 0.08));
    const traces = [];

    series.forEach((s, idx) => {
        const values = s.values;
        const colorAt = (i) => Array.isArray(s.color) ? s.color[i % s.color.length] : s.color;
        const fillColor = Array.isArray(s.color)
            ? values.map((_, i) => colorAt(i))
            : values.map(() => colorAt(0));
        const textPosition = s.textposition || "outside";
        const defaultTextFont = textPosition === "outside"
            ? { color: "#FFFFFF", size: 12, family: "Inter, sans-serif" }
            : { color: PLOTLY_READABLE_TEXT, size: 12, family: "Inter, sans-serif" };

        traces.push({
            x: labels,
            y: values,
            type: "bar",
            width: barWidth,
            name: s.name,
            marker: {
                color: fillColor,
                line: { color: s.borderColor || "#CBD5E1", width: 1.5 },
            },
            opacity: s.opacity ?? 1,
            text: s.text || values.map(v => `${v.toFixed(1)}%`),
            textfont: s.textfont || defaultTextFont,
            textposition: textPosition,
            cliponaxis: false,
            hovertemplate: s.hovertemplate || "%{x}<br>%{fullData.name}: %{y:.1f}%<extra></extra>",
            legendgroup: s.name,
            offsetgroup: `${idx}`,
            error_y: s.errorY,
            showlegend: extra.showlegend ?? (series.length > 1),
        });
    });

    const plotLayout = {
        ...layout,
        barmode: "group",
        bargap: extra.bargap ?? 0.18,
        bargroupgap: extra.bargroupgap ?? 0.1,
        hovermode: "x unified",
        showlegend: extra.showlegend ?? (series.length > 1),
        hoverlabel: ensurePlotlyHoverContrast({
            ...(layout.hoverlabel || {}),
            ...(extra.hoverlabel || {}),
        }),
        xaxis: ensurePlotlyAxisContrast({
            ...(layout.xaxis || {}),
            tickmode: "array",
            tickvals: labels,
            ticktext: labels,
            ...extra.xaxis,
        }),
        yaxis: ensurePlotlyAxisContrast({
            ...(layout.yaxis || {}),
            ...extra.yaxis,
        }, (layout?.yaxis?.title?.text ?? "")),
        legend: ensurePlotlyLegendContrast({
            ...(layout.legend || {}),
            ...extra.legend,
        }),
    };

    return { data: traces, layout: plotLayout };
}

const PLOTLY_READABLE_TEXT = "#E2E8F0";
const PLOTLY_AXIS_GRID = "rgba(255,255,255,0.1)";
const PLOTLY_AXIS_ZEROLINE = "rgba(255,255,255,0.2)";
const PLOTLY_HOVER_BG = "#0F172A";

function ensurePlotlyAxisContrast(axis = {}, fallbackTitle = "") {
    const safeAxis = axis && typeof axis === "object" ? axis : {};
    const safeTitle = safeAxis.title && typeof safeAxis.title === "object"
        ? safeAxis.title
        : (safeAxis.title ? { text: safeAxis.title } : {});
    const safeTitleFont = safeTitle.font && typeof safeTitle.font === "object" ? safeTitle.font : {};
    const safeLegacyTitleFont = safeAxis.titlefont && typeof safeAxis.titlefont === "object" ? safeAxis.titlefont : {};

    return {
        ...safeAxis,
        gridcolor: PLOTLY_AXIS_GRID,
        zerolinecolor: PLOTLY_AXIS_ZEROLINE,
        tickfont: {
            ...(safeAxis.tickfont || {}),
            color: PLOTLY_READABLE_TEXT,
        },
        titlefont: {
            ...safeLegacyTitleFont,
            color: PLOTLY_READABLE_TEXT,
        },
        title: {
            ...safeTitle,
            ...(safeTitle.text === undefined && fallbackTitle ? { text: fallbackTitle } : {}),
            font: {
                ...safeLegacyTitleFont,
                ...safeTitleFont,
                color: PLOTLY_READABLE_TEXT,
            },
        },
    };
}

function ensurePlotlyLegendContrast(legend = {}) {
    const safeLegend = legend && typeof legend === "object" ? legend : {};
    return {
        ...safeLegend,
        font: {
            ...(safeLegend.font || {}),
            color: PLOTLY_READABLE_TEXT,
        },
        bgcolor: "rgba(0,0,0,0.3)",
    };
}

function ensurePlotlyHoverContrast(hoverlabel = {}) {
    const safeHover = hoverlabel && typeof hoverlabel === "object" ? hoverlabel : {};
    return {
        ...safeHover,
        bgcolor: PLOTLY_HOVER_BG,
        font: {
            ...(safeHover.font || {}),
            color: "#FFFFFF",
        },
    };
}

function baseLayout(yTitle = "", extra = {}) {
    const { xaxis = {}, yaxis = {}, legend = {}, hoverlabel = {}, title = {}, ...rest } = extra;
    return {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(15,23,42,0.28)",
        margin: { t: 56, r: 32, b: 64, l: 64, pad: 14 },
        font: { color: PLOTLY_READABLE_TEXT, family: "Inter, sans-serif", size: 13 },
        hovermode: "x unified",
        hoverlabel: ensurePlotlyHoverContrast({
            bordercolor: "rgba(255,255,255,0.18)",
            font: { family: "Inter, sans-serif", size: 13 },
            align: "left",
            ...hoverlabel
        }),
        title: {
            font: { family: "Inter, sans-serif", size: 16, color: PLOTLY_READABLE_TEXT },
            x: 0,
            xanchor: "left",
            ...title
        },
        xaxis: ensurePlotlyAxisContrast({
            linecolor: "rgba(148,163,184,0.35)",
            zeroline: false,
            showline: true,
            tickcolor: "rgba(226,232,240,0.65)",
            tickfont: { size: 12 },
            title: { font: { size: 12 } },
            ticklen: 4,
            tickwidth: 1,
            ...xaxis
        }),
        yaxis: ensurePlotlyAxisContrast({
            title: { text: yTitle, font: { size: 12 } },
            linecolor: "rgba(148,163,184,0.35)",
            zeroline: false,
            showline: true,
            tickcolor: "rgba(226,232,240,0.65)",
            tickfont: { size: 12 },
            ticklen: 4,
            tickwidth: 1,
            ...yaxis
        }, yTitle),
        legend: ensurePlotlyLegendContrast({
            orientation: "h",
            x: 0.5,
            y: 1.14,
            xanchor: "center",
            yanchor: "bottom",
            bordercolor: "rgba(255,255,255,0.14)",
            borderwidth: 1,
            font: { size: 11 },
            itemclick: "toggleothers",
            itemdoubleclick: "toggle",
            ...legend
        }),
        ...rest,
    };
}

function darkBaseLayout(yTitle = "", extra = {}) {
    return baseLayout(yTitle, extra);
}

function pitchLayout(title, subtitle, extra = {}) {
    const {
        xaxis = {},
        yaxis = {},
        legend = {},
        hoverlabel = {},
        showZones = false,
        showAnnotations = true,
        pitchImageOpacity = 0.62,
        ...rest
    } = extra;
    const hasTitle = Boolean(title || subtitle);
    const subtitleSpan = subtitle
        ? `<br><span style="font-size:11px;color:${PITCH_THEME.axisTextSoft};">${subtitle}</span>`
        : "";
    return {
        template: {},
        ...(hasTitle ? {
            title: {
                text: `${title}${subtitleSpan}`,
                font: { family: "Inter, sans-serif", size: 16, color: "#F8FAFC" },
                x: .02,
                xanchor: "left",
            },
        } : {}),
        paper_bgcolor: PITCH_THEME.surfaceDeep,
        plot_bgcolor: PITCH_THEME.surface,
        margin: { t: hasTitle ? 58 : 8, r: 20, b: hasTitle ? 28 : 8, l: 20, pad: 0 },
        font: { color: "#E2E8F0", family: "Inter, sans-serif", size: 12 },
        showlegend: true, autosize: true, dragmode: false,
        legend: {
            orientation: "h",
            x: 0.5,
            y: 1.02,
            xanchor: "center",
            yanchor: "bottom",
            bgcolor: PITCH_THEME.legendPanel,
            bordercolor: PITCH_THEME.legendBorder,
            borderwidth: 1,
            font: { size: 11, color: "#F8FAFC" },
            ...legend
        },
        hoverlabel: {
            bgcolor: PITCH_THEME.hoverPanel,
            bordercolor: PITCH_THEME.hoverBorder,
            font: { color: "#F8FAFC", family: "Inter, sans-serif", size: 12 },
            align: "left",
            ...hoverlabel
        },
        xaxis: {
            range: [0, 100],
            showgrid: false,
            zeroline: false,
            showline: false,
            ticks: "",
            showticklabels: false,
            tickmode: "array",
            tickvals: [0, 25, 50, 75, 100],
            ticktext: ["0", "25", "50", "75", "100"],
            tickfont: { color: PITCH_THEME.axisTextSoft, size: 11 },
            title: { text: "", font: { color: PITCH_THEME.axisText, size: 12 } },
            fixedrange: true,
            constrain: "domain",
            ...xaxis
        },
        yaxis: {
            range: [0, 100],
            showgrid: false,
            zeroline: false,
            showline: false,
            ticks: "",
            showticklabels: false,
            tickmode: "array",
            tickvals: [0, 25, 50, 75, 100],
            ticktext: ["0", "25", "50", "75", "100"],
            tickfont: { color: PITCH_THEME.axisTextSoft, size: 11 },
            title: { text: "", font: { color: PITCH_THEME.axisText, size: 12 } },
            fixedrange: true,
            scaleanchor: "x",
            scaleratio: .68,
            ...yaxis
        },
        images: [
            {
                source: PITCH_REAL_SRC,
                xref: "x",
                yref: "y",
                x: 0,
                y: 100,
                sizex: 100,
                sizey: 100,
                sizing: "stretch",
                opacity: pitchImageOpacity,
                layer: "below",
            },
        ],
        shapes: buildPitchShapes({ showZones }),
        annotations: showAnnotations ? buildPitchAnnotations() : [],
        transition: { duration: 360, easing: "cubic-in-out" },
        ...rest,
    };
}

// ── PITCH SHAPES ──────────────────────────────────────────
function buildPitchAnnotations() {
    return [
        { x:100,y:50,xref:"x",yref:"y",text:"Arco rival",showarrow:true,arrowhead:2,arrowsize:1,arrowwidth:1.2,arrowcolor:"#f8fafc",ax:-90,ay:-28,font:{color:"#f8fafc",size:10},bgcolor:"rgba(6,26,16,0.74)",borderwidth:1 },
        { x:0,  y:50,xref:"x",yref:"y",text:"Arco propio",showarrow:true,arrowhead:2,arrowwidth:1,arrowcolor:"#e2f8ee",ax:80,ay:24,font:{color:"#e2f8ee",size:10},bgcolor:"rgba(6,26,16,0.70)",borderwidth:1 },
        { x:72, y:93,xref:"x",yref:"y",text:"Dirección →",showarrow:true,arrowhead:3,arrowcolor:"#fef3c7",ax:-50,ay:0,font:{color:"#fef3c7",size:10},bgcolor:"rgba(6,26,16,0.68)",borderwidth:1 },
    ];
}

function buildPitchShapes(options = {}) {
    const { showZones = false } = options;
    const ln = { color: PITCH_THEME.line, width: 2 };
    const shapes = [
        { type: "rect", x0: 0, y0: 0, x1: 100, y1: 100, fillcolor: PITCH_THEME.surfaceTint, line: { width: 0 }, layer: "below" },
        rect(0,0,100,100,ln), seg(50,0,50,100,ln),
        circ(40.85,40.85,59.15,59.15,ln), circ(49.35,49.35,50.65,50.65,ln),
        rect(0,21.1,16.5,78.9,ln), rect(0,36.8,5.5,63.2,ln),
        rect(83.5,21.1,100,78.9,ln), rect(94.5,36.8,100,63.2,ln),
        circ(10.5,49.35,11.5,50.65,ln), circ(88.5,49.35,89.5,50.65,ln),
        rect(-2,44.5,0,55.5,ln), rect(100,44.5,102,55.5,ln),
        pth(arcPath(11,50,9.15,-52,52),ln), pth(arcPath(89,50,9.15,128,232),ln),
    ];
    if (showZones) {
        shapes.push({
            type: "rect",
            x0: 83.5,
            y0: 21.1,
            x1: 100,
            y1: 78.9,
            line: { color: "rgba(56,189,248,.45)", width: 1.1, dash: "dot" },
            fillcolor: "rgba(56,189,248,.05)",
            layer: "below",
        });
        shapes.push({
            type: "rect",
            x0: 94.5,
            y0: 36.8,
            x1: 100,
            y1: 63.2,
            line: { color: "rgba(52,211,153,.72)", width: 1.2, dash: "dot" },
            fillcolor: "rgba(52,211,153,.10)",
            layer: "below",
        });
    }
    return shapes;
}
function rect(x0,y0,x1,y1,line){return{type:"rect",x0,y0,x1,y1,line,fillcolor:"rgba(0,0,0,0)"}}
function circ(x0,y0,x1,y1,line){return{type:"circle",x0,y0,x1,y1,line,fillcolor:"rgba(0,0,0,0)"}}
function seg(x0,y0,x1,y1,line){return{type:"line",x0,y0,x1,y1,line}}
function pth(path,line){return{type:"path",path,line}}
function arcPath(cx,cy,r,s,e){
    return Array.from({length:49},(_,i)=>{
        const a=(s+(e-s)*i/48)*Math.PI/180;
        return `${i===0 ? "M" : "L"} ${cx+r*Math.cos(a)} ${cy+r*Math.sin(a)}`;
    }).join(" ");
}
