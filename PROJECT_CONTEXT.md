# WriterFlow — PROJECT_CONTEXT.md

## Visão Geral

WriterFlow é uma plataforma de escrita profissional construída com **Streamlit** e **SQLite**.
Permite gerenciar livros, capítulos, personagens, world building, notas e exportação para DOCX/PDF/EPUB.

---

## Estrutura de Arquivos (arquitetura simplificada)

```
writerflow/
├── app.py                  # Entrada principal + todas as páginas + helpers visuais
├── database.py             # Conexão, schema, repositories e services
├── export.py               # Geração de DOCX, PDF e EPUB
├── utils.py                # Utilitários de texto (count_words, strip_markdown)
├── styles/
│   ├── __init__.py
│   └── main_css.py         # CSS global + STATUS_CONFIG + GENRE_OPTIONS
├── requirements.txt
└── PROJECT_CONTEXT.md
```

Para rodar:
```bash
streamlit run app.py
```

---

## app.py

**Responsabilidades:**
- Configuração do Streamlit (`set_page_config`)
- Inicialização do banco (`initialize_database`)
- Injeção do CSS global
- Helpers visuais de UI: `status_badge`, `progress_bar_html`, `stat_card`, `section_header`, `confirm_delete`
- Onboarding: `should_show_onboarding`, `render_onboarding`
- Todas as páginas: `render_dashboard`, `render_library`, `render_chapters`, `render_kindle`, `render_characters`, `render_world`, `render_brain_dump`, `render_export`
- Sidebar com navegação, stats e livro ativo
- Roteamento de páginas via `PAGES` dict + `st.session_state["current_page"]`

**Imports externos:**
```python
from database import initialize_database, BookService, ChapterService,
                     CharacterService, WorldBuildingService, BrainDumpService,
                     DashboardService, SettingsService, image_to_base64
from export import export_to_docx, export_to_pdf, export_to_epub
from styles.main_css import GLOBAL_CSS, STATUS_CONFIG, GENRE_OPTIONS, STATUS_OPTIONS
from utils import count_words
```

---

## database.py

Arquivo central do backend. Contém cinco seções:

### 1. Conexão & Schema
| Símbolo | Descrição |
|---|---|
| `DB_PATH` | Caminho do SQLite (env `WRITERFLOW_DB` → `/tmp/writerflow.db` → `writerflow.db`) |
| `ALLOWED_TABLES` | Frozenset com tabelas permitidas (proteção contra injeção de tabela) |
| `get_connection()` | Context manager thread-safe com WAL mode, foreign keys ON e auto-commit/rollback |
| `initialize_database()` | Cria tabelas, roda migrações de colunas, cria índices (ordem crítica) |
| `_add_column_if_missing()` | ALTER TABLE idempotente para migrações de schema |

**Tabelas:**
`books`, `chapters`, `characters`, `locations`, `factions`, `timeline_events`, `brain_dumps`, `goals`, `writing_sessions`, `app_settings`

Todas as tabelas de conteúdo têm `deleted_at TIMESTAMP` para soft delete.

### 2. BaseRepository (ABC)
Classe base herdada por todos os repositories.

| Método | Descrição |
|---|---|
| `find_by_id(id)` | Retorna registro ativo por PK |
| `find_all(order_by)` | Retorna todos os registros ativos |
| `soft_delete(id)` | Marca `deleted_at = CURRENT_TIMESTAMP` |
| `restore(id)` | Limpa `deleted_at` (restaura da lixeira) |
| `find_deleted()` | Retorna registros soft-deletados |
| `delete(id)` | Hard delete permanente |
| `_build_update_query(id, data)` | Helper para UPDATE dinâmico com allowlist |

### 3. Repositories

| Classe | Tabela | Métodos notáveis |
|---|---|---|
| `BookRepository` | `books` | `create`, `update`, `search`, `list_lightweight`, `get_all_genres`, `recalculate_word_count`, `get_stats`, `get_deleted_books` |
| `ChapterRepository` | `chapters` | `create` (BEGIN IMMEDIATE), `find_by_book`, `find_by_book_lightweight`, `find_deleted_by_book`, `update_content`, `get_word_count`, `update`, `reorder`, `get_total_words_for_book` |
| `CharacterRepository` | `characters` | `create`, `find_by_book`, `update`, `search` |
| `LocationRepository` | `locations` | `create`, `find_by_book`, `update`, `search` |
| `FactionRepository` | `factions` | `create`, `find_by_book`, `update` |
| `TimelineRepository` | `timeline_events` | `create` (BEGIN IMMEDIATE), `find_by_book`, `update` |
| `BrainDumpRepository` | `brain_dumps` | `create`, `find_all_with_filter`, `update`, `get_all_tags` |
| `GoalRepository` | `goals` | `insert`, `deactivate_by_period`, `get_active_goals` |
| `WritingSessionRepository` | `writing_sessions` | `log_session`, `get_words_today`, `get_words_this_month`, `get_daily_words_last_30_days` |
| `SettingsRepository` | `app_settings` | `get(key, default)`, `set(key, value)` — key-value store, não herda BaseRepository |

