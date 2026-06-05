import logging
import markdown2
import streamlit as st
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from database import (
    initialize_database,
    BookService, ChapterService, CharacterService,
    WorldBuildingService, BrainDumpService, DashboardService,
    SettingsService, image_to_base64,
)
from export import export_to_docx, export_to_pdf, export_to_epub
from styles.main_css import (
    GLOBAL_CSS, STATUS_CONFIG, GENRE_OPTIONS, STATUS_OPTIONS,
)
from utils import count_words

# ═══════════════════════════════════════════════════════════════════════════════
# APP CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Kindle_Plus - By Miiihl",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_database()
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

ROLES = ["Protagonista", "Antagonista", "Coadjuvante", "Mentor", "Comic Relief",
         "Interesse Romântico", "Vilão", "Aliado", "Neutro", "Outro"]

_THEMES = {
    "🌙 Escuro": ("#1a1209", "#d4a853", "#3d2e1a"),
    "☀️ Claro":  ("#faf6f0", "#2c2416", "#ede8e0"),
    "📜 Sépia":  ("#f4ecd8", "#5c4a32", "#e8d9b8"),
}
_FONTS = {
    "Serif":  "'Georgia', 'Palatino', serif",
    "Sans":   "'Helvetica Neue', Arial, sans-serif",
    "Mono":   "'Courier New', monospace",
}
_AUTOSAVE = timedelta(seconds=45)

# ═══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def status_badge(status: str) -> str:
    cfg = STATUS_CONFIG.get(status, {"color": "#64748b", "icon": "📌"})
    return (
        f'<span class="wf-badge" style="background:{cfg["color"]}22;'
        f'color:{cfg["color"]};border:1px solid {cfg["color"]}55">'
        f'{cfg["icon"]} {status}</span>'
    )

def progress_bar_html(value: int, color: str = "#6366f1") -> str:
    val = min(100, max(0, value))
    return (
        f'<div class="wf-progress-wrap">'
        f'<div class="wf-progress-bar" style="width:{val}%;'
        f'background:linear-gradient(90deg,{color},{color}cc)"></div>'
        f'</div>'
        f'<div style="font-size:0.75rem;color:#64748b;margin-top:4px">{val}%</div>'
    )

def stat_card(value, label: str, icon: str = "") -> str:
    return (
        f'<div class="wf-stat">'
        f'<div class="wf-stat-value">{icon} {value}</div>'
        f'<div class="wf-stat-label">{label}</div>'
        f'</div>'
    )

