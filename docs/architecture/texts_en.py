"""English texts of the architecture decks (used by build_decks.py).

EN:        German slide text -> English slide text
SAME:      language-neutral texts (file, tool and product names) that stay as they are
GROUPS_EN: English names of the expenditure groups (for slide texts generated from the data)
"""

GROUPS_EN: dict[str, str] = {
    "food": "Food", "housing_energy": "Housing / energy", "mobility": "Transport", "health": "Health",
    "communication": "Communication",
}

SAME: set[str] = {
    "Azure OpenAI", "gpt-4o (Completion)", "text-embedding-3-large", "index.py", "investigation.py",
    "REALBASKET-ORCHESTRATOR · agents/orchestrator.py", "MCPClient · agents/mcp_clients.py",
    "data: get_basket · get_prices · get_cpi · calculate_index · data_checks",
    "analysis: investigate_deviation · get_regional_rents", "knowledge: search_methodology · list_documents",
    "reports/pdf_report.py (reportlab)", "ingest · BM25 + Embedding", "(RRF) · index.json",
    "core/settings.py · core/llm.py", "Chat", "PDF", "MCP (stdio / HTTP)", "Orchestrator", "Sub-Agent",
    "Disclaimer", "reports/real-data", "ingest.extract_pages", "(pypdf)", "load_basket()", "Index", "index.json",
    "+ Embeddings", "BM25 + Embedding", "(Reciprocal Rank Fusion)", "UI", "Streamlit, Plotly",
    "Strands Agents SDK (OpenAIModel / AzureOpenAIModel)", "MCP Python SDK (MCPServer), Strands MCPClient", "LLM",
    "Azure OpenAI: gpt-4o, text-embedding-3-large", "pypdf, pandas, pydantic", "reportlab",
    "Microsoft Teams / Copilot", "A2A-Client", "Claude Desktop / VS Code", "gpt-4o · Embeddings", "Price-Collector",
    "Report-Agent", "get_prices · get_cpi", "calculate_index · data_checks", "investigate_deviation",
    "get_regional_rents", "search_methodology", "render_pdf", "reports/real-data/*.pdf", "index.json / Vector Store",
    "Clients", "Tools", "Resources / Prompts", "Status", "data (data_tools.py)",
    "get_basket() · get_prices(category, months) · get_cpi(months) · calculate_index(weights, months) · data_checks()",
    "basket://weights · basket://checks", "analysis (analysis_tools.py)",
    "investigate_deviation(level, category, region_type, months) · get_regional_rents(region_type)",
    "knowledge (knowledge_tools.py)", "search_methodology(query, year) · list_documents()", "render_pdf(kind, year)",
    "report://{name}.pdf", "get_vpi_table(code, from, to)", "Agent", "Skills (Agent Card)", "data",
    "data, analysis", "knowledge", "report, data", "Client", "investigate_deviation (MCP)", "MCP", "MCP / A2A",
    "A2A", "A2A / MCP", "agents/tools.py: fetch_prices, fetch_official_cpi, calculate_essential_vs_cpi",
    "agents/tools.py: investigate_deviation, fetch_regional_rents", "Entra ID, Key Vault, Container Apps",
    "OpenTelemetry, Monitoring", "Prompts  (agents/prompts.py)", "MCP – Model Context Protocol",
    "Resource doc://…/seite", "Resource report://…", "search_methodology (MCP),",
    "agents/tools.py: search_methodology + knowledge/", "agents/guardrail.py",
}

