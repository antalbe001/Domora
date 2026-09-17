# Design: chatbot annunci immobiliari

Documento di design condiviso, prodotto tramite un ciclo di grilling (interrogazione
strutturata delle decisioni). Fissa le decisioni prese e il perché, prima
dell'implementazione. Data: 2026-09-16.

## Obiettivo

Un sito con un chatbot per un'agenzia immobiliare che
permette ai clienti di interrogare in linguaggio naturale gli annunci
disponibili (es. "trilocale sotto i 150k con box"), con dati in
un formato standardizzato e un backend organizzato secondo design pattern e
single responsibility.

## Prodotto

- **Sito solo-chatbot**: una pagina di chat, niente pagine di annunci
  tradizionali (griglia/filtri a form) nell'MVP. I risultati sono card
  cliccabili che linkano all'annuncio originale su salamonimmobiliare.com.
  *Perché*: lo scope del chatbot è già limitato alla ricerca annunci; un
  sito a doppio binario raddoppierebbe il lavoro frontend senza che sia
  stato richiesto esplicitamente. Le pagine tradizionali restano
  un'estensione naturale per dopo.
- **Pubblico**: clienti finali dell'agenzia, sito pubblico (non uno
  strumento interno per gli agenti). Nessuna autenticazione utente
  nell'MVP.
- **Ambito del chatbot in fase 1**: solo ricerca/Q&A sugli annunci. Fuori
  scope: info generiche sull'agenzia, lead capture/prenotazione visite
  (estensioni naturali per un secondo giro).
- **Lingua**: il chatbot risponde nella lingua in cui scrive l'utente
  (default italiano), gestito nel system prompt — nessun livello i18n
  dedicato.

## Dati

### Schema canonico

Un modello `Listing` in Pydantic è l'unica fonte di verità del contratto
dati, usato sia dallo scraper (valida in output) sia dal backend (valida in
input). Sostituisce il dizionario `features` libero attuale: dall'analisi
del dataset (`annunci.json`, 98 annunci) sono emerse solo **8 chiavi
chiuse** in `features`, quindi vengono promosse a campi tipizzati:

- `garden: bool | None`
- `cellar: bool | None`
- `terraces: int | None`
- `parking_spaces: int | None` + `parking_type: ParkingType | None`
  (enum: none/open/covered/double/condominial — derivato da valori misti
  numero/testo tipo "0", "Doppio", "Posto auto scoperto")
- `kitchen: KitchenType` (enum: separata/open space/angolo cottura)
- `area_type: AreaType` (enum: centrale/periferia/semicentrale)
- `furnished: FurnishedStatus` (enum: sì/no/parzialmente)
- `raw_features: dict[str, str]` residuo, solo per chiavi non mappate
  (estensibilità futura, es. altra fonte/agenzia)

### Normalizzazioni necessarie

- **Località**: `city`, `province`, `address` sono `null` su **tutti** i 98
  record nell'export attuale; l'unica geo-informazione è dentro
  `features.posizione` (es. `"Via Carlo Goldoni 16 - PORDENONE"`, 96/98
  record regolari, 2 eccezioni senza via). Un `LocationNormalizer` fa
  parsing di `posizione`, popola i campi canonici, mappa il comune alla
  provincia con una tabella statica (zona di Pordenone, ~23 comuni).
- **`energy_class` / `heating`**: enum opzionali. `"In fase di redazione"`
  (32/98 record) è un placeholder, non un valore → mappato a `None` in
  normalizzazione. `heating` è `null` nel 59% dei casi, filtro poco
  significativo di suo ma resta disponibile.
- **`floor`**: misto int (1,2,3…) e stringhe ("terra", "rialzato", "5
  oltre"). Due campi: `floor_label: str` per la visualizzazione,
  `floor_level: int | None` derivato per ordinamento/filtro (terra=0,
  rialzato=0, "5 oltre"=5).
- **`year_built`**: validator con range largo (1000–2035) per scartare solo
  garbage reale, senza toccare outlier plausibili osservati nel dataset
  (700 = villa storica, 2027 = nuova costruzione).
- **`price_eur` per affitti**: 3 capannoni su 29 affitti hanno canoni
  implausibili da mensile (4.500/24.000/24.000€), probabile confusione
  mensile/annuo nello scraper sorgente. **Non modellato nello schema**
  (niente `price_period`): annotato come bug da verificare in un secondo
  momento sullo scraper, riguarda 3 record su 98.
- **Immagini**: lo scraper attuale non cattura foto. Va esteso per
  catturare almeno l'immagine di copertina (`image_url`, URL esterno,
  nessun hosting nostro) — un chatbot immobiliare senza foto nei risultati
  è poco utile.

## Motore di comprensione del linguaggio naturale

**LLM con tool/function calling su un filtro deterministico**, non RAG/
embeddings: con 98 annunci e campi già normalizzati il retrieval semantico
è overkill e impreciso sui confronti numerici (prezzo, mq). Claude riceve
la domanda, emette parametri strutturati tramite un tool, il backend
filtra in modo deterministico, Claude sintetizza il risultato.

- **Provider**: Anthropic Claude, dietro un'interfaccia `ChatModel`
  (provider sostituibile). Modello default `claude-haiku-4-5`
  (costo/latenza, compito ristretto), configurabile via env var per salire
  a `claude-sonnet-5` se la qualità non basta su richieste ambigue.