def section_header(title: str, subtitle: str = ""):
    st.markdown(f'<div class="wf-section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="wf-section-subtitle">{subtitle}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ONBOARDING
# ═══════════════════════════════════════════════════════════════════════════════

_SAMPLE_CHAPTERS = [
    ("Prólogo — O Chamado", """## O Chamado

A carta chegou numa manhã de chuva fina, deslizando pelo vão da porta com um sussurro de papel velho. Ela ficou parada no tapete por alguns minutos antes que Elena a notasse — e quando a viu, algo no seu peito se contraiu de um jeito que não conseguia explicar.

O envelope era de um marrom desbotado, quase cor de terra seca. Não tinha remetente. Apenas o seu nome escrito em tinta azul-escura, numa caligrafia que parecia familiar demais para ser coincidência.

> *Quando o silêncio falar mais alto que as palavras, siga o rio para o norte.*

Ela leu a frase três vezes. Depois dobrou o papel com cuidado, como se fosse frágil, e foi preparar café."""),
    ("Capítulo 1 — A Floresta dos Espelhos", """## A Floresta

O rio começava atrás do mercado velho, num lugar que os moradores mais antigos chamavam de *Boca da Terra*. Elena chegou lá no fim da tarde, com a mochila pesando nos ombros e o mapa desenhado à mão que encontrara junto com a carta.

A floresta era densa, mas não opressiva. As árvores tinham cascas prateadas que capturavam a luz mortiça do fim do dia e a devolviam transformada — mais quente, mais âmbar.

- As sombras se moviam de maneira estranha
- Os sons chegavam com um leve atraso, como eco de si mesmos
- O cheiro era de terra molhada e algo mais antigo

Ela caminhou por quarenta minutos antes de ver a primeira árvore espelho."""),
    ("Capítulo 2 — O Guardião", """## O Guardião

O velho estava sentado numa raiz exposta, talhando algo num pedaço de madeira clara. Ele não olhou para cima quando Elena se aproximou — apenas continuou movendo a faca com gestos precisos e lentos.

**"Sabia que você viria"**, disse ele. **"A floresta me avisou."**

Elena ficou parada a alguns metros de distância. Havia algo nele que não encaixava com o ambiente — roupas demais para o calor, cabelos brancos demais para um homem que parecia ter cinquenta anos.

**"Quem escreveu a carta?"**

O velho colocou o talhe no bolso e se levantou com uma agilidade que contradisse a aparência de velhice.

**"Sua avó. Que morreu há sete anos."**"""),
]

_BRAIN_DUMPS = [
    ("E se a floresta fosse uma metáfora para a memória da protagonista? Cada árvore = uma lembrança?",
     "worldbuilding, metáfora, rascunho"),
    ("O guardião pode ser uma manifestação física do inconsciente coletivo da família de Elena.",
     "personagem, teoria, explorar"),
    ("Cena pendente: Elena encontra o diário da avó dentro de uma das árvores espelho.",
     "cena, plot, próximos capítulos"),
]

def should_show_onboarding() -> bool:
    if st.session_state.get("onboarding_dismissed"):
        return False
    books = BookService().list_books_lightweight()
    return len(books) == 0

def _create_sample_book():
    book_svc  = BookService()
    ch_svc    = ChapterService()
    brain_svc = BrainDumpService()
    dash_svc  = DashboardService()

    with st.spinner("Criando seu livro de exemplo…"):
        book_id = book_svc.create_book(
            title="A Floresta dos Espelhos",
            synopsis=(
                "Elena recebe uma carta assinada por sua avó — que morreu sete anos atrás. "
                "Seguindo as instruções, ela viaja para uma floresta que guarda segredos "
                "sobre sua família e sobre quem ela realmente é."
            ),
            genre="Fantasia",
            status="Escrita",
        )
        for title, content in _SAMPLE_CHAPTERS:
            ch_id = ch_svc.create_chapter(book_id, title)
            ch_svc.save_content(ch_id, content, book_id)
        for content, tags in _BRAIN_DUMPS:
            brain_svc.create(content, book_id, tags)
        dash_svc.save_goal(1000, "daily")
        dash_svc.save_goal(30000, "monthly")

    st.session_state["onboarding_dismissed"] = True
    st.session_state["selected_book_id"]     = book_id
    st.session_state["current_page"]         = "📚 Biblioteca"
    st.success("✅ Livro de exemplo criado! Explorando a Biblioteca…")
    st.rerun()

def render_onboarding():
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #0d0d1a 0%, #1a1035 50%, #0d1a2e 100%);
        border: 1px solid #2a2a4a; border-radius: 16px;
        padding: 3rem 2.5rem; text-align: center; margin-bottom: 2rem;">
        <div style="font-size: 3.5rem; margin-bottom: 0.75rem">📖</div>
        <h1 style="font-family:'Playfair Display',Georgia,serif;font-size:2.4rem;
                   font-weight:700;color:#e2e8f0;letter-spacing:-0.03em;margin-bottom:0.5rem">
            Bem-vinda ao Kindle_Plus - By Miiihl</h1>
        <p style="color:#94a3b8;font-size:1.05rem;max-width:540px;margin:0 auto">
            Sua plataforma para organizar, escrever e publicar histórias.
            Vamos começar com um livro de exemplo para você explorar tudo.</p>
    </div>
    """, unsafe_allow_html=True)

    features = [
        ("📚","Biblioteca","Organize seus livros com capas, sinopse e status"),
        ("✍️","Editor Markdown","Escreva com preview ao vivo e auto-save"),
        ("📖","Modo Kindle","Leia seu trabalho como num e-reader real"),
        ("👥","Personagens","Cadastre personagens com fotos e relacionamentos"),
        ("🌍","World Building","Locais, facções e cronologia do seu universo"),
        ("🧠","Brain Dump","Capture ideias rápidas antes que se percam"),
        ("📤","Exportação","PDF, DOCX e EPUB prontos para publicação"),
        ("📊","Dashboard","Acompanhe seu progresso e metas diárias"),
    ]
    cols = st.columns(4)
    for i, (icon, name, desc) in enumerate(features):
        with cols[i % 4]:
            st.markdown(f"""
            <div style="background:#13131f;border:1px solid #1e1e3f;border-radius:10px;
                        padding:1rem;text-align:center;margin-bottom:0.75rem;height:120px">
                <div style="font-size:1.8rem">{icon}</div>
                <div style="color:#c084fc;font-weight:600;font-size:0.85rem;margin:0.25rem 0">{name}</div>
                <div style="color:#64748b;font-size:0.75rem;line-height:1.4">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    col_cta, col_skip = st.columns([2, 1])
    with col_cta:
        if st.button("🚀 Criar livro de exemplo e começar a explorar",
                     use_container_width=True, type="primary"):
            _create_sample_book()
    with col_skip:
        if st.button("Começar com livro em branco →", use_container_width=True):
            st.session_state["onboarding_dismissed"] = True
            st.session_state["current_page"] = "📚 Biblioteca"
            st.session_state["show_new_book"] = True
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def render_dashboard():
    import pandas as pd
    import plotly.graph_objects as go
    import plotly.express as px

    section_header("📊 Dashboard", "Visão geral do seu progresso literário")

    _dash = DashboardService()
    data  = _dash.get_dashboard_data()

    # ── Stats row ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(stat_card(data["total_books"], "Livros", "📚"), unsafe_allow_html=True)
    with c2:
        st.markdown(stat_card(data["total_chapters"], "Capítulos", "📄"), unsafe_allow_html=True)
    with c3:
        wc = f"{data['total_words']:,}".replace(",", ".")
        st.markdown(stat_card(wc, "Palavras Totais", "✍️"), unsafe_allow_html=True)
    with c4:
        wt = f"{data['words_today']:,}".replace(",", ".")
        st.markdown(stat_card(wt, "Palavras Hoje", "⚡"), unsafe_allow_html=True)

    st.markdown("<div class='wf-divider'></div>", unsafe_allow_html=True)

    tab_visao, tab_progresso, tab_livros, tab_metas, tab_sessoes = st.tabs([
        "📈 Visão Geral", "🎯 Progresso", "📚 Meus Livros", "⚙️ Metas", "🕐 Sessões",
    ])

    # ── TAB: Visão Geral ──────────────────────────────────────────────────────
    with tab_visao:
        col_goal, col_chart = st.columns([1, 2])

        with col_goal:
            st.markdown("### 🎯 Metas")
            daily_goal   = data["daily_goal"]
            words_today  = data["words_today"]
            daily_pct    = min(100, int(words_today / daily_goal * 100)) if daily_goal else 0
            _db = min(100, max(0, daily_pct))
            st.markdown(f'''<div class="wf-card" style="margin-bottom:1rem">
                <div style="display:flex;justify-content:space-between;margin-bottom:8px">
                    <span style="color:#e2e8f0;font-weight:600">⚡ Meta Diária</span>
                    <span style="color:#c084fc">{words_today:,}/{daily_goal:,}</span>
                </div>
                <div class="wf-progress-wrap">
                    <div class="wf-progress-bar" style="width:{_db}%;background:linear-gradient(90deg,#6366f1,#6366f1cc)"></div>
                </div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px">{_db}%</div>
            </div>''', unsafe_allow_html=True)

            monthly_goal = data["monthly_goal"]
            words_month  = data["words_month"]
            monthly_pct  = min(100, int(words_month / monthly_goal * 100)) if monthly_goal else 0
            _mb = min(100, max(0, monthly_pct))
            st.markdown(f'''<div class="wf-card" style="margin-bottom:1rem">
                <div style="display:flex;justify-content:space-between;margin-bottom:8px">
                    <span style="color:#e2e8f0;font-weight:600">📅 Meta Mensal</span>
                    <span style="color:#06b6d4">{words_month:,}/{monthly_goal:,}</span>
                </div>
                <div class="wf-progress-wrap">
                    <div class="wf-progress-bar" style="width:{_mb}%;background:linear-gradient(90deg,#06b6d4,#06b6d4cc)"></div>
                </div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px">{_mb}%</div>
            </div>''', unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**Registrar Sessão de Escrita**")
            with st.form("session_form"):
                words_written = st.number_input("Palavras escritas agora", min_value=0, step=50)
                if st.form_submit_button("➕ Registrar"):
                    if words_written > 0:
                        _dash.log_words(words_written)
                        st.success(f"✅ {words_written} palavras registradas!")
                        st.rerun()

        with col_chart:
            st.markdown("### 📈 Evolução (últimos 30 dias)")
            from datetime import timedelta as _td
            daily_data = data.get("daily_data", [])
            end   = datetime.now().date()
            start = end - _td(days=29)
            date_range = [(start + _td(days=i)).isoformat() for i in range(30)]
            data_map   = {row["session_date"]: row["total"] for row in daily_data}
            import pandas as pd
            chart_data = pd.DataFrame({
                "Data": date_range,
                "Palavras": [data_map.get(d, 0) for d in date_range],
            })
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=chart_data["Data"], y=chart_data["Palavras"],
                marker_color="#6366f1", marker_opacity=0.8, name="Palavras",
            ))
            fig.add_hline(
                y=daily_goal, line_dash="dash", line_color="#f59e0b", opacity=0.7,
                annotation_text=f"Meta: {daily_goal}", annotation_font_color="#f59e0b",
            )
            fig.update_layout(
                plot_bgcolor="#0d0d1a", paper_bgcolor="#0d0d1a", font_color="#94a3b8",
                xaxis=dict(showgrid=False, tickformat="%d/%m"),
                yaxis=dict(gridcolor="#1e1e3f"),
                margin=dict(l=0, r=0, t=10, b=0), height=300, showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            if data["by_status"]:
                st.markdown("### 📚 Livros por Status")
                status_df = pd.DataFrame([
                    {"Status": k, "Quantidade": v} for k, v in data["by_status"].items()
                ])
                colors_map = {
                    "Planejamento": "#6366f1", "Escrita": "#06b6d4",
                    "Revisão": "#f59e0b", "Publicado": "#10b981",
                }
                fig2 = px.pie(
                    status_df, values="Quantidade", names="Status",
                    color="Status", color_discrete_map=colors_map, hole=0.5,
                )
                fig2.update_layout(
                    plot_bgcolor="#0d0d1a", paper_bgcolor="#0d0d1a", font_color="#94a3b8",
                    margin=dict(l=0, r=0, t=10, b=0), height=250,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.3),
                )
                fig2.update_traces(textinfo="percent+label")
                st.plotly_chart(fig2, use_container_width=True)

    # ── TAB: Progresso ────────────────────────────────────────────────────────
    with tab_progresso:
        import pandas as pd
        p1, p2 = st.columns(2)
        with p1:
            pct_d   = data["daily_progress"]
            color_d = "#10b981" if pct_d >= 100 else "#f59e0b" if pct_d >= 50 else "#6366f1"
            st.markdown(
                f'<div class="wf-card"><div style="color:#64748b;font-size:0.75rem;'
                f'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem">🎯 Meta Diária</div>'
                f'<div style="font-size:2.5rem;font-weight:700;color:{color_d};'
                f'font-family:Playfair Display,serif">{pct_d}%</div>'
                f'<div style="color:#64748b;margin-bottom:0.75rem">'
                f'{data["words_today"]:,} de {data["daily_goal"]:,} palavras</div>',
                unsafe_allow_html=True,
            )
            st.markdown(progress_bar_html(pct_d, color_d), unsafe_allow_html=True)
            remaining_d = max(0, data["daily_goal"] - data["words_today"])
            st.markdown(
                f'<div style="color:#64748b;font-size:0.8rem;margin-top:0.5rem">'
                f'{"✅ Meta atingida!" if pct_d >= 100 else f"Faltam {remaining_d:,} palavras"}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        with p2:
            pct_m   = data["monthly_progress"]
            color_m = "#10b981" if pct_m >= 100 else "#06b6d4" if pct_m >= 50 else "#818cf8"
            st.markdown(
                f'<div class="wf-card"><div style="color:#64748b;font-size:0.75rem;'
                f'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem">📅 Meta Mensal</div>'
                f'<div style="font-size:2.5rem;font-weight:700;color:{color_m};'
                f'font-family:Playfair Display,serif">{pct_m}%</div>'
                f'<div style="color:#64748b;margin-bottom:0.75rem">'
                f'{data["words_month"]:,} de {data["monthly_goal"]:,} palavras</div>',
                unsafe_allow_html=True,
            )
            st.markdown(progress_bar_html(pct_m, color_m), unsafe_allow_html=True)
            remaining_m = max(0, data["monthly_goal"] - data["words_month"])
            st.markdown(
                f'<div style="color:#64748b;font-size:0.8rem;margin-top:0.5rem">'
                f'{"✅ Meta atingida!" if pct_m >= 100 else f"Faltam {remaining_m:,} palavras"}'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        if data["daily_data"]:
            st.markdown("<br>", unsafe_allow_html=True)
            df = pd.DataFrame(data["daily_data"])
            df["session_date"] = pd.to_datetime(df["session_date"])
            df = df.sort_values("session_date")
            df["acumulado"] = df["total"].cumsum()
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=df["session_date"], y=df["acumulado"],
                fill="tozeroy", fillcolor="rgba(99,102,241,0.12)",
                line=dict(color="#6366f1", width=2), name="Acumulado",
                hovertemplate="<b>%{x|%d/%m}</b><br>%{y:,} palavras acumuladas<extra></extra>",
            ))
            fig3.add_trace(go.Bar(
                x=df["session_date"], y=df["total"],
                marker_color="rgba(6,182,212,0.5)", name="Por dia",
                hovertemplate="<b>%{x|%d/%m}</b><br>%{y:,} palavras no dia<extra></extra>",
            ))
            fig3.update_layout(
                title="Produção acumulada — últimos 30 dias",
                plot_bgcolor="#0d0d1a", paper_bgcolor="#13131f", font_color="#e2e8f0",
                xaxis=dict(gridcolor="#1e1e3f", title=""),
                yaxis=dict(gridcolor="#1e1e3f"),
                title_font_size=14, margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(bgcolor="rgba(0,0,0,0)", font_color="#94a3b8"),
                barmode="overlay",
            )
            st.plotly_chart(fig3, use_container_width=True)

    # ── TAB: Meus Livros ──────────────────────────────────────────────────────
    with tab_livros:
        import pandas as pd
        books = BookService().list_books_lightweight()
        if not books:
            st.markdown('<div class="wf-info">Nenhum livro criado ainda. Vá para a Biblioteca!</div>', unsafe_allow_html=True)
        else:
            for book in books:
                updated = book.get("updated_at", "")[:10] if book.get("updated_at") else "—"
                ba, bb, bc, bd, be = st.columns([3, 1, 1, 1, 1])
                with ba:
                    st.markdown(
                        f'<div style="font-weight:600;color:#e2e8f0">{book["title"]}</div>'
                        f'<div style="color:#64748b;font-size:0.8rem">'
                        f'{book.get("genre","") or "Sem gênero"} · Atualizado {updated}</div>',
                        unsafe_allow_html=True,
                    )
                with bb:
                    st.markdown(status_badge(book["status"]), unsafe_allow_html=True)
                with bc:
                    st.markdown(
                        f'<div style="color:#c084fc;font-weight:600">{book["word_count"]:,}</div>'
                        f'<div style="color:#64748b;font-size:0.72rem">palavras</div>',
                        unsafe_allow_html=True,
                    )
                with bd:
                    chs = ChapterService().get_chapters_lightweight(book["id"])
                    st.markdown(
                        f'<div style="color:#06b6d4;font-weight:600">{len(chs)}</div>'
                        f'<div style="color:#64748b;font-size:0.72rem">capítulos</div>',
                        unsafe_allow_html=True,
                    )
                with be:
                    if st.button("✍️ Abrir", key=f"dash_open_{book['id']}"):
                        st.session_state["selected_book_id"] = book["id"]
                        st.session_state["current_page"]     = "✍️ Capítulos"
                        st.rerun()
                st.markdown('<div class="wf-divider"></div>', unsafe_allow_html=True)

            df_books = pd.DataFrame([
                {"title": b["title"][:25] + ("…" if len(b["title"]) > 25 else ""),
                 "palavras": b["word_count"]}
                for b in books if b["word_count"] > 0
            ])
            if not df_books.empty and len(df_books) > 1:
                fig4 = px.bar(
                    df_books.sort_values("palavras", ascending=True),
                    x="palavras", y="title", orientation="h",
                    color="palavras",
                    color_continuous_scale=["#1e1b4b","#6366f1","#c084fc"],
                    labels={"palavras":"Palavras","title":""},
                )
                fig4.update_layout(
                    title="Palavras por livro", plot_bgcolor="#0d0d1a", paper_bgcolor="#13131f",
                    font_color="#e2e8f0", xaxis=dict(gridcolor="#1e1e3f"),
                    yaxis=dict(gridcolor="#1e1e3f"), title_font_size=14,
                    margin=dict(l=0,r=0,t=40,b=0), coloraxis_showscale=False,
                )
                fig4.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,} palavras<extra></extra>")
                st.plotly_chart(fig4, use_container_width=True)

    # ── TAB: Metas ────────────────────────────────────────────────────────────
    with tab_metas:
        st.markdown("#### ⚙️ Configurar Metas de Escrita")
        with st.form("goals_form"):
            mg1, mg2 = st.columns(2)
            with mg1:
                st.markdown('<div style="color:#f59e0b;font-size:1rem;font-weight:600;margin-bottom:0.5rem">🎯 Meta Diária</div>', unsafe_allow_html=True)
                daily_target = st.number_input("Palavras por dia", min_value=100,
                    value=data["daily_goal"], step=100, label_visibility="collapsed")
                st.caption(f"Atual: {data['daily_goal']:,} palavras/dia")
            with mg2:
                st.markdown('<div style="color:#818cf8;font-size:1rem;font-weight:600;margin-bottom:0.5rem">📅 Meta Mensal</div>', unsafe_allow_html=True)
                monthly_target = st.number_input("Palavras por mês", min_value=1000,
                    value=data["monthly_goal"], step=1000, label_visibility="collapsed")
                st.caption(f"Atual: {data['monthly_goal']:,} palavras/mês")
            if st.form_submit_button("💾 Salvar Metas", use_container_width=True):
                _dash.save_goal(daily_target, "daily")
                _dash.save_goal(monthly_target, "monthly")
                st.success("✅ Metas salvas!")
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 💡 Metas Sugeridas")
        sugestoes = [
            ("🌱 Iniciante",   200,  6000,  "5 min/dia"),
            ("✍️ Regular",     500,  15000, "15 min/dia"),
            ("📖 Consistente", 1000, 30000, "30 min/dia"),
            ("🚀 Intenso",     2000, 60000, "1h/dia"),
            ("💪 NaNoWriMo",   1667, 50000, "~45 min/dia"),
        ]
        cols_s = st.columns(len(sugestoes))
        for col, (nome, dia, mes, tempo) in zip(cols_s, sugestoes):
            with col:
                st.markdown(
                    f'<div class="wf-card" style="text-align:center">'
                    f'<div style="font-weight:600;color:#e2e8f0;margin-bottom:0.25rem">{nome}</div>'
                    f'<div style="color:#c084fc;font-size:0.9rem">{dia:,} palavras/dia</div>'
                    f'<div style="color:#64748b;font-size:0.75rem">{mes:,}/mês · {tempo}</div>'
                    f'</div>', unsafe_allow_html=True,
                )
                if st.button("Usar", key=f"sugestao_{nome}", use_container_width=True):
                    _dash.save_goal(dia, "daily")
                    _dash.save_goal(mes, "monthly")
                    st.success(f"Meta '{nome}' aplicada!")
                    st.rerun()

    # ── TAB: Sessões ──────────────────────────────────────────────────────────
    with tab_sessoes:
        import pandas as pd
        st.markdown("#### 🕐 Histórico de Sessões")
        if not data["daily_data"]:
            st.markdown('<div class="wf-info">Nenhuma sessão ainda. Salve capítulos para ver o histórico.</div>', unsafe_allow_html=True)
        else:
            df_sess = pd.DataFrame(data["daily_data"])
            df_sess["session_date"] = pd.to_datetime(df_sess["session_date"])
            df_sess = df_sess.sort_values("session_date", ascending=False)

            sm1, sm2, sm3, sm4 = st.columns(4)
            total_dias = len(df_sess)
            media_dia  = int(df_sess["total"].mean())
            melhor_dia = int(df_sess["total"].max())
            total_sess = int(df_sess["total"].sum())
            for col, (val, label, color) in zip([sm1,sm2,sm3,sm4],[
                (total_dias,        "Dias ativos",     "#6366f1"),
                (f"{media_dia:,}",  "Média/dia",       "#06b6d4"),
                (f"{melhor_dia:,}", "Melhor dia",      "#f59e0b"),
                (f"{total_sess:,}", "Total período",   "#10b981"),
            ]):
                with col:
                    st.markdown(
                        f'<div class="wf-stat">'
                        f'<div class="wf-stat-value" style="color:{color}">{val}</div>'
                        f'<div class="wf-stat-label">{label}</div>'
                        f'</div>', unsafe_allow_html=True,
                    )
            st.markdown("<br>", unsafe_allow_html=True)
            for _, row in df_sess.iterrows():
                data_fmt = row["session_date"].strftime("%d/%m/%Y")
                total    = int(row["total"])
                pct      = min(100, int(total / data["daily_goal"] * 100)) if data["daily_goal"] else 0
                color    = "#10b981" if pct >= 100 else "#f59e0b" if pct >= 50 else "#6366f1"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:1rem;'
                    f'padding:0.5rem 0;border-bottom:1px solid #1e1e3f">'
                    f'<div style="color:#94a3b8;font-size:0.85rem;min-width:90px">{data_fmt}</div>'
                    f'<div style="flex:1"><div class="wf-progress-wrap">'
                    f'<div class="wf-progress-bar" style="width:{pct}%;'
                    f'background:linear-gradient(90deg,{color},{color}cc)"></div>'
                    f'</div></div>'
                    f'<div style="color:{color};font-weight:600;min-width:80px;text-align:right">'
                    f'{total:,} palavras</div></div>',
                    unsafe_allow_html=True,
                )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: LIBRARY