EN: dict[str, str] = {
    # --- shared -------------------------------------------------------------------------------------
    "RealBasket · Architektur · Stand November 2026": "RealBasket · Architecture · As of November 2026",

    # --- deck 1: current architecture -------------------------------------------------------------
    "RealBasket – Ist-Architektur": "RealBasket – Current Architecture",
    "Agentischer Index der Grundlebenshaltungskosten im Vergleich zum amtlichen VPI\n"
    "Streamlit · Strands Agents · MCP · Azure OpenAI · deterministische Rechenkerne":
        "Agentic index of essential living costs compared with the official CPI (VPI)\n"
        "Streamlit · Strands Agents · MCP · Azure OpenAI · deterministic calculation core",
    "Was RealBasket heute leistet": "What RealBasket does today",
    "Index der Grundlebenshaltungskosten (ECLI-Warenkorb, 5 Ausgabengruppen) vs. amtlicher VPI":
        "Essential living cost index (ECLI basket, 5 expenditure groups) vs. official CPI (VPI)",
    "Echte Daten: deterministisch aus den PDF-Tabellen in reports/real-data geparst":
        "Real data: parsed deterministically from the PDF tables in reports/real-data",
    "Keine Demo-Daten, kein Fallback: ohne PDFs Fehlermeldung statt Zahlen":
        "No demo data, no fallback: without the PDFs an error instead of numbers",
    "Einflussfaktoren: Beitrag jeder Ausgabengruppe zur Abweichung in Prozentpunkten":
        "Drivers: contribution of each expenditure group to the deviation in percentage points",
    "Mieten der 15 größten Städte (Jan vs. Okt 2026); je Bundesland nur Abdeckung":
        "Rents of the 15 largest cities (Jan vs. Oct 2026); per federal state coverage only",
    "Methodenhinweise per RAG (BM25 + Embeddings), Zitate mit Datei und Seite":
        "Method notes via RAG (BM25 + embeddings), citations with file and page",
    "Chat mit RealBasket: Strands-Agent auf Azure OpenAI (gpt-4o), Antworten auf Deutsch":
        "Chat with RealBasket: Strands agent on Azure OpenAI (gpt-4o), answers in German",
    "Alle Werkzeuge im MCP-Server realbasket (ein Prozess, Bereiche data · analysis · knowledge)":
        "All tools in the MCP server realbasket (one process, areas data · analysis · knowledge)",
    "Grundsatz: Zahlen nur aus deterministischen Tools; ein Guardrail prüft jede Zahl der Antwort":
        "Principle: numbers only from deterministic tools; a guardrail checks every number of the answer",
    "Größter Einflussfaktor:": "Biggest driver:",
    "Quelle: ECLI-Modellrechnung 2024–2026, Basis Nov 2024 = 100; Abweichung aus ungerundeten Raten, Werte beim "
    "Erstellen der Folien berechnet":
        "Source: ECLI model calculation 2024–2026, base Nov 2024 = 100; deviation from unrounded rates, values "
        "computed when the slides are built",
    "Komponenten": "Components",
    "Streamlit hostet Dashboard und Agenten; die Werkzeuge laufen im MCP-Server realbasket (Subprozess, stdio); "
    "nur das LLM ist extern":
        "Streamlit hosts dashboard and agent; the tools run in the MCP server realbasket (subprocess, stdio); "
        "only the LLM is external",
    "Streamlit-UI  (ui/app.py)": "Streamlit UI  (ui/app.py)",
    "Index vs. VPI · Einflussfaktoren · Miete Städte · Methodenhinweise · Chat mit RealBasket · "
    "Sidebar: Gewichte & PDF-Berichte":
        "Index vs. CPI · Drivers · City rents · Method notes · Chat with RealBasket · "
        "Sidebar: weights & PDF reports",
    "Orchestrator-Agent (Strands)": "Orchestrator agent (Strands)",
    "Zahlen-Guardrail": "Number guardrail",
    "Zahlen der Antwort vs. Tool-Ergebnisse": "numbers of the answer vs. tool results",
    "Antwort prüfen": "Check answer",
    "MCP-Server realbasket  (mcp_servers/)": "MCP server realbasket  (mcp_servers/)",
    "Deutsch · Disclaimer · nur echte Daten, keine Schätzungen":
        "German · disclaimer · real data only, no estimates",
    "PDF-Berichte": "PDF reports",
    "Rechenkern  core/": "Calculation core  core/",
    "Daten  data/": "Data  data/",
    "real_data.py (Parser + Prüfungen)": "real_data.py (parser + checks)",
    "basket.py (nur echte Daten)": "basket.py (real data only)",
    "Wissensbasis  knowledge/": "Knowledge base  knowledge/",
    "Konfiguration": "Configuration",
    ".env im Projektordner": ".env in the project folder",
    "reports/real-data/*.pdf  –  ECLI-Modellrechnung 2024 · 2025 · 2026":
        "reports/real-data/*.pdf  –  ECLI model calculation 2024 · 2025 · 2026",
    "Dashboard (ohne LLM)": "Dashboard (no LLM)",
    "Ablauf einer Chat-Frage": "Flow of a chat question",
    "Beispiel: „Steigen die Grundlebenshaltungskosten stärker als der VPI?“":
        "Example: “Are essential living costs rising faster than the CPI?”",
    "Frage": "Question",
    "Nutzer fragt im Tab": "User asks in the tab",
    "„Chat mit RealBasket“": "“Chat mit RealBasket”",
    "Streamlit ruft den Agenten": "Streamlit calls the agent",
    "in-process auf; MCP-Server": "in-process; the MCP server",
    "startet als Subprozess": "starts as a subprocess",
    "Planung": "Planning",
    "gpt-4o wählt die Tools": "gpt-4o picks the tools",
    "(Function Calling über": "(function calling via",
    "die MCP-Tool-Schemas)": "the MCP tool schemas)",
    "Rechnen": "Calculate",
    "MCP-Tools rechnen deter-": "MCP tools calculate deter-",
    "ministisch (core/, data/)": "ministically (core/, data/)",
    "bzw. suchen Hinweise": "or search method notes",
    "Prüfung": "Check",
    "Guardrail gleicht jede": "Guardrail matches every",
    "Zahl mit den Tool-": "number against the tool",
    "Ergebnissen ab": "results",
    "Antwort": "Answer",
    "Deutsch, Zahlen aus Tools,": "German, numbers from tools,",
    "Quellen „Datei S. N“,": "sources “file p. N”,",
    "Dashboard-Tabs (Index vs. VPI, Einflussfaktoren) rufen core/ und data/ direkt auf – ohne LLM, "
    "deshalb identische Zahlen in Dashboard und Chat":
        "Dashboard tabs (index vs. CPI, drivers) call core/ and data/ directly – without LLM, "
        "so dashboard and chat show identical numbers",
    "Nur echte Daten: Mieten je Bundesland und Nettogehälter sind nicht in den Quellen – der Agent sagt das, "
    "statt zu schätzen":
        "Real data only: rents per federal state and net salaries are not in the sources – the agent says so "
        "instead of estimating",
    "Unveränderte Gewichts-Regler → exakte Warenkorbgewichte aus den PDFs":
        "Untouched weight sliders → exact basket weights from the PDFs",
    "Datenpipeline": "Data pipeline",
    "Zwei getrennte Pfade: Zahlen (deterministisch) und Methodenhinweise (RAG)":
        "Two separate paths: numbers (deterministic) and method notes (RAG)",
    "Referenz-PDFs": "Reference PDFs",
    "Zahlenpfad": "Numbers path",
    "Hinweispfad (RAG)": "Method-notes path (RAG)",
    "Text extrahieren": "Extract text",
    "Tabellen parsen": "Parse tables",
    "Basiswarenkorb · Monats-": "Base basket · monthly",
    "kosten · ECLI/VPI · Mieten": "costs · ECLI/CPI · rents",
    "Summen · Lücken · ECLI": "Sums · gaps · ECLI",
    "VPI · Mieten · Länder": "CPI · rents · states",
    "Warenkorb": "Basket",
    "nur echte Daten": "real data only",
    "Rechenkern": "Calculation core",
    "Index · Abweichung": "Index · deviation",
    "Einflussfaktoren": "Drivers",
    "Passagen": "Passages",
    "Hinweise + Text-": "Notes + text",
    "Tabellenzellen": "table cells",
    "Bereinigen": "Clean up",
    "Zahlen verworfen,": "Numbers dropped,",
    "Duplikate zusammengeführt": "duplicates merged",
    "Suche": "Search",
    "Zitat": "Citation",
    "Datei + Seite": "File + page",
    "„auch in …“": "“also in …”",
    "Kein Fallback: PDFs fehlen oder nicht lesbar → RealDataError; Dashboard zeigt den Fehler, Tools liefern "
    "{\"error\": …} – es gibt keine Demo-Daten":
        "No fallback: PDFs missing or unreadable → RealDataError; the dashboard shows the error, tools return "
        "{\"error\": …} – there is no demo data",
    "Ohne LLM-Zugang: reine BM25-Suche (offline) mit deutscher Stammformbildung und Glossar Englisch → Deutsch":
        "Without LLM access: pure BM25 search (offline) with German stemming and an English → German glossary",
    "Technologie-Stack": "Technology stack",
    "Schicht": "Layer",
    "Technologie": "Technology",
    "Rolle": "Role",
    "Dashboard, Chat, PDF-Download": "Dashboard, chat, PDF download",
    "Agenten": "Agents",
    "Orchestrator-Agent + Zahlen-Guardrail": "Orchestrator agent + number guardrail",
    "Werkzeuge": "Tools",
    "Ein MCP-Server realbasket, stdio / HTTP": "One MCP server realbasket, stdio / HTTP",
    "Planung, Formulierung, Embeddings": "Planning, wording, embeddings",
    "Daten": "Data",
    "PDF-Parsing, Prüfungen, Modelle": "PDF parsing, checks, models",
    "Wissen": "Knowledge",
    "eigener BM25 + Embedding-Retriever, index.json": "own BM25 + embedding retriever, index.json",
    "Methodenhinweise mit Zitaten": "Method notes with citations",
    "Berichte": "Reports",
    "pydantic-settings, .env (Projektordner)": "pydantic-settings, .env (project folder)",
    "Azure-Einstellungen, KNOWLEDGE_DIR": "Azure settings, KNOWLEDGE_DIR",
    "Qualität / Build": "Quality / build",
    "pytest (inkl. MCP-Contract-Tests), ruff, Poetry, GitHub Actions":
        "pytest (incl. MCP contract tests), ruff, Poetry, GitHub Actions",
    "Tests, Lint, CI, Abhängigkeiten": "Tests, lint, CI, dependencies",
    "Stärken und Grenzen": "Strengths and limitations",
    "Stärken": "Strengths",
    "Einfach: ein Deployment, ein MCP-Server-Prozess – ideal für die Demo":
        "Simple: one deployment, one MCP server process – ideal for the demo",
    "Werkzeuge per MCP wiederverwendbar (Claude Desktop, VS Code)":
        "Tools reusable via MCP (Claude Desktop, VS Code)",
    "Deterministische, nachgeprüfte Zahlen; LLM nur für Sprache":
        "Deterministic, re-checked numbers; LLM for language only",
    "Dashboard und Chat nutzen denselben Rechenkern": "Dashboard and chat share the same calculation core",
    "Nur echte, nachgerechnete Daten – keine synthetischen Werte":
        "Real, re-checked data only – no synthetic values",
    "Offline nutzbar ohne LLM (Dashboard, BM25-Suche, PDFs)":
        "Works offline without LLM (dashboard, BM25 search, PDFs)",
    "Automatische Tests inkl. MCP-Contract-Tests, Lint und CI":
        "Automated tests incl. MCP contract tests, lint and CI",
    "Grenzen": "Limitations",
    "Ein MCP-Server für alle Bereiche: gemeinsame Rechte, gemeinsame Skalierung":
        "One MCP server for all areas: shared permissions, shared scaling",
    "Agent läuft im Streamlit-Prozess: skaliert nur mit der UI; Dashboard nutzt core/ direkt":
        "Agent runs in the Streamlit process: scales only with the UI; dashboard uses core/ directly",
    "Guardrail prüft Zahlen, nicht Aussagen (falsche Zuordnung bleibt möglich)":
        "Guardrail checks numbers, not statements (a wrong attribution remains possible)",
    "Datenstand fix (PDFs bis 10/2026), keine Live-Anbindung (Destatis)":
        "Fixed data (PDFs up to 10/2026), no live connection (Destatis)",
    "Keine Mieten je Bundesland, keine Nettogehälter in den Quellen":
        "No rents per federal state, no net salaries in the sources",
    "Kein Auth-/Mandantenkonzept, Schlüssel in .env": "No auth / multi-tenancy concept, keys in .env",

    # --- deck 2: MCP / A2A proposal ----------------------------------------------------------------
    "RealBasket – Zielarchitektur mit MCP und A2A": "RealBasket – Target Architecture with MCP and A2A",
    "Vorschlag: Werkzeuge und Daten per MCP, Agenten als A2A-Dienste\n"
    "Phase 1 umgesetzt: ein MCP-Server realbasket mit den Bereichen data · analysis · knowledge":
        "Proposal: tools and data via MCP, agents as A2A services\n"
        "Phase 1 implemented: one MCP server realbasket with the areas data · analysis · knowledge",
    "Warum MCP und A2A?": "Why MCP and A2A?",
    "Wiederverwendung: RealBasket-Daten und -Rechnungen in Copilot, Claude Desktop oder VS Code nutzbar":
        "Reuse: RealBasket data and calculations usable in Copilot, Claude Desktop or VS Code",
    "Interoperabilität: andere Agenten (z. B. von Partnern) fragen RealBasket per A2A":
        "Interoperability: other agents (e.g. from partners) query RealBasket via A2A",
    "Entkopplung: Agenten und Werkzeuge einzeln versionieren, deployen und skalieren":
        "Decoupling: version, deploy and scale agents and tools individually",
    "Klare Verträge: Tool-Schemas (MCP) und Agent Cards (A2A) statt Python-Importen":
        "Clear contracts: tool schemas (MCP) and agent cards (A2A) instead of Python imports",
    "Determinismus bleibt: Zahlen kommen weiterhin nur aus den Rechen-Tools":
        "Determinism stays: numbers still come only from the calculation tools",
    "Agent ↔ Werkzeuge & Daten": "Agent ↔ tools & data",
    "Tools (Funktionen) · Resources (Dokumente, Daten)": "Tools (functions) · resources (documents, data)",
    "Prompts (Vorlagen)": "Prompts (templates)",
    "Transport: stdio (lokal) · Streamable HTTP": "Transport: stdio (local) · Streamable HTTP",
    "A2A – Agent2Agent-Protokoll": "A2A – Agent2Agent protocol",
    "Agent ↔ Agent": "Agent ↔ agent",
    "Agent Card (Fähigkeiten, Endpunkt, Auth)": "Agent card (skills, endpoint, auth)",
    "Tasks · Nachrichten · Artefakte": "Tasks · messages · artifacts",
    "JSON-RPC über HTTPS · SSE-Streaming": "JSON-RPC over HTTPS · SSE streaming",
    "Zielarchitektur": "Target architecture",
    "Clients → Orchestrator (A2A) → Fach-Agenten (A2A) → MCP-Server realbasket → Datenquellen":
        "Clients → orchestrator (A2A) → specialist agents (A2A) → MCP server realbasket → data sources",
    "Streamlit-UI": "Streamlit UI",
    "Dashboard + Chat · A2A-Client": "Dashboard + chat · A2A client",
    "Partner-Agenten": "Partner agents",
    "z. B. Verbraucherberatung · A2A": "e.g. consumer advice · A2A",
    "MCP-Host": "MCP host",
    "A2A-Server + A2A-Client · Antwort auf Deutsch mit Disclaimer":
        "A2A server + A2A client · answer in German with disclaimer",
    "A2A  ·  JSON-RPC über HTTPS  ·  Agent Cards  ·  Tasks  ·  SSE-Streaming":
        "A2A  ·  JSON-RPC over HTTPS  ·  agent cards  ·  tasks  ·  SSE streaming",
    "Preise je Gruppe": "Prices per group",
    "Abweichungs-Analyst": "Deviation analyst",
    "Einflussfaktoren, Mieten": "Drivers, rents",
    "Methodik-Agent": "Methodology agent",
    "RAG, Zitate": "RAG, citations",
    "MCP-Server realbasket (ein Prozess, ein Modul je Bereich)  ·  stdio / Streamable HTTP  ·  "
    "Tools · Resources · Prompts":
        "MCP server realbasket (one process, one module per area)  ·  stdio / Streamable HTTP  ·  "
        "tools · resources · prompts",
    "Bereich data ✓": "Area data ✓",
    "Bereich analysis ✓": "Area analysis ✓",
    "Bereich knowledge ✓": "Area knowledge ✓",
    "Bereich report (geplant)": "Area report (planned)",
    "destatis-genesis (neu)": "destatis-genesis (new)",
    "eigener Server": "separate server",
    "get_vpi_table · Live-VPI": "get_vpi_table · live CPI",
    "ECLI 2024–2026 · VPI": "ECLI 2024–2026 · CPI",
    "Stadtmieten (in den PDFs)": "City rents (in the PDFs)",
    "15 Städte, immowelt": "15 cities, immowelt",
    "Vektorindex": "Vector index",
    "Externe APIs": "External APIs",
    "Destatis GENESIS · Mietportale": "Destatis GENESIS · rental portals",
    "MCP direkt": "MCP direct",
    "A2A-Agenten": "A2A agents",
    "MCP-Server": "MCP server",
    "Datenquellen": "Data sources",
    "MCP-Server realbasket im Detail": "MCP server realbasket in detail",
    "Ein Server-Prozess, ein Modul je Bereich – dünne Hüllen um core/, data/, knowledge/ "
    "(src/real_basket/mcp_servers/)":
        "One server process, one module per area – thin wrappers around core/, data/, knowledge/ "
        "(src/real_basket/mcp_servers/)",
    "Bereich (Modul)": "Area (module)",
    "umgesetzt": "implemented",
    "doc://{datei}/seite/{n} · Prompt hinweis_zitieren": "doc://{file}/seite/{n} · prompt hinweis_zitieren",
    "report (geplant)": "report (planned)",
    "offen (reports/pdf_report.py)": "open (reports/pdf_report.py)",
    "destatis-genesis (eigener Server)": "destatis-genesis (separate server)",
    "offen (GENESIS-API, Token)": "open (GENESIS API, token)",
    "Start: poetry run real-basket-mcp [--transport streamable-http --port 8001] [--areas data,analysis]. "
    "Nur echte Daten: jedes Tool liefert Datenbasis, Quell-PDFs und Prüfergebnisse mit; fehlen die PDFs, kommt "
    "ein Fehler statt Zahlen.":
        "Start: poetry run real-basket-mcp [--transport streamable-http --port 8001] [--areas data,analysis]. "
        "Real data only: every tool returns data basis, source PDFs and check results; without the PDFs an error "
        "instead of numbers.",
    "Ein MCP-Server statt mehrerer": "One MCP server instead of several",
    "Entscheidung für den Hackathon – Aufteilung bleibt jederzeit möglich":
        "Decision for the hackathon – splitting remains possible at any time",
    "Warum ein Server": "Why one server",
    "MCP erlaubt beliebig viele Tools, Resources und Prompts je Server":
        "MCP allows any number of tools, resources and prompts per server",
    "Ein Prozess: PDFs werden nur einmal geparst, schnellerer Start":
        "One process: PDFs are parsed only once, faster start",
    "Ein Eintrag in Claude Desktop / VS Code, eine URL (MCP_URL)":
        "One entry in Claude Desktop / VS Code, one URL (MCP_URL)",
    "Weniger Betrieb und Konfiguration für die Demo": "Less operations and configuration for the demo",
    "Fach-Agenten erhalten per Filter nur ihre Tools (z. B. nur data)":
        "Specialist agents get only their tools via a filter (e.g. data only)",
    "Wann aufteilen": "When to split",
    "Least Privilege: nur knowledge braucht den LLM-Schlüssel (Embeddings)":
        "Least privilege: only knowledge needs the LLM key (embeddings)",
    "Unabhängige Skalierung, z. B. Berichte (report)": "Independent scaling, e.g. reports (report)",
    "Externe Quellen mit eigenem Token (destatis-genesis)":
        "External sources with their own token (destatis-genesis)",
    "Andere Teams übernehmen einzelne Bereiche": "Other teams take over individual areas",
    "Technisch: --areas bzw. ein Einstiegspunkt je Bereich – Tool-Namen bleiben gleich":
        "Technically: --areas or one entry point per area – tool names stay the same",
    "A2A-Agenten im Detail": "A2A agents in detail",
    "Jeder Agent veröffentlicht eine Agent Card unter /.well-known/agent-card.json":
        "Every agent publishes an agent card at /.well-known/agent-card.json",
    "nutzt MCP-Bereiche": "uses MCP areas",
    "Ergebnis (Artefakt)": "Result (artifact)",
    "Lebenshaltung vs. VPI erklären · Fragen an Fach-Agenten verteilen":
        "Explain living costs vs. CPI · distribute questions to specialist agents",
    "– (delegiert)": "– (delegates)",
    "Antwort auf Deutsch + Disclaimer": "Answer in German + disclaimer",
    "Preise je Ausgabengruppe sammeln und zusammenfassen": "Collect and summarise prices per expenditure group",
    "Preisübersicht je Gruppe": "Price overview per group",
    "Einflussfaktoren · Stadtmieten · Abdeckung je Bundesland": "Drivers · city rents · coverage per federal state",
    "Beiträge in PP, Tabellen": "Contributions in pp, tables",
    "Methodenhinweise und Grenzen mit Zitat erklären": "Explain method notes and caveats with citations",
    "Zitate (Datei, Seite)": "Citations (file, page)",
    "PDF-Berichte erstellen": "Create PDF reports",
    "PDF als Artefakt": "PDF as artifact",
    "Lang laufende Aufgaben (z. B. Berichte) als A2A-Task mit Status-Updates per SSE; Ergebnisse als Artefakte "
    "statt Freitext.":
        "Long-running work (e.g. reports) as an A2A task with status updates via SSE; results as artifacts "
        "instead of free text.",
    "Ablauf einer Frage in der Zielarchitektur": "Flow of a question in the target architecture",
    "Beispiel: „Warum liegt der Grundbedarf über dem VPI und was sagt die Methodik dazu?“":
        "Example: “Why are essentials above the CPI and what does the methodology say?”",
    "Streamlit / Teams sendet": "Streamlit / Teams sends",
    "A2A-Nachricht an den": "an A2A message to the",
    "Orchestrator liest Agent": "Orchestrator reads agent",
    "Cards und verteilt": "cards and distributes",
    "Teilaufgaben": "subtasks",
    "Analyse": "Analysis",
    "Abweichungs-Analyst ruft": "Deviation analyst calls",
    "calculate_index und": "calculate_index and",
    "Methodik": "Methodology",
    "Methodik-Agent ruft": "Methodology agent calls",
    "parallel zur Analyse": "in parallel to the analysis",
    "Zusammenführen": "Combine",
    "Orchestrator kombiniert": "Orchestrator combines",
    "Artefakte, prüft": "artifacts, checks",
    "Quellen + Prüfungen": "sources + checks",
    "Deutsch, Zahlen + Zitate,": "German, numbers + citations,",
    "Disclaimer, gestreamt": "disclaimer, streamed",
    "per SSE": "via SSE",
    "Die Zahlen stammen ausschließlich aus MCP-Tools – kein Agent rechnet selbst":
        "Numbers come exclusively from MCP tools – no agent calculates itself",
    "Unabhängige Teilaufgaben laufen parallel (Analyse und Methodik)":
        "Independent subtasks run in parallel (analysis and methodology)",
    "Durchgängiges Tracing über A2A- und MCP-Grenzen (OpenTelemetry, in Strands integriert)":
        "End-to-end tracing across A2A and MCP boundaries (OpenTelemetry, built into Strands)",
    "Abbildung Ist → Ziel": "Mapping current → target",
    "Stand November 2026: Phase 1 (MCP) umgesetzt, Phase 2 (A2A) offen":
        "As of November 2026: phase 1 (MCP) implemented, phase 2 (A2A) open",
    "Vorher": "Before",
    "Ziel": "Target",
    "Protokoll": "Protocol",
    "MCP-Server realbasket, Bereich data": "MCP server realbasket, area data",
    "Bereich analysis (get_regional_rents)": "Area analysis (get_regional_rents)",
    "Bereich knowledge (Tools, Resource, Prompt)": "Area knowledge (tools, resource, prompt)",
    "ui/app.py: PDF-Download über reports/pdf_report.py": "ui/app.py: PDF download via reports/pdf_report.py",
    "Bereich report + Report-Agent": "Area report + report agent",
    "offen": "open",
    "Collector-Sub-Agent (entfernt 11/2026; get_prices liefert die Zusammenfassung)":
        "Collector sub-agent (removed 11/2026; get_prices returns the summary)",
    "Price-Collector als eigener Dienst, sobald es Live-Quellen gibt":
        "Price collector as a separate service once there are live sources",
    "Orchestrator im Streamlit-Prozess": "Orchestrator in the Streamlit process",
    "Orchestrator-Dienst (A2A-Server)": "Orchestrator service (A2A server)",
    "Streamlit ruft den Agenten direkt auf": "Streamlit calls the agent directly",
    "Streamlit als A2A-Client; Dashboard über MCP": "Streamlit as A2A client; dashboard via MCP",
    "core/, data/, Tests": "core/, data/, tests",
    "unverändert; Tests inkl. MCP-Contract-Tests, CI": "unchanged; tests incl. MCP contract tests, CI",
    "Umsetzung mit Strands und dem MCP-SDK": "Implementation with Strands and the MCP SDK",
    "Links umgesetzt (mcp_servers/server.py), Mitte und rechts Skizze für Phase 2":
        "Left implemented (mcp_servers/server.py), middle and right a sketch for phase 2",
    "MCP-Server realbasket (umgesetzt)": "MCP server realbasket (implemented)",
    "Fach-Agent als A2A-Dienst mit MCP-Tools": "Specialist agent as A2A service with MCP tools",
    "Orchestrator ruft A2A-Agenten": "Orchestrator calls A2A agents",
    "Pakete: mcp (MCPServer, stdio / Streamable HTTP) · strands.tools.mcp.MCPClient · Phase 2: "
    "strands-agents[a2a] (A2AServer) · strands-agents-tools (A2AClientToolProvider)":
        "Packages: mcp (MCPServer, stdio / Streamable HTTP) · strands.tools.mcp.MCPClient · phase 2: "
        "strands-agents[a2a] (A2AServer) · strands-agents-tools (A2AClientToolProvider)",
    "Querschnittsthemen": "Cross-cutting concerns",
    "Sicherheit": "Security",
    "Entra ID / OAuth 2.1 für MCP-HTTP und A2A": "Entra ID / OAuth 2.1 for MCP HTTP and A2A",
    "Auth-Schemata in der Agent Card": "Auth schemes in the agent card",
    "Schlüssel in Azure Key Vault statt .env": "Keys in Azure Key Vault instead of .env",
    "Least Privilege: Bereiche bei Bedarf als eigene Server (--areas)":
        "Least privilege: areas as separate servers when needed (--areas)",
    "Determinismus & Qualität": "Determinism & quality",
    "Zahlen nur aus MCP-Tools": "Numbers only from MCP tools",
    "Prüfergebnisse als Resource": "Check results as a resource",
    "Contract-Tests je Tool-Schema (umgesetzt)": "Contract tests per tool schema (implemented)",
    "Zahlen-Guardrail für Antworten (umgesetzt)": "Number guardrail for answers (implemented)",
    "Betrieb": "Operations",
    "Je Dienst ein Container (Azure Container Apps)": "One container per service (Azure Container Apps)",
    "Health-Checks, unabhängige Skalierung": "Health checks, independent scaling",
    "OpenTelemetry-Tracing über alle Hops": "OpenTelemetry tracing across all hops",
    "Versionierte Agent Cards und Tools": "Versioned agent cards and tools",
    "Roadmap und Empfehlung": "Roadmap and recommendation",
    "Phase 1 · umgesetzt ✓": "Phase 1 · implemented ✓",
    "Ein MCP-Server realbasket": "One MCP server realbasket",
    "Bereiche data · analysis · knowledge": "Areas data · analysis · knowledge",
    "Agent nutzt MCPClient (stdio / HTTP)": "Agent uses MCPClient (stdio / HTTP)",
    "Tests + CI grün": "Tests + CI green",
    "Nutzbar in Claude Desktop / VS Code": "Usable in Claude Desktop / VS Code",
    "Phase 2 · nach dem Hackathon": "Phase 2 · after the hackathon",
    "Collector, Analyst, Methodik als": "Collector, analyst, methodology as",
    "A2A-Dienste mit Agent Cards": "A2A services with agent cards",
    "Orchestrator als A2A-Server": "Orchestrator as A2A server",
    "Streamlit als A2A-Client": "Streamlit as A2A client",
    "Phase 3 · Produktion": "Phase 3 · production",
    "destatis-genesis-MCP (Live-VPI)": "destatis-genesis MCP (live CPI)",
    "Neue Quellen: Ländermieten, Gehälter": "New sources: state rents, salaries",
    "Vorteile": "Benefits",
    "Wiederverwendbar und interoperabel": "Reusable and interoperable",
    "Einzeln skalier- und deploybar": "Individually scalable and deployable",
    "Klare Schnittstellen, gleicher Rechenkern": "Clear interfaces, same calculation core",
    "Aufwand / Risiken": "Effort / risks",
    "Mehr Dienste, mehr Betrieb": "More services, more operations",
    "Zusätzliche Latenz je Netzwerk-Hop": "Additional latency per network hop",
    "Auth und Versionierung nötig – für den Hackathon genügt Phase 1":
        "Auth and versioning needed – phase 1 is enough for the hackathon",
}