- **`SearchCriteria`**: oggetto Pydantic condiviso fra tool LLM, service e
  repository — un campo opzionale per ciascun criterio filtrabile
  (transazione, città, provincia, prezzo min/max, tipologia, superficie
  min, camere min, bagni min, classe energetica, ecc.) più
  `keywords: list[str]` come fallback per richieste qualitative non
  coperte da campi strutturati ("ristrutturato", "luminoso"), match per
  sostringa case-insensitive su titolo/descrizione/raw_features.
- **Grounding**: dopo il filtro, si iniettano nel contesto solo gli
  annunci risultanti (cap ~15, campi essenziali), con system prompt che
  vincola Claude a rispondere esclusivamente su quelli, citando
  `reference`/URL — mai dati fuori dai risultati del tool. Un secondo tool
  `get_listing_detail(reference)` copre i follow-up di approfondimento.
- **Zero risultati / richiesta vaga**: su zero risultati Claude propone di
  allentare un criterio e rilancia il tool con criteri rilassati; su
  richiesta senza criteri filtrabili fa una domanda di chiarimento invece
  di eseguire il filtro a vuoto.
- **Guardrail anti prompt-injection/abuso**: system prompt con rifiuto
  esplicito di richieste fuori tema (non immobiliari) e divieto di
  rivelare il prompt/dettagli tecnici interni; input utente cappato a
  ~500 caratteri (validato da Pydantic sulla request).

## Backend (FastAPI, Python 3.12, gestito con uv)

Architettura a livelli, ciascuno con una singola responsabilità:

```
app/domain          Listing, SearchCriteria, enum — puro, zero dipendenze
app/normalization    LocationNormalizer, FeatureNormalizer
app/repositories     interfaccia ListingRepository + implementazione in-memory
app/services         SearchService, ChatService (orchestrazione LLM)
app/llm              interfaccia ChatModel + implementazione Anthropic, tool schema
app/api              router FastAPI
```

Dependency injection tramite `Depends` di FastAPI con un composition root
in `dependencies.py` — niente container DI dedicato (over-engineering per
questa scala).

- **Persistenza**: repository in-memory dietro interfaccia, popolato da
  `annunci.json` all'avvio. 98 record e filtri semplici non giustificano
  SQLite/Postgres ora; l'interfaccia rende l'implementazione sostituibile
  se il volume cresce.
- **Aggiornamento dati**: `POST /admin/reload` (bearer token statico da
  env var) ricarica il file; anche ricarica automatica all'avvio.
- **Sessioni/conversazione**: multi-turn con memoria — `session_id` (UUID)
  generato dal frontend e salvato in `localStorage`, storia tenuta in un
  `ConversationStore` in memoria (interfaccia sostituibile con Redis se
  servisse multi-processo), TTL 60 minuti di inattività, max ~20 turni
  tenuti. Nessuna persistenza delle conversazioni su disco (nessun tema di
  privacy/GDPR aggiuntivo).
- **Streaming**: SSE (`StreamingResponse`) per la sintesi finale del testo;
  la fase di tool-use (filtro) non è streammabile — il frontend mostra
  "sto cercando...".
- **Rate limiting**: 10 messaggi/minuto per sessione (token bucket in
  memoria), necessario perché ogni messaggio chiama l'API Anthropic a
  pagamento su un sito pubblico.
- **Errori Anthropic**: 1 retry con backoff, poi messaggio d'errore chiaro
  in chat (mai un 500 grezzo), loggato lato server.
- **CORS**: ristretto all'origin del frontend in dev (`localhost:5173`),
  configurabile via env.
- **Config/secrets**: `.env` + `pydantic-settings`, mai committati.

## Frontend (React + Vite + TypeScript + Tailwind)

Una pagina di chat: lista messaggi, input, indicatore "sta pensando/
cercando", risultati come card (titolo, prezzo, città, mq, camere, link
"vedi annuncio" verso il sito originale). Nessuna component library
pesante, stato locale/context, niente Redux.

## Testing

TDD sul backend: `Listing`, `SearchCriteria`, `LocationNormalizer`,
repository, `ChatService` con un `ChatModel` finto — nessuna chiamata reale
ad Anthropic nei test. Frontend: test leggeri con Vitest sui componenti
chiave.

## Repo & deploy

- **Monorepo**: `scraper/`, `backend/`, `frontend/`. Il modello `Listing`
  vive nel backend ed è importato dallo scraper (entrambi Python).
- **Deploy**: solo locale per ora, via `docker-compose` (Dockerfile per
  ciascun servizio). Il target cloud si decide quando c'è qualcosa da
  ospitare.
- **Automazione scraping**: manuale per l'MVP — uno script
  `scraper/run_and_reload.sh` che fa scrape + chiama `/admin/reload`,
  lanciato a mano. Costruire uno scheduler ora è prematuro senza sapere la
  frequenza di aggiornamento desiderata dall'agenzia; lo script rende
  comunque banale collegarlo a un cron di sistema più avanti.

## Prossimi passi

1. TDD sul livello `domain` (`Listing`, enum) e `normalization`
   (`LocationNormalizer`, mapping features) nel backend.
2. `repositories` (interfaccia + in-memory).
3. `SearchService` + `SearchCriteria`.
4. Integrazione LLM (`ChatModel`, tool schema, `ChatService`).
5. Router FastAPI + streaming SSE.
6. Frontend: pagina di chat.
7. Estensione dello scraper per `image_url` e spostamento in `scraper/`.