# ═══════════════════════════════════════════════════════════════════════════════

def render_library():
    section_header("📚 Biblioteca", "Todos os seus livros em um só lugar")

    _book_svc = BookService()
    tab_books, tab_trash = st.tabs(["📚 Livros", "🗑️ Lixeira"])

    with tab_books:
        col_search, col_genre, col_status, col_btn = st.columns([3, 2, 2, 1])
        with col_search:
            query = st.text_input("🔍", placeholder="Buscar livros...", label_visibility="collapsed")
        with col_genre:
            genres = ["Todos"] + _book_svc.get_all_genres()
            genre_filter = st.selectbox("Gênero", genres, label_visibility="collapsed")
        with col_status:
            status_filter = st.selectbox("Status", ["Todos"] + STATUS_OPTIONS, label_visibility="collapsed")
        with col_btn:
            if st.button("✚ Novo", use_container_width=True):
                st.session_state["show_new_book"] = True
                st.session_state.pop("show_edit_book", None)

        if st.session_state.get("show_new_book"):
            with st.expander("📖 Criar Novo Livro", expanded=True):
                with st.form("new_book_form"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        cover_file = st.file_uploader("Capa", type=["jpg","jpeg","png","webp"])
                    with c2:
                        title    = st.text_input("Título *")
                        synopsis = st.text_area("Sinopse", height=100)
                        cg, cs   = st.columns(2)
                        with cg: genre  = st.selectbox("Gênero", [""]+GENRE_OPTIONS)
                        with cs: status = st.selectbox("Status", STATUS_OPTIONS)
                    s1, s2 = st.columns(2)
                    with s1: submitted = st.form_submit_button("💾 Criar", use_container_width=True)
                    with s2:
                        if st.form_submit_button("❌ Cancelar", use_container_width=True):
                            st.session_state["show_new_book"] = False
                            st.rerun()
                    if submitted:
                        if not title.strip():
                            st.error("Título obrigatório.")
                        else:
                            _book_svc.create_book(title.strip(), synopsis, genre, status, cover_file)
                            st.session_state["show_new_book"] = False
                            st.rerun()

        edit_id = st.session_state.get("show_edit_book")
        if edit_id:
            book_data = _book_svc.get_book(edit_id)
            if book_data:
                _render_edit_form(book_data, _book_svc)

        gf    = None if genre_filter  == "Todos" else genre_filter
        sf    = None if status_filter == "Todos" else status_filter
        books = _book_svc.list_books(query, gf, sf)

        if not books:
            st.markdown("""
            <div style="text-align:center;padding:4rem;color:#64748b">
                <div style="font-size:4rem">📚</div>
                <h3 style="color:#94a3b8">Nenhum livro encontrado</h3>
                <p>Clique em ✚ Novo para criar seu primeiro livro.</p>
            </div>""", unsafe_allow_html=True)
        else:
            COLS = 4
            for i in range(0, len(books), COLS):
                cols = st.columns(COLS)
                for j, book in enumerate(books[i:i+COLS]):
                    with cols[j]:
                        _render_book_card(book, _book_svc)

    with tab_trash:
        deleted = _book_svc.get_deleted_books()
        if not deleted:
            st.markdown('<div style="text-align:center;padding:2.5rem;color:#64748b"><div style="font-size:2rem">✨</div><p>Lixeira vazia.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f"**{len(deleted)} livro(s) na lixeira**")
            for b in deleted:
                c_info, c_restore, c_purge = st.columns([5, 1, 1])
                with c_info:
                    deleted_on = (b.get("deleted_at") or "")[:10]
                    wc = f"{b.get('word_count',0):,}".replace(",",".")
                    st.markdown(f'<div style="padding:0.5rem 0;border-bottom:1px solid #1e1e3f"><span style="color:#e2e8f0;font-weight:500">{b["title"]}</span><span style="color:#64748b;font-size:0.75rem;margin-left:0.75rem">{b.get("genre","")} · {wc} palavras · deletado em {deleted_on}</span></div>', unsafe_allow_html=True)
                with c_restore:
                    if st.button("↩ Restaurar", key=f"rbk_{b['id']}", use_container_width=True):
                        _book_svc.restore_book(b["id"])
                        st.rerun()
                with c_purge:
                    if st.button("💀 Apagar", key=f"pbk_{b['id']}", use_container_width=True):
                        st.session_state[f"purge_bk_{b['id']}"] = True
                if st.session_state.get(f"purge_bk_{b['id']}"):
                    st.warning(f"Excluir '{b['title']}' permanentemente?")
                    p1, p2 = st.columns(2)
                    with p1:
                        if st.button("✅ Excluir para sempre", key=f"pbk_yes_{b['id']}"):
                            _book_svc.delete_book(b["id"])
                            st.session_state.pop(f"purge_bk_{b['id']}", None)
                            st.rerun()
                    with p2:
                        if st.button("❌ Cancelar", key=f"pbk_no_{b['id']}"):
                            st.session_state.pop(f"purge_bk_{b['id']}", None)
                            st.rerun()


def _render_book_card(book: dict, _book_svc):
    book_id      = book["id"]
    is_edit_open = st.session_state.get("show_edit_book") == book_id

    if book.get("cover_image"):
        img = image_to_base64(book["cover_image"])
        cover_html = f'<img src="{img}" style="width:100%;aspect-ratio:2/3;object-fit:cover;border-radius:8px;border:1px solid #2a2a4a">'
    else:
        cover_html = '<div class="book-cover-placeholder">📖</div>'

    badge = status_badge(book.get("status","Planejamento"))
    wc    = f"{book.get('word_count',0):,}".replace(",",".")
    bdr   = "border-color:#6366f1!important;" if is_edit_open else ""

    st.markdown(f"""
    <div class="wf-card" style="{bdr}">
        {cover_html}
        <div style="margin-top:0.75rem">
            <div style="font-weight:600;color:#e2e8f0;font-size:0.9rem;margin-bottom:4px;
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{book['title']}">{book['title']}</div>
            <div style="margin-bottom:6px">{badge}</div>
            <div style="font-size:0.75rem;color:#64748b">{book.get('genre','')}{'·' if book.get('genre') else ''} {wc} palavras</div>
        </div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        lbl = "✏️ Fechar" if is_edit_open else "✏️ Editar"
        if st.button(lbl, key=f"edit_{book_id}", use_container_width=True):
            if is_edit_open:
                st.session_state.pop("show_edit_book", None)
            else:
                st.session_state["show_edit_book"] = book_id
                st.session_state["show_new_book"]  = False
            st.rerun()
    with c2:
        if st.button("✍️ Escrever", key=f"write_{book_id}", use_container_width=True):
            st.session_state["selected_book_id"] = book_id
            st.session_state["current_page"]     = "✍️ Capítulos"
            st.rerun()
    with c3:
        if st.button("📖 Ler", key=f"read_{book_id}", use_container_width=True):
            st.session_state["kindle_book_id"] = book_id
            st.session_state["current_page"]   = "📖 Modo Kindle"
            st.rerun()


def _render_edit_form(book: dict, _book_svc):
    book_id     = book["id"]
    confirm_key = f"confirm_del_{book_id}"

    with st.expander(f"✏️ Editando: {book['title']}", expanded=True):
        with st.form(f"edit_{book_id}"):
            cc, cf = st.columns([1, 2])
            with cc:
                if book.get("cover_image"):
                    st.markdown(f'<img src="{image_to_base64(book["cover_image"])}" style="width:100%;border-radius:8px;margin-bottom:0.5rem">', unsafe_allow_html=True)
                cover_file = st.file_uploader("Nova capa", type=["jpg","jpeg","png","webp"])
            with cf:
                title    = st.text_input("Título", value=book["title"])
                synopsis = st.text_area("Sinopse", value=book.get("synopsis",""), height=100)
                cg, cs   = st.columns(2)
                with cg:
                    opts  = [""]+GENRE_OPTIONS
                    g     = book.get("genre","")
                    genre = st.selectbox("Gênero", opts, index=opts.index(g) if g in opts else 0)
                with cs:
                    cur    = book.get("status", STATUS_OPTIONS[0])
                    if cur not in STATUS_OPTIONS: cur = STATUS_OPTIONS[0]
                    status = st.selectbox("Status", STATUS_OPTIONS, index=STATUS_OPTIONS.index(cur))

            s1, s2, s3 = st.columns(3)
            with s1:
                if st.form_submit_button("💾 Salvar", use_container_width=True):
                    if not title.strip():
                        st.error("Título obrigatório.")
                    else:
                        _book_svc.update_book(book_id, title=title.strip(),
                            synopsis=synopsis, genre=genre, status=status,
                            cover_file=cover_file or None)
                        st.session_state.pop("show_edit_book", None)
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
            with s2:
                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                    st.session_state.pop("show_edit_book", None)
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
            with s3:
                if st.form_submit_button("🗑️ Lixeira", use_container_width=True):
                    if st.session_state.get(confirm_key):
                        _book_svc.soft_delete_book(book_id)
                        st.session_state.pop("show_edit_book", None)
                        st.session_state.pop(confirm_key, None)
                        st.session_state.pop("selected_book_id", None)
                        st.rerun()
                    else:
                        st.session_state[confirm_key] = True
                        st.rerun()
        if st.session_state.get(confirm_key):
            st.warning(f"⚠️ Mover **{book['title']}** para a lixeira? Clique em 🗑️ Lixeira novamente para confirmar.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: CHAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

def _dk(ch_id):       return f"draft_{ch_id}"
def _dirty(ch_id):    return f"dirty_{ch_id}"
def _saved_at(ch_id): return f"saved_at_{ch_id}"

def _init_draft(ch: dict):
    k = _dk(ch["id"])
    if k not in st.session_state:
        st.session_state[k]                = ch.get("content") or ""
        st.session_state[_dirty(ch["id"])] = False
        st.session_state[_saved_at(ch["id"])] = datetime.now()

def _flush(ch_id: int, book_id: int):
    content = st.session_state.get(_dk(ch_id), "")
    ChapterService().save_content(ch_id, content, book_id)
    st.session_state[_dirty(ch_id)]    = False
    st.session_state[_saved_at(ch_id)] = datetime.now()

def _maybe_autosave(ch_id: int, book_id: int) -> bool:
    if not st.session_state.get(_dirty(ch_id)):
        return False
    last = st.session_state.get(_saved_at(ch_id), datetime.min)
    if datetime.now() - last >= _AUTOSAVE:
        _flush(ch_id, book_id)
        return True
    return False

_FOCUS_CSS = """
<style>
[data-testid="stSidebar"]        { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
.block-container { max-width: 860px !important; padding: 1rem 1.5rem !important; }
</style>
"""

def render_chapters():
    _book_svc = BookService()
    _ch_svc   = ChapterService()

    if st.session_state.get("focus_mode"):
        st.markdown(_FOCUS_CSS, unsafe_allow_html=True)

    section_header("✍️ Capítulos", "Escreva e organize os capítulos do seu livro")

    books = _book_svc.list_books_lightweight()
    if not books:
        st.info("📚 Crie um livro na Biblioteca primeiro.")
        return

    book_options = {b["id"]: b["title"] for b in books}
    selected_id  = st.session_state.get("selected_book_id")
    sel_ids      = list(book_options.keys())
    default_idx  = sel_ids.index(selected_id) if selected_id in sel_ids else 0

    col_sel, col_badge, col_focus = st.columns([4, 1, 1])
    with col_sel:
        chosen_id = st.selectbox("Livro", sel_ids,
            format_func=lambda x: book_options[x],
            index=default_idx, label_visibility="collapsed")
        st.session_state["selected_book_id"] = chosen_id
    with col_badge:
        book = _book_svc.get_book(chosen_id)
        if book:
            st.markdown(status_badge(book.get("status","Planejamento")), unsafe_allow_html=True)
    with col_focus:
        focus_label = "🔲 Sair" if st.session_state.get("focus_mode") else "🔲 Foco"
        if st.button(focus_label, use_container_width=True):
            st.session_state["focus_mode"] = not st.session_state.get("focus_mode", False)
            st.rerun()

    st.markdown("---")
    tab_editor, tab_trash = st.tabs(["✍️ Editor", "🗑️ Lixeira"])

    with tab_editor:
        chapters_nav = _ch_svc.get_chapters_lightweight(chosen_id)

        if st.session_state.get("focus_mode"):
            col_list, col_editor = None, st
        else:
            col_list, col_editor = st.columns([1, 3])

        if col_list is not None:
            with col_list:
                st.markdown("**📑 Capítulos**")
                with st.form("new_ch_form"):
                    new_title = st.text_input("Novo capítulo", placeholder="Título…")
                    if st.form_submit_button("✚ Adicionar", use_container_width=True):
                        if new_title.strip():
                            ch_id = _ch_svc.create_chapter(chosen_id, new_title.strip())
                            st.session_state["active_chapter_id"] = ch_id
                            st.rerun()
                st.markdown("")

                active_ch_id   = st.session_state.get("active_chapter_id")
                pending_switch = st.session_state.get("pending_chapter_switch")

                for ch in chapters_nav:
                    ch_id    = ch["id"]
                    is_active = ch_id == active_ch_id
                    is_dirty  = st.session_state.get(_dirty(ch_id), False) if is_active else False
                    label     = f"{'▶ ' if is_active else ''}{'🔴 ' if is_dirty else ''}{ch['title']}"

                    c_btn, c_del = st.columns([4, 1])
                    with c_btn:
                        if st.button(label, key=f"ch_{ch_id}", use_container_width=True):
                            if ch_id != active_ch_id:
                                if active_ch_id and st.session_state.get(_dirty(active_ch_id)):
                                    st.session_state["pending_chapter_switch"] = ch_id
                                else:
                                    st.session_state["active_chapter_id"] = ch_id
                                st.rerun()
                    with c_del:
                        if st.button("🗑", key=f"d_{ch_id}"):
                            st.session_state[f"confirm_del_{ch_id}"] = True

                    if st.session_state.get(f"confirm_del_{ch_id}"):
                        st.warning(f"Mover '{ch['title']}' para a lixeira?")
                        y, n = st.columns(2)
                        with y:
                            if st.button("Sim", key=f"yes_{ch_id}"):
                                _ch_svc.soft_delete_chapter(ch_id, chosen_id)
                                st.session_state.pop(f"confirm_del_{ch_id}", None)
                                if st.session_state.get("active_chapter_id") == ch_id:
                                    st.session_state.pop("active_chapter_id", None)
                                st.rerun()
                        with n:
                            if st.button("Não", key=f"no_{ch_id}"):
                                st.session_state.pop(f"confirm_del_{ch_id}", None)
                                st.rerun()

                    st.markdown(
                        f'<div style="font-size:0.7rem;color:#64748b;margin-top:-6px;'
                        f'padding-left:4px">{ch.get("word_count",0):,} palavras</div>',
                        unsafe_allow_html=True,
                    )

        # Editor pane
        _ed = col_editor
        with _ed:
            active_ch_id   = st.session_state.get("active_chapter_id")
            pending_switch = st.session_state.get("pending_chapter_switch")

            if pending_switch and active_ch_id:
                target_title = next(
                    (c["title"] for c in chapters_nav if c["id"] == pending_switch), "capítulo"
                )
                st.warning(f"⚠️ Alterações não salvas. O que fazer antes de abrir **{target_title}**?")
                g1, g2, g3 = st.columns(3)
                with g1:
                    if st.button("💾 Salvar e continuar", use_container_width=True):
                        _flush(active_ch_id, chosen_id)
                        st.session_state["active_chapter_id"] = pending_switch
                        st.session_state.pop("pending_chapter_switch", None)
                        st.rerun()
                with g2:
                    if st.button("🗑 Descartar e continuar", use_container_width=True):
                        st.session_state.pop(_dk(active_ch_id), None)
                        st.session_state[_dirty(active_ch_id)] = False
                        st.session_state["active_chapter_id"] = pending_switch
                        st.session_state.pop("pending_chapter_switch", None)
                        st.rerun()
                with g3:
                    if st.button("❌ Cancelar", use_container_width=True):
                        st.session_state.pop("pending_chapter_switch", None)
                        st.rerun()
            elif not active_ch_id:
                st.markdown("""
                <div style="text-align:center;padding:4rem;color:#64748b">
                    <div style="font-size:3rem">✍️</div>
                    <h3 style="color:#94a3b8">Selecione ou crie um capítulo</h3>
                </div>""", unsafe_allow_html=True)
            else:
                ch = _ch_svc.get_chapter(active_ch_id)
                if not ch:
                    st.warning("Capítulo não encontrado.")
                else:
                    _init_draft(ch)
                    col_title, col_stat = st.columns([4, 1])
                    with col_title:
                        new_title = st.text_input("Título", value=ch["title"], key=f"title_{active_ch_id}")
                        if new_title != ch["title"]:
                            _ch_svc.update_chapter(active_ch_id, title=new_title)
                    with col_stat:
                        current_draft = st.session_state.get(_dk(active_ch_id), "")
                        live_wc       = count_words(current_draft)
                        is_dirty      = st.session_state.get(_dirty(active_ch_id), False)
                        saved_at      = st.session_state.get(_saved_at(active_ch_id), datetime.now())
                        saved_str     = saved_at.strftime("%H:%M")
                        indicator     = "🔴 Não salvo" if is_dirty else f"✅ {saved_str}"
                        ind_color     = "#f59e0b" if is_dirty else "#10b981"
                        st.markdown(f"""
                        <div style="text-align:right;padding-top:1.5rem">
                            <div style="font-size:0.75rem;color:{ind_color}">{indicator}</div>
                            <div style="color:#6366f1;font-weight:600;font-size:1rem">{live_wc:,}</div>
                            <div style="color:#64748b;font-size:0.7rem">palavras</div>
                        </div>""", unsafe_allow_html=True)

                    preview_on = st.session_state.get(f"preview_{active_ch_id}", False)
                    c_info, c_prev_btn = st.columns([5, 1])
                    with c_info:
                        st.markdown('<div class="wf-info">💡 <strong>Markdown</strong> — **negrito** *itálico* ## Título > Citação — Auto-save 45s</div>', unsafe_allow_html=True)
                    with c_prev_btn:
                        if st.button("👁 Preview", use_container_width=True, key=f"ptgl_{active_ch_id}"):
                            st.session_state[f"preview_{active_ch_id}"] = not preview_on
                            st.rerun()

                    if preview_on:
                        ed_col, prev_col = st.columns(2)
                        with ed_col:
                            content = st.text_area("Conteudo",
                                value=st.session_state.get(_dk(active_ch_id), ""),
                                height=520, key=f"editor_{active_ch_id}",
                                label_visibility="collapsed", placeholder="Comece a escrever...")
                        with prev_col:
                            _prev_src = st.session_state.get(_dk(active_ch_id), "") or ""
                            _html = markdown2.markdown(_prev_src,
                                extras=["fenced-code-blocks","tables","strike","footnotes"])
                            st.markdown(
                                "<div style='background:#13131f;border:1px solid #1e1e3f;"
                                "border-radius:8px;padding:1.5rem 2rem;font-family:Georgia,serif;"
                                "line-height:1.8;color:#d1d5db;height:520px;overflow-y:auto;"
                                "font-size:0.95rem'>" + _html + "</div>",
                                unsafe_allow_html=True,
                            )
                    else:
                        content = st.text_area("Conteudo",
                            value=st.session_state.get(_dk(active_ch_id), ""),
                            height=520, key=f"editor_{active_ch_id}",
                            label_visibility="collapsed", placeholder="Comece a escrever...")

                    if content != st.session_state.get(_dk(active_ch_id)):
                        st.session_state[_dk(active_ch_id)]    = content
                        st.session_state[_dirty(active_ch_id)] = True

                    s1, s2, _ = st.columns([1, 1, 4])
                    with s1:
                        if st.button("💾 Salvar", key=f"save_{active_ch_id}", use_container_width=True):
                            _flush(active_ch_id, chosen_id)
                            st.rerun()
                    with s2:
                        if st.session_state.get("focus_mode"):
                            if st.button("Sair Foco", use_container_width=True, key="exit_focus_2"):
                                st.session_state["focus_mode"] = False
                                st.rerun()

                    if _maybe_autosave(active_ch_id, chosen_id):
                        st.toast("Auto-saved! ✅")

    with tab_trash:
        deleted = _ch_svc.get_deleted_chapters(chosen_id)
        if not deleted:
            st.markdown('<div style="text-align:center;padding:2rem;color:#64748b"><div style="font-size:2rem">✨</div><p>Lixeira vazia.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f"**{len(deleted)} capítulo(s) na lixeira**")
            for ch in deleted:
                col_info, col_restore, col_purge = st.columns([5, 1, 1])
                with col_info:
                    deleted_on = (ch.get("deleted_at") or "")[:10]
                    st.markdown(f'<div style="padding:0.5rem 0;border-bottom:1px solid #1e1e3f"><span style="color:#e2e8f0;font-weight:500">{ch["title"]}</span><span style="color:#64748b;font-size:0.75rem;margin-left:0.75rem">{ch.get("word_count",0):,} palavras · deletado em {deleted_on}</span></div>', unsafe_allow_html=True)
                with col_restore:
                    if st.button("↩ Restaurar", key=f"rst_{ch['id']}", use_container_width=True):
                        _ch_svc.restore_chapter(ch["id"], chosen_id)
                        st.rerun()
                with col_purge:
                    if st.button("💀 Apagar", key=f"prg_{ch['id']}", use_container_width=True):
                        st.session_state[f"purge_{ch['id']}"] = True
                if st.session_state.get(f"purge_{ch['id']}"):
                    st.warning(f"Excluir '{ch['title']}' permanentemente?")
                    p1, p2 = st.columns(2)
                    with p1:
                        if st.button("✅ Excluir para sempre", key=f"pyes_{ch['id']}"):
                            _ch_svc.delete_chapter(ch["id"], chosen_id)
                            st.session_state.pop(f"purge_{ch['id']}", None)
                            st.rerun()
                    with p2:
                        if st.button("❌ Cancelar", key=f"pno_{ch['id']}"):
                            st.session_state.pop(f"purge_{ch['id']}", None)
                            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: KINDLE
# ═══════════════════════════════════════════════════════════════════════════════

def render_kindle():
    _book_svc     = BookService()
    _ch_svc       = ChapterService()
    _settings_svc = SettingsService()

    books = _book_svc.list_books_lightweight()
    if not books:
        st.info("📚 Crie um livro na Biblioteca primeiro.")
        return

    book_options = {b["id"]: b["title"] for b in books}
    sel_ids = list(book_options.keys())

    saved_bid, saved_idx = _settings_svc.get_kindle_position()
    current_bid = st.session_state.get("kindle_book_id") or saved_bid
    if current_bid not in sel_ids:
        current_bid = sel_ids[0]
    current_idx = st.session_state.get("kindle_chapter_idx")
    if current_idx is None:
        current_idx = saved_idx if saved_bid == current_bid else 0

    col_book, col_theme, col_font, col_size = st.columns([3, 2, 1, 1])
    with col_book:
        book_idx  = sel_ids.index(current_bid) if current_bid in sel_ids else 0
        chosen_id = st.selectbox("Livro", sel_ids, format_func=lambda x: book_options[x],
            index=book_idx, label_visibility="collapsed")
        if chosen_id != current_bid:
            st.session_state["kindle_book_id"] = chosen_id
            st.session_state["kindle_chapter_idx"] = 0
            _settings_svc.save_kindle_position(chosen_id, 0)
            st.rerun()
    with col_theme:
        theme_key = st.selectbox("Tema", list(_THEMES.keys()), label_visibility="collapsed")
    with col_font:
        font_key = st.selectbox("Fonte", list(_FONTS.keys()), label_visibility="collapsed")
    with col_size:
        font_size = st.select_slider("Tamanho", [12,14,16,18,20,24], value=16, label_visibility="collapsed")

    bg_color, text_color, border_color = _THEMES[theme_key]
    font_family = _FONTS[font_key]

    book         = _book_svc.get_book(chosen_id)
    chapters_nav = _ch_svc.get_chapters_lightweight(chosen_id)

    if not chapters_nav:
        st.markdown('<div style="text-align:center;padding:4rem;color:#64748b"><div style="font-size:3rem">📭</div><h3 style="color:#94a3b8">Nenhum capítulo ainda</h3><p>Adicione capítulos na seção ✍️ Capítulos.</p></div>', unsafe_allow_html=True)
        return

    active_idx = min(int(current_idx), len(chapters_nav) - 1)
    st.session_state["kindle_book_id"]     = chosen_id
    st.session_state["kindle_chapter_idx"] = active_idx

    def _nav(book_id: int, new_idx: int):
        st.session_state["kindle_chapter_idx"] = new_idx
        _settings_svc.save_kindle_position(book_id, new_idx)
        st.rerun()

    col_prev, col_sel, col_next = st.columns([1, 6, 1])
    with col_prev:
        if st.button("◀", disabled=active_idx == 0, use_container_width=True):
            _nav(chosen_id, active_idx - 1)
    with col_sel:
        sel_idx = st.selectbox("Capítulo", range(len(chapters_nav)),
            format_func=lambda i: f"{i+1}. {chapters_nav[i]['title']}",
            index=active_idx, label_visibility="collapsed")
        if sel_idx != active_idx:
            _nav(chosen_id, sel_idx)
    with col_next:
        if st.button("▶", disabled=active_idx == len(chapters_nav) - 1, use_container_width=True):
            _nav(chosen_id, active_idx + 1)

    total_words = sum(c.get("word_count",0) for c in chapters_nav)
    words_read  = sum(chapters_nav[i].get("word_count",0) for i in range(active_idx + 1))
    progress    = int((active_idx + 1) / len(chapters_nav) * 100)

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem">
        <div style="flex:1;background:#1e1e3f;border-radius:4px;height:4px;overflow:hidden">
            <div style="width:{progress}%;height:4px;background:linear-gradient(90deg,#6366f1,#8b5cf6)"></div>
        </div>
        <div style="font-size:0.75rem;color:#64748b;white-space:nowrap">
            Cap {active_idx+1}/{len(chapters_nav)} · {words_read:,}/{total_words:,} palavras
        </div>
    </div>""", unsafe_allow_html=True)

    ch_id   = chapters_nav[active_idx]["id"]
    ch_nav  = chapters_nav[active_idx]
    ch_full = _ch_svc.get_chapter(ch_id)
    content = (ch_full or {}).get("content","") or ""

    cache_key = f"kindle_html_{ch_id}_{hash(content)}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = markdown2.markdown(
            content or "_Este capítulo está vazio._",
            extras=["fenced-code-blocks","tables","break-on-newline"],
        )
    html_content = st.session_state[cache_key]

    st.markdown(f"""
    <style>
    .kindle-reader {{ background:{bg_color};color:{text_color};font-family:{font_family};
        font-size:{font_size}px;line-height:1.9;max-width:680px;margin:0 auto;
        padding:3rem 2.5rem;border-radius:12px;border:1px solid {border_color};
        box-shadow:0 20px 60px rgba(0,0,0,0.4);min-height:60vh; }}
    .kindle-reader h1 {{ font-size:{font_size*1.8}px;margin-bottom:2rem;text-align:center;
        opacity:0.9;border-bottom:1px solid {border_color};padding-bottom:1rem; }}
    .kindle-reader h2,.kindle-reader h3 {{ font-size:{font_size*1.3}px;margin:2rem 0 1rem; }}
    .kindle-reader p {{ margin-bottom:1.2em;text-align:justify;text-indent:2em; }}
    .kindle-reader p:first-of-type {{ text-indent:0; }}
    .kindle-reader blockquote {{ border-left:3px solid {border_color};padding-left:1em;
        font-style:italic;opacity:0.8;margin:1em 0; }}
    .kindle-book-title {{ text-align:center;font-size:{font_size*0.8}px;color:{text_color}88;
        margin-bottom:0.5rem;letter-spacing:0.12em;text-transform:uppercase; }}
    </style>""", unsafe_allow_html=True)

    book_title = book["title"] if book else ""
    st.markdown(
        f"<div class='kindle-reader'>"
        f"<div class='kindle-book-title'>{book_title}</div>"
        f"<h1>{ch_nav['title']}</h1>"
        f"<div class='kindle-content'>{html_content}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns([1, 3, 1])
    with b1:
        if st.button("◀ Anterior", disabled=active_idx == 0, use_container_width=True, key="k_prev_bot"):
            _nav(chosen_id, active_idx - 1)
    with b2:
        st.markdown(f'<div style="text-align:center;color:#64748b;font-size:0.85rem;padding-top:0.6rem">{ch_nav["title"]} · {ch_nav.get("word_count",0):,} palavras</div>', unsafe_allow_html=True)
    with b3:
        if st.button("Próximo ▶", disabled=active_idx == len(chapters_nav)-1, use_container_width=True, key="k_next_bot"):
            _nav(chosen_id, active_idx + 1)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: CHARACTERS
# ═══════════════════════════════════════════════════════════════════════════════

def render_characters():
    _book_svc = BookService()
    _char_svc = CharacterService()

    section_header("👥 Personagens", "Gerencie os personagens dos seus livros")

    books = _book_svc.list_books_lightweight()
    if not books:
        st.info("📚 Crie um livro primeiro.")
        return

    book_options = {b["id"]: b["title"] for b in books}
    selected_id  = st.session_state.get("selected_book_id")
    sel_ids      = list(book_options.keys())
    default_idx  = sel_ids.index(selected_id) if selected_id in sel_ids else 0

    col_sel, col_search, col_btn = st.columns([3, 2, 1])
    with col_sel:
        chosen_id = st.selectbox("Livro", sel_ids, format_func=lambda x: book_options[x],
            index=default_idx, label_visibility="collapsed")
        st.session_state["selected_book_id"] = chosen_id
    with col_search:
        search_q = st.text_input("🔍", placeholder="Buscar personagem...", label_visibility="collapsed")
    with col_btn:
        if st.button("✚ Novo", use_container_width=True):
            st.session_state["show_new_char"] = True

    if st.session_state.get("show_new_char"):
        _render_char_form(chosen_id, None, _char_svc)

    chars = _char_svc.search(chosen_id, search_q) if search_q else _char_svc.get_characters(chosen_id)

    if not chars:
        st.markdown('<div style="text-align:center;padding:3rem;color:#64748b"><div style="font-size:3rem">👥</div><h3 style="color:#94a3b8">Nenhum personagem</h3><p>Crie personagens para popular seu universo!</p></div>', unsafe_allow_html=True)
        return

    COLS = 3
    for i in range(0, len(chars), COLS):
        row  = chars[i:i+COLS]
        cols = st.columns(COLS)
        for j, ch in enumerate(row):
            with cols[j]:
                _render_char_card(ch, chosen_id, _char_svc)


def _render_char_form(book_id: int, char, _char_svc):
    is_edit = char is not None
    char_id = char["id"] if is_edit else None
    with st.expander(f"{'✏️ Editar' if is_edit else '✚ Novo'} Personagem", expanded=True):
        with st.form(f"char_form_{char_id or 'new'}"):
            col1, col2 = st.columns([1, 2])
            with col1:
                photo_file = st.file_uploader("Foto", type=["jpg","jpeg","png","webp"])
                if is_edit and char.get("photo"):
                    st.markdown(f'<img src="{image_to_base64(char["photo"])}" style="width:100%;border-radius:8px">', unsafe_allow_html=True)
            with col2:
                name         = st.text_input("Nome *", value=char["name"] if is_edit else "")
                role         = st.selectbox("Papel", [""]+ROLES,
                    index=ROLES.index(char["role"])+1 if is_edit and char.get("role") in ROLES else 0)
                description  = st.text_area("Descrição", value=char.get("description","") if is_edit else "", height=100)
                relationships= st.text_area("Relacionamentos", value=char.get("relationships","") if is_edit else "", height=80,
                    placeholder="Ex: Irmão de João, rival de Maria...")
                notes        = st.text_area("Notas", value=char.get("notes","") if is_edit else "", height=80)

            col_s, col_c = st.columns(2)
            with col_s: submitted = st.form_submit_button("💾 Salvar", use_container_width=True)
            with col_c: cancelled = st.form_submit_button("❌ Cancelar", use_container_width=True)

            if cancelled:
                st.session_state.pop("show_new_char", None)
                st.session_state.pop(f"edit_char_{char_id}", None)
                st.rerun()
            if submitted:
                if not name.strip():
                    st.error("Nome é obrigatório.")
                else:
                    if is_edit:
                        _char_svc.update(char_id, name=name, role=role, description=description,
                            photo_file=photo_file, relationships=relationships, notes=notes)
                        st.session_state.pop(f"edit_char_{char_id}", None)
                    else:
                        _char_svc.create(book_id, name, role, description,
                            photo_file, relationships=relationships, notes=notes)
                        st.session_state.pop("show_new_char", None)
                    st.success("✅ Salvo!")
                    st.rerun()


def _render_char_card(char: dict, book_id: int, _char_svc):
    char_id = char["id"]
    if char.get("photo"):
        photo_html = f'<img src="{image_to_base64(char["photo"])}" style="width:80px;height:80px;object-fit:cover;border-radius:50%;border:2px solid #6366f1">'
    else:
        photo_html = '<div style="width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,#1e1b4b,#2d1b69);display:flex;align-items:center;justify-content:center;font-size:2rem;border:2px solid #2a2a4a">👤</div>'

    role_color = {"Protagonista":"#6366f1","Antagonista":"#ef4444","Vilão":"#ef4444",
                  "Mentor":"#f59e0b","Coadjuvante":"#06b6d4"}.get(char.get("role",""),"#64748b")

    st.markdown(f"""
    <div class="wf-card">
        <div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.75rem">
            {photo_html}
            <div>
                <div style="font-weight:700;color:#e2e8f0;font-size:1rem">{char['name']}</div>
                <div style="font-size:0.75rem;color:{role_color};font-weight:600">{char.get('role','')}</div>
            </div>
        </div>
        <div style="color:#94a3b8;font-size:0.85rem;line-height:1.5;margin-bottom:0.5rem">
            {(char.get('description','') or '')[:120]}{'...' if len(char.get('description','') or '') > 120 else ''}
        </div>
        {f'<div style="font-size:0.75rem;color:#64748b;border-top:1px solid #1e1e3f;padding-top:0.5rem;margin-top:0.5rem">🔗 {char["relationships"][:80]}</div>' if char.get("relationships") else ''}
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✏️ Editar", key=f"edit_char_{char_id}", use_container_width=True):
            st.session_state[f"edit_char_{char_id}"] = True
            st.rerun()
    with col2:
        if st.button("🗑️ Excluir", key=f"del_char_{char_id}", use_container_width=True):
            _char_svc.delete(char_id)
            st.rerun()

    if st.session_state.get(f"edit_char_{char_id}"):
        _render_char_form(book_id, char, _char_svc)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: WORLD BUILDING
# ═══════════════════════════════════════════════════════════════════════════════

def render_world():
    _book_svc  = BookService()
    _world_svc = WorldBuildingService()

    section_header("🌍 World Building", "Construa o universo dos seus livros")

    books = _book_svc.list_books_lightweight()
    if not books:
        st.info("📚 Crie um livro primeiro.")
        return

    book_options = {b["id"]: b["title"] for b in books}
    selected_id  = st.session_state.get("selected_book_id")
    sel_ids      = list(book_options.keys())
    default_idx  = sel_ids.index(selected_id) if selected_id in sel_ids else 0

    chosen_id = st.selectbox("Livro", sel_ids, format_func=lambda x: book_options[x],
        index=default_idx, label_visibility="collapsed")
    st.session_state["selected_book_id"] = chosen_id

    tab1, tab2, tab3 = st.tabs(["📍 Locais", "⚔️ Facções", "⏳ Cronologia"])

    with tab1:
        col_search, col_btn = st.columns([4, 1])
        with col_search:
            q = st.text_input("🔍", placeholder="Buscar locais...", key="loc_search", label_visibility="collapsed")
        with col_btn:
            if st.button("✚ Local", key="new_loc"):
                st.session_state["show_new_loc"] = True

        if st.session_state.get("show_new_loc"):
            with st.form("new_loc_form"):
                name  = st.text_input("Nome do local *")
                desc  = st.text_area("Descrição", height=100)
                notes = st.text_area("Notas", height=80)
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("💾 Criar", use_container_width=True):
                        if name.strip():
                            _world_svc.create_location(chosen_id, name, desc, notes)
                            st.session_state.pop("show_new_loc", None)
                            st.rerun()
                with c2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.pop("show_new_loc", None)
                        st.rerun()

        locations = _world_svc.search_locations(chosen_id, q) if q else _world_svc.get_locations(chosen_id)
        if not locations:
            st.markdown('<div style="text-align:center;padding:2rem;color:#64748b">📍 Nenhum local cadastrado</div>', unsafe_allow_html=True)
        else:
            for loc in locations:
                with st.expander(f"📍 {loc['name']}"):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        new_name  = st.text_input("Nome", value=loc["name"], key=f"loc_n_{loc['id']}")
                        new_desc  = st.text_area("Descrição", value=loc.get("description",""), key=f"loc_d_{loc['id']}", height=100)
                        new_notes = st.text_area("Notas", value=loc.get("notes",""), key=f"loc_nt_{loc['id']}", height=80)
                    with col2:
                        if st.button("💾", key=f"save_loc_{loc['id']}", use_container_width=True):
                            _world_svc.update_location(loc["id"], name=new_name, description=new_desc, notes=new_notes)
                            st.success("Salvo!")
                            st.rerun()
                        if st.button("🗑️", key=f"del_loc_{loc['id']}", use_container_width=True):
                            _world_svc.delete_location(loc["id"])
                            st.rerun()

    with tab2:
        col_btn = st.columns([5, 1])
        with col_btn[1]:
            if st.button("✚ Facção", key="new_fac"):
                st.session_state["show_new_fac"] = True

        if st.session_state.get("show_new_fac"):
            with st.form("new_fac_form"):
                name  = st.text_input("Nome da facção *")
                desc  = st.text_area("Descrição", height=100)
                notes = st.text_area("Notas", height=80)
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("💾 Criar", use_container_width=True):
                        if name.strip():
                            _world_svc.create_faction(chosen_id, name, desc, notes)
                            st.session_state.pop("show_new_fac", None)
                            st.rerun()
                with c2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.pop("show_new_fac", None)
                        st.rerun()

        factions = _world_svc.get_factions(chosen_id)
        if not factions:
            st.markdown('<div style="text-align:center;padding:2rem;color:#64748b">⚔️ Nenhuma facção cadastrada</div>', unsafe_allow_html=True)
        else:
            for fac in factions:
                with st.expander(f"⚔️ {fac['name']}"):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        new_name  = st.text_input("Nome", value=fac["name"], key=f"fac_n_{fac['id']}")
                        new_desc  = st.text_area("Descrição", value=fac.get("description",""), key=f"fac_d_{fac['id']}", height=100)
                        new_notes = st.text_area("Notas", value=fac.get("notes",""), key=f"fac_nt_{fac['id']}", height=80)
                    with col2:
                        if st.button("💾", key=f"save_fac_{fac['id']}", use_container_width=True):
                            _world_svc.update_faction(fac["id"], name=new_name, description=new_desc, notes=new_notes)
                            st.success("Salvo!")
                            st.rerun()
                        if st.button("🗑️", key=f"del_fac_{fac['id']}", use_container_width=True):
                            _world_svc.delete_faction(fac["id"])
                            st.rerun()

    with tab3:
        col_btn = st.columns([5, 1])
        with col_btn[1]:
            if st.button("✚ Evento", key="new_ev"):
                st.session_state["show_new_ev"] = True

        if st.session_state.get("show_new_ev"):
            with st.form("new_ev_form"):
                title      = st.text_input("Título do evento *")
                date_label = st.text_input("Data/Período", placeholder="Ex: Ano 432, Inverno de 1600...")
                desc       = st.text_area("Descrição", height=100)
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("💾 Criar", use_container_width=True):
                        if title.strip():
                            _world_svc.create_event(chosen_id, title, desc, date_label)
                            st.session_state.pop("show_new_ev", None)
                            st.rerun()
                with c2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.pop("show_new_ev", None)
                        st.rerun()

        events = _world_svc.get_events(chosen_id)
        if not events:
            st.markdown('<div style="text-align:center;padding:2rem;color:#64748b">⏳ Nenhum evento na cronologia</div>', unsafe_allow_html=True)
        else:
            for i, ev in enumerate(events):
                col_line, col_content = st.columns([1, 8])
                with col_line:
                    st.markdown(f'<div style="display:flex;flex-direction:column;align-items:center;height:100%"><div style="width:12px;height:12px;border-radius:50%;background:#6366f1;margin-top:0.5rem"></div>{"<div style=width:2px;flex:1;background:#1e1e3f;margin:0 auto></div>" if i < len(events)-1 else ""}</div>', unsafe_allow_html=True)
                with col_content:
                    with st.expander(f"{'⏳' if i==0 else '📅'} {ev.get('date_label','') + ' — ' if ev.get('date_label') else ''}{ev['title']}"):
                        new_title = st.text_input("Título", value=ev["title"], key=f"ev_t_{ev['id']}")
                        new_date  = st.text_input("Data/Período", value=ev.get("date_label",""), key=f"ev_d_{ev['id']}")
                        new_desc  = st.text_area("Descrição", value=ev.get("description",""), key=f"ev_desc_{ev['id']}", height=80)
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("💾 Salvar", key=f"save_ev_{ev['id']}", use_container_width=True):
                                _world_svc.update_event(ev["id"], title=new_title, description=new_desc, date_label=new_date)
                                st.success("Salvo!")
                                st.rerun()
                        with col2:
                            if st.button("🗑️ Excluir", key=f"del_ev_{ev['id']}", use_container_width=True):
                                _world_svc.delete_event(ev["id"])
                                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: BRAIN DUMP
# ═══════════════════════════════════════════════════════════════════════════════

def render_brain_dump():
    _book_svc  = BookService()
    _brain_svc = BrainDumpService()

    section_header("🧠 Brain Dump", "Capture ideias antes que se percam")

    col_search, col_tag, col_book_filter, col_btn = st.columns([3, 2, 2, 1])
    with col_search:
        search_q = st.text_input("🔍", placeholder="Buscar ideias...", label_visibility="collapsed")
    with col_tag:
        all_tags   = _brain_svc.get_all_tags()
        tag_filter = st.selectbox("Tag", ["Todas"]+all_tags, label_visibility="collapsed")
    with col_book_filter:
        books      = _book_svc.list_books_lightweight()
        book_opts  = {None: "Todos os livros"}
        book_opts.update({b["id"]: b["title"] for b in books})
        book_filter = st.selectbox("Livro", list(book_opts.keys()),
            format_func=lambda x: book_opts[x], label_visibility="collapsed")
    with col_btn:
        if st.button("✚ Ideia", use_container_width=True):
            st.session_state["show_new_dump"] = True

    if st.session_state.get("show_new_dump"):
        with st.form("new_dump_form"):
            st.markdown("### 💡 Nova Ideia")
            content = st.text_area("Conteúdo *", height=150,
                placeholder="Capture sua ideia aqui... pode ser qualquer coisa!",
                label_visibility="collapsed")
            col1, col2 = st.columns(2)
            with col1:
                tags_input = st.text_input("Tags (separadas por vírgula)",
                    placeholder="ex: magia, conflito, revisar")
                link_book  = st.selectbox("Vincular a livro (opcional)",
                    [None]+[b["id"] for b in books],
                    format_func=lambda x: "Sem vínculo" if x is None else book_opts.get(x,""))
            with col2:
                st.markdown('<div class="wf-info" style="margin-top:1.5rem">💡 <strong>Dica:</strong> Use tags para organizar. Ex: #plot, #personagem, #revisar</div>', unsafe_allow_html=True)
            cs, cc = st.columns(2)
            with cs:
                if st.form_submit_button("💾 Salvar Ideia", use_container_width=True):
                    if content.strip():
                        tags_clean = ", ".join(t.strip() for t in tags_input.split(",") if t.strip())
                        _brain_svc.create(content, link_book, tags_clean)
                        st.session_state.pop("show_new_dump", None)
                        st.success("✅ Ideia salva!")
                        st.rerun()
                    else:
                        st.error("O conteúdo não pode estar vazio.")
            with cc:
                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                    st.session_state.pop("show_new_dump", None)
                    st.rerun()

    tag_f = None if tag_filter == "Todas" else tag_filter
    dumps = _brain_svc.list(search_q, book_filter, tag_f)

    if not dumps:
        st.markdown('<div style="text-align:center;padding:3rem;color:#64748b"><div style="font-size:3rem">🧠</div><h3 style="color:#94a3b8">Nenhuma ideia encontrada</h3><p>Capture sua próxima grande ideia!</p></div>', unsafe_allow_html=True)
        return

    st.markdown(f"<div style='color:#64748b;font-size:0.85rem;margin-bottom:1rem'>{len(dumps)} ideia(s) encontrada(s)</div>", unsafe_allow_html=True)

    for dump in dumps:
        dump_id  = dump["id"]
        tags     = [t.strip() for t in dump.get("tags","").split(",") if t.strip()]
        tags_html = " ".join(
            f'<span style="background:#1e1b4b;color:#a5b4fc;padding:2px 8px;border-radius:12px;font-size:0.72rem">{t}</span>'
            for t in tags
        )
        linked_book = ""
        if dump.get("book_id"):
            for b in books:
                if b["id"] == dump["book_id"]:
                    linked_book = f'<span style="color:#06b6d4;font-size:0.75rem">📚 {b["title"]}</span>'
                    break
        preview  = dump["content"][:300] + ("..." if len(dump["content"]) > 300 else "")
        edit_key = f"edit_dump_{dump_id}"

        if st.session_state.get(edit_key):
            with st.form(f"edit_form_{dump_id}"):
                st.markdown("**✏️ Editando ideia**")
                new_content = st.text_area("Conteúdo", value=dump["content"], height=150, label_visibility="collapsed")
                new_tags    = st.text_input("Tags", value=dump.get("tags",""))
                c1, c2, c3  = st.columns(3)
                with c1:
                    if st.form_submit_button("💾 Salvar"):
                        _brain_svc.update(dump_id, new_content, new_tags)
                        st.session_state.pop(edit_key, None)
                        st.rerun()
                with c2:
                    if st.form_submit_button("❌ Cancelar"):
                        st.session_state.pop(edit_key, None)
                        st.rerun()
                with c3:
                    if st.form_submit_button("🗑️ Excluir"):
                        _brain_svc.delete(dump_id)
                        st.rerun()
        else:
            st.markdown(f"""
            <div class="wf-card" style="margin-bottom:0.75rem">
                <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem">
                    <div>{tags_html}</div>
                    <div style="display:flex;gap:0.5rem;align-items:center">
                        {linked_book}
                        <span style="font-size:0.72rem;color:#64748b">{dump.get('created_at','')[:10]}</span>
                    </div>
                </div>
                <div style="color:#d1d5db;line-height:1.7;font-size:0.9rem">{preview.replace(chr(10), '<br>')}</div>
            </div>""", unsafe_allow_html=True)
            col1, col2 = st.columns([1, 6])
            with col1:
                if st.button("✏️ Editar", key=f"edit_btn_{dump_id}"):
                    st.session_state[edit_key] = True
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def render_export():
    _book_svc = BookService()

    section_header("📤 Exportar", "Exporte seus livros em diferentes formatos")

    books = _book_svc.list_books_lightweight()
    if not books:
        st.info("📚 Crie e escreva um livro primeiro.")
        return

    book_options = {b["id"]: b["title"] for b in books}
    selected_id  = st.session_state.get("selected_book_id")
    sel_ids      = list(book_options.keys())
    default_idx  = sel_ids.index(selected_id) if selected_id in sel_ids else 0

    chosen_id = st.selectbox("Selecionar livro", sel_ids,
        format_func=lambda x: book_options[x], index=default_idx)

    book = _book_svc.get_book(chosen_id)
    wc   = book.get("word_count", 0)

    st.markdown(f"""
    <div class="wf-card" style="margin:1rem 0">
        <div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;margin-bottom:0.5rem">{book['title']}</div>
        <div style="color:#64748b;font-size:0.85rem">{book.get('genre','')} · {wc:,} palavras · Status: {book.get('status','')}</div>
        {f'<div style="color:#94a3b8;font-size:0.85rem;margin-top:0.5rem">{(book.get("synopsis","") or "")[:200]}</div>' if book.get('synopsis') else ''}
    </div>""", unsafe_allow_html=True)

    if wc == 0:
        st.warning("⚠️ Este livro ainda não tem conteúdo. Escreva alguns capítulos primeiro.")

    st.markdown("### Formatos de Exportação")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown('<div class="wf-card"><div style="text-align:center;padding:1rem"><div style="font-size:3rem;margin-bottom:0.5rem">📄</div><div style="font-weight:700;color:#e2e8f0;font-size:1.1rem">PDF</div><div style="color:#64748b;font-size:0.8rem;margin-top:0.25rem">Documento formatado<br>para impressão e leitura</div></div></div>', unsafe_allow_html=True)
        if st.button("⬇ Exportar PDF", key="exp_pdf", use_container_width=True):
            with st.spinner("Gerando PDF..."):
                try:
                    pdf_bytes = export_to_pdf(chosen_id)
                    fname = f"{book['title'].replace(' ','_')}.pdf"
                    st.download_button("📥 Baixar PDF", data=pdf_bytes,
                        file_name=fname, mime="application/pdf", use_container_width=True)
                    st.success("✅ PDF gerado!")
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}")

    with col2:
        st.markdown('<div class="wf-card"><div style="text-align:center;padding:1rem"><div style="font-size:3rem;margin-bottom:0.5rem">📝</div><div style="font-weight:700;color:#e2e8f0;font-size:1.1rem">DOCX</div><div style="color:#64748b;font-size:0.8rem;margin-top:0.25rem">Microsoft Word<br>para edição adicional</div></div></div>', unsafe_allow_html=True)
        if st.button("⬇ Exportar DOCX", key="exp_docx", use_container_width=True):
            with st.spinner("Gerando DOCX..."):
                try:
                    docx_bytes = export_to_docx(chosen_id)
                    fname = f"{book['title'].replace(' ','_')}.docx"
                    st.download_button("📥 Baixar DOCX", data=docx_bytes, file_name=fname,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True)
                    st.success("✅ DOCX gerado!")
                except Exception as e:
                    st.error(f"Erro ao gerar DOCX: {e}")

    with col3:
        st.markdown('<div class="wf-card"><div style="text-align:center;padding:1rem"><div style="font-size:3rem;margin-bottom:0.5rem">📱</div><div style="font-weight:700;color:#e2e8f0;font-size:1.1rem">EPUB</div><div style="color:#64748b;font-size:0.8rem;margin-top:0.25rem">E-reader universal<br>Kindle, Kobo, etc.</div></div></div>', unsafe_allow_html=True)
        if st.button("⬇ Exportar EPUB", key="exp_epub", use_container_width=True):
            with st.spinner("Gerando EPUB..."):
                try:
                    epub_bytes = export_to_epub(chosen_id)
                    fname = f"{book['title'].replace(' ','_')}.epub"
                    st.download_button("📥 Baixar EPUB", data=epub_bytes,
                        file_name=fname, mime="application/epub+zip", use_container_width=True)
                    st.success("✅ EPUB gerado!")
                except Exception as e:
                    st.error(f"Erro ao gerar EPUB: {e}")

    st.markdown('<div class="wf-info" style="margin-top:2rem">ℹ️ <strong>Dica:</strong> O PDF é ideal para impressão. O DOCX permite edições no Word. O EPUB é perfeito para e-readers.</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

PAGES = {
    "📊 Dashboard":      render_dashboard,
    "📚 Biblioteca":     render_library,
    "✍️ Capítulos":      render_chapters,
    "📖 Modo Kindle":    render_kindle,
    "👥 Personagens":    render_characters,
    "🌍 World Building": render_world,
    "🧠 Brain Dump":     render_brain_dump,
    "📤 Exportar":       render_export,
}
PAGE_KEYS = list(PAGES.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# ONBOARDING GATE
# ═══════════════════════════════════════════════════════════════════════════════

if should_show_onboarding():
    with st.sidebar:
        st.markdown("""
        <div style="padding:1.5rem 0 1rem">
            <div style="font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:700;
                        background:linear-gradient(135deg,#c084fc,#818cf8);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent">
                Kindle_Plus - By Miiihl</div>
            <div style="color:#64748b;font-size:0.75rem;text-transform:uppercase;
                        letter-spacing:0.1em">Plataforma para Escritores</div>
        </div>""", unsafe_allow_html=True)
    render_onboarding()
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div style="padding:1.5rem 0 1rem">
        <div style="font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:700;
                    background:linear-gradient(135deg,#c084fc,#818cf8);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                    letter-spacing:-0.03em">Kindle_Plus - By Miiihl</div>
        <div style="color:#64748b;font-size:0.75rem;letter-spacing:0.1em;
                    text-transform:uppercase;margin-top:-2px">Plataforma para Escritores</div>
    </div>""", unsafe_allow_html=True)
    st.markdown('<div class="wf-divider"></div>', unsafe_allow_html=True)

    current_page = st.session_state.get("current_page", PAGE_KEYS[0])
    if current_page not in PAGE_KEYS:
        current_page = PAGE_KEYS[0]

    for page_name in PAGE_KEYS:
        is_active = page_name == current_page
        if st.button(page_name, key=f"nav_{page_name}", use_container_width=True,
                     type="primary" if is_active else "secondary"):
            st.session_state["current_page"] = page_name
            st.rerun()

    st.markdown('<div class="wf-divider"></div>', unsafe_allow_html=True)

    try:
        _s = BookService().get_stats()
        st.markdown(f"""
        <div style="padding:0.75rem;background:#0d0d1a;border-radius:8px;border:1px solid #1e1e3f">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem">
                <div style="text-align:center">
                    <div style="color:#c084fc;font-weight:700;font-size:1.1rem">{_s['total_books']}</div>
                    <div style="color:#64748b;font-size:0.65rem;text-transform:uppercase">Livros</div>
                </div>
                <div style="text-align:center">
                    <div style="color:#06b6d4;font-weight:700;font-size:1.1rem">{_s['total_chapters']}</div>
                    <div style="color:#64748b;font-size:0.65rem;text-transform:uppercase">Capítulos</div>
                </div>
            </div>
            <div style="text-align:center;margin-top:0.5rem">
                <div style="color:#10b981;font-weight:700">{_s['total_words']:,}</div>
                <div style="color:#64748b;font-size:0.65rem;text-transform:uppercase">Palavras Totais</div>
            </div>
        </div>""", unsafe_allow_html=True)
    except Exception:
        pass

    sel_bid = st.session_state.get("selected_book_id")
    if sel_bid:
        try:
            _ab = BookService().get_book(sel_bid)
            if _ab:
                st.markdown(f"""
                <div style="margin-top:0.75rem;padding:0.5rem 0.75rem;
                            background:#1e1b4b;border-radius:6px;border-left:3px solid #6366f1">
                    <div style="font-size:0.65rem;color:#818cf8;text-transform:uppercase">Livro ativo</div>
                    <div style="font-size:0.8rem;color:#e2e8f0;font-weight:500;
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
                         title="{_ab['title']}">{_ab['title']}</div>
                </div>""", unsafe_allow_html=True)
        except Exception:
            pass

    st.markdown('<div style="position:fixed;bottom:1rem;left:0;right:0;text-align:center;color:#2a2a4a;font-size:0.7rem">Kindle_Plus - By Miiihl v2.0</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

page = st.session_state.get("current_page", PAGE_KEYS[0])
if page not in PAGES:
    page = PAGE_KEYS[0]
PAGES[page]()