### 4. Utilitários de Imagem
| Função | Descrição |
|---|---|
| `process_image(file, max_size)` | Redimensiona e comprime para JPEG via Pillow |
| `image_to_base64(bytes)` | Converte bytes para data URI `data:image/jpeg;base64,...` |

### 5. Services (orquestração / business logic)

Singletons de repository no nível de módulo (`_book_repo`, `_chapter_repo`, etc.) compartilhados entre todos os services — são stateless, seguro para compartilhar.

| Classe | Responsabilidade |
|---|---|
| `BookService` | CRUD de livros, soft/hard delete, refresh de word count |
| `ChapterService` | CRUD de capítulos, `save_content` (delta de palavras → log de sessão), reordenação, soft/hard delete |
| `CharacterService` | CRUD de personagens com upload de foto |
| `WorldBuildingService` | Locais, facções e eventos de timeline |
| `BrainDumpService` | Notas livres com tags e filtros |
| `DashboardService` | Agrega stats, metas e dados de progresso diário/mensal |
| `SettingsService` | Key-value genérico + helpers tipados para posição Kindle (`get_kindle_position`, `save_kindle_position`) |

---

## export.py

Geração de arquivos a partir dos dados do livro. Importa `BookService` e `ChapterService` de `database.py`.

| Função | Formato | Detalhes |
|---|---|---|
| `export_to_docx(book_id)` | `.docx` | Capa, página de título, sinopse, sumário manual, capítulos com `page_break` |
| `export_to_pdf(book_id)` | `.pdf` | ReportLab com estilos customizados, numeração de página, capa, sumário, TOC |
| `export_to_epub(book_id)` | `.epub` | ebooklib + markdown2, CSS embutido, capa, spine completo com NAV |

Todas as funções usam `strip_markdown()` de `utils.py` para limpar o conteúdo antes de exportar.

---

## utils.py

Utilitários de texto puros (sem dependência de DB).

| Função | Descrição |
|---|---|
| `strip_markdown(text)` | Remove toda sintaxe Markdown, retorna texto plano |
| `count_words(text)` | Conta palavras reais ignorando markup Markdown |

Padrões regex pré-compilados para performance em documentos grandes.

---

## styles/main_css.py

| Símbolo | Tipo | Descrição |
|---|---|---|
| `GLOBAL_CSS` | `str` | String HTML com `<style>` completo para injetar via `st.markdown` |
| `STATUS_CONFIG` | `dict` | Mapeamento status → `{color, icon, bg}` |
| `GENRE_OPTIONS` | `list[str]` | Lista de gêneros literários disponíveis |
| `STATUS_OPTIONS` | `list[str]` | Lista de status de livros (`list(STATUS_CONFIG.keys())`) |

---

## Fluxo de Dados

```
app.py (página)
    │
    ├── chama Service (database.py)
    │       │
    │       └── chama Repository (database.py)
    │               │
    │               └── get_connection() → SQLite
    │
    ├── chama export_to_*(book_id) (export.py)
    │       │
    │       └── chama BookService / ChapterService (database.py)
    │
    └── usa count_words / strip_markdown (utils.py)
```

---

## Session State (Streamlit)

| Chave | Tipo | Descrição |
|---|---|---|
| `current_page` | `str` | Nome da página ativa (chave do dict `PAGES`) |
| `selected_book_id` | `int` | ID do livro selecionado globalmente |
| `selected_chapter_id` | `int` | ID do capítulo aberto no editor |
| `onboarding_complete` | `bool` | Flag em memória para evitar re-checar settings |
| `editing_book_id` | `int` | ID do livro com formulário de edição aberto |
| `adding_chapter` | `bool` | Controla exibição do form de novo capítulo |
| `adding_char` | `bool` | Controla exibição do form de novo personagem |
| `kindle_theme` | `str` | Tema do modo Kindle (`dark`/`sepia`/`light`) |
| `kindle_ch_idx` | `int` | Índice do capítulo atual no modo Kindle |

---

## Soft Delete

Todas as tabelas de conteúdo implementam soft delete via coluna `deleted_at TIMESTAMP`.

- **Excluir**: `soft_delete(id)` → seta `deleted_at = CURRENT_TIMESTAMP`
- **Restaurar**: `restore(id)` → seta `deleted_at = NULL`
- **Apagar permanentemente**: `delete(id)` → `DELETE FROM`
- **Queries normais**: sempre filtram `WHERE deleted_at IS NULL`
- **Lixeira**: `find_deleted()` / `get_deleted_books()` → `WHERE deleted_at IS NOT NULL`

---

## Migração para PostgreSQL

1. Substituir `get_connection()` por pool psycopg2/asyncpg
2. Trocar `?` por `%s` nos placeholders
3. Substituir `DATE('now')` por `CURRENT_DATE`
4. Remover cláusulas `WHERE` em índices parciais (ou usar views filtradas)
5. `ALLOWED_TABLES`, repositories e services permanecem inalterados

---

## Requirements

```
streamlit>=1.32.0
plotly>=5.20.0
pandas>=2.0.0
Pillow>=10.0.0
python-docx>=1.1.0
reportlab>=4.1.0
markdown2>=2.4.12
ebooklib>=0.18
```
