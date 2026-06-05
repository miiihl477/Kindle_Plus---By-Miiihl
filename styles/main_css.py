"""
Global CSS styles and theme definitions for WriterFlow.
"""

# Status configuration (used by UI helpers)
STATUS_CONFIG = {
    "Planejamento": {"color": "#6366f1", "icon": "📋", "bg": "#1e1b4b"},
    "Escrita":      {"color": "#06b6d4", "icon": "✍️",  "bg": "#0c4a6e"},
    "Revisão":      {"color": "#f59e0b", "icon": "🔍", "bg": "#451a03"},
    "Publicado":    {"color": "#10b981", "icon": "✅", "bg": "#064e3b"},
}

GENRE_OPTIONS = [
    "Ficção Científica", "Fantasia", "Romance", "Thriller", "Terror",
    "Mistério", "Aventura", "Drama", "Histórico", "Autobiografia",
    "Não-ficção", "Poesia", "Conto", "Infantil", "Jovem Adulto", "Outro"
]

STATUS_OPTIONS = list(STATUS_CONFIG.keys())

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');

/* ── Reset & Base ── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #0a0a0f; }
.block-container { padding: 2.5rem 2rem 1.5rem !important; max-width: 1400px !important; }

/* ── Hide Streamlit defaults ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Hide native sidebar navigation ── */
[data-testid="stSidebarNav"]          { display: none !important; }
[data-testid="stSidebarNavItems"]     { display: none !important; }
[data-testid="stSidebarNavSeparator"] { display: none !important; }
section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d0d1a 0%, #111127 100%);
    border-right: 1px solid #1e1e3f;
}
[data-testid="stSidebar"] .stMarkdown h1 {
    font-family: 'Playfair Display', serif;
    color: #c084fc;
    font-size: 1.4rem;
    letter-spacing: -0.02em;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4) !important;
}

/* ── Input fields ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    background: #13131f !important;
    border: 1px solid #2a2a4a !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 2px rgba(99,102,241,0.2) !important;
}

/* ── Cards ── */
.wf-card {
    background: linear-gradient(135deg, #13131f 0%, #1a1a2e 100%);
    border: 1px solid #1e1e3f;
    border-radius: 12px;
    padding: 1.25rem;
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
}
.wf-card:hover {
    border-color: #6366f1;
    box-shadow: 0 4px 24px rgba(99,102,241,0.15);
    transform: translateY(-2px);
}
.wf-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #6366f1, #8b5cf6, #06b6d4);
}

/* ── Section headers ── */
.wf-section-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.8rem;
    font-weight: 700;
    color: #e2e8f0;
    letter-spacing: -0.03em;
    margin-bottom: 0.25rem;
}
.wf-section-subtitle {
    color: #64748b;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}

/* ── Stats ── */
.wf-stat {
    background: #13131f;
    border: 1px solid #1e1e3f;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    text-align: center;
}
.wf-stat-value {
    font-family: 'Playfair Display', serif;
    font-size: 2rem;
    font-weight: 700;
    color: #c084fc;
    line-height: 1;
}
.wf-stat-label {
    font-size: 0.75rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 0.25rem;
}

/* ── Status badges ── */
.wf-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}

/* ── Progress bars ── */
.wf-progress-wrap { background: #1e1e3f; border-radius: 8px; height: 8px; overflow: hidden; }
.wf-progress-bar { height: 8px; border-radius: 8px; background: linear-gradient(90deg, #6366f1, #8b5cf6); transition: width 0.6s ease; }

/* ── Book cover placeholder ── */
.book-cover-placeholder {
    width: 100%; aspect-ratio: 2/3;
    background: linear-gradient(135deg, #1e1b4b, #2d1b69);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 3rem;
    border: 1px solid #2a2a4a;
}

/* ── Dividers ── */
.wf-divider { border: none; border-top: 1px solid #1e1e3f; margin: 1rem 0; }

/* ── Alert boxes ── */
.wf-info {
    background: rgba(99,102,241,0.1);
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 8px; padding: 0.75rem 1rem;
    color: #a5b4fc; font-size: 0.875rem;
    margin-bottom: 1rem;
}

/* ── Metric ── */
[data-testid="metric-container"] {
    background: #13131f;
    border: 1px solid #1e1e3f;
    border-radius: 10px;
    padding: 1rem !important;
}

/* ── Tab styling ── */
.stTabs [data-baseweb="tab-list"] {
    background: #0d0d1a !important;
    border-radius: 8px !important;
    padding: 4px !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #64748b !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
}
.stTabs [aria-selected="true"] {
    background: #1e1e3f !important;
    color: #c084fc !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    background: #13131f !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
}

/* ── Number input ── */
.stNumberInput input {
    background: #13131f !important;
    border: 1px solid #2a2a4a !important;
    color: #e2e8f0 !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0a0a0f; }
::-webkit-scrollbar-thumb { background: #2a2a4a; border-radius: 3px; }

/* ── Kindle/Reader mode ── */
.kindle-container {
    max-width: 680px; margin: 0 auto;
    padding: 3rem 2rem; min-height: 100vh;
}
.kindle-dark { background: #1a1209; color: #d4a853; }
.kindle-light { background: #faf6f0; color: #2c2416; }
.kindle-sepia { background: #f4ecd8; color: #5c4a32; }
.kindle-content p { text-indent: 2em; margin-bottom: 0.8em; text-align: justify; }
.kindle-content h1, .kindle-content h2, .kindle-content h3 {
    font-family: 'Playfair Display', serif;
    text-indent: 0; margin: 1.5em 0 0.8em;
}
</style>
"""