# Poker con Socket in Python

Un'implementazione completa del **Texas Hold'em Poker** per 2 giocatori utilizzando socket TCP in Python con **interfaccia grafica Tkinter**.

## Struttura del Progetto

```
Socket/Poker/
├── poker_game.py          # Logica del gioco (carte, mazzo, valutazione mani)
├── server/
│   └── server.py          # Server che gestisce la partita
├── client/
│   └── client.py          # Client per giocare
└── README.md              # Questo file
```

## Caratteristiche

### Funzionalità Implementate

- 🎨 **Interfaccia Grafica Tkinter**: GUI intuitiva e accattivante con tema tavolo da poker
- ♠️ **Texas Hold'em completo**: Pre-flop, Flop, Turn, River e Showdown
- 💰 **Sistema di chips**: 1000 chips iniziali per giocatore
- 🎲 **Blind**: Small blind (5) e Big blind (10)
- 🎯 **Azioni**: Fold, Check, Call, Raise, All-in (tramite bottoni colorati)
- 🏆 **Valutazione automatica**: Tutte le mani dal poker (carta alta fino alla scala reale)
- 🔄 **Partite multiple**: Possibilità di giocare mani consecutive
- 📊 **Visualizzazione real-time**: Carte grafiche, chips, piatto, puntate e stato giocatori
- 🃏 **Carte colorate**: Rosse per cuori/quadri, nere per picche/fiori
- 🎬 **Transizioni fluide**: Notifiche e pause tra le fasi del gioco
- ⏱️ **Timeout automatico**: se un giocatore non agisce entro 45s viene forzato il fold
- 📈 **Statistiche live**: GUI aggiorna mani giocate/vinte per ogni giocatore
- 🔐 **Comunicazione robusta**: framing JSON bufferizzato con gestione pulita delle disconnessioni

## Miglioramenti recenti

- **JSONSocket condiviso** (`network_utils.py`) evita messaggi troncati e supporta timeout configurabili.
- **Server resiliente**: fold automatico su timeout, gestione disconnessioni e conteggio vittorie/presenze.
- **Client più informativo**: mostra le statistiche aggiornate e notifica quando un avversario viene forzato al fold.

### Mani di Poker Supportate

1. **Carta Alta** (High Card)
2. **Coppia** (Pair)
3. **Doppia Coppia** (Two Pair)
4. **Tris** (Three of a Kind)
5. **Scala** (Straight)
6. **Colore** (Flush)
7. **Full** (Full House)
8. **Poker** (Four of a Kind)
9. **Scala Colore** (Straight Flush)
10. **Scala Reale** (Royal Flush)

## Come Giocare

### 1. Avvia il Server

Apri un terminale nella directory `server/` ed esegui:

```bash
cd server
python server.py
```

Il server si metterà in ascolto su `localhost:5555` e attenderà 2 giocatori.

### 2. Avvia i Client GUI

Apri **due terminali separati** (uno per ogni giocatore) nella directory `client/` ed esegui:

**Terminale Giocatore 1:**
```bash
cd client
python client.py
```

**Terminale Giocatore 2:**
```bash
cd client
python client.py
```

Si aprirà una **finestra grafica** per ogni giocatore con:

#### Schermata di Connessione
- Campo **Nome**: Inserisci il tuo nome
- Campo **Server**: localhost (default)
- Campo **Porta**: 5555 (default)
- Bottone **CONNETTI**: Clicca per connetterti

### 3. Gioca con la GUI!

Una volta connessi entrambi i giocatori, vedrai la schermata di gioco con:

- **Tavolo verde** in stile casinò
- **Info avversario** in alto (nome, chips, puntata, stato)
- **Carte comuni** al centro con indicatore di fase
- **Le tue carte** visualizzate graficamente
- **Valutazione mano** automatica quando ci sono carte comuni
- **Info personali** in basso (nome, chips, puntata)
- **Bottoni azione** colorati quando è il tuo turno

#### Durante il Tuo Turno

Vedrai il messaggio **"È IL TUO TURNO!"** e bottoni colorati per le azioni:

- 🔴 **FOLD** (rosso): Ti ritiri dalla mano
- 🟠 **CHECK** (arancione): Passi senza puntare (solo se non c'è puntata da chiamare)
- 🔵 **CALL** (blu): Chiami la puntata corrente
- 🟢 **RAISE** (verde): Rilanci aumentando la puntata (apparirà un dialogo per l'importo)
- 🟣 **ALL-IN** (viola): Punti tutte le tue chips rimanenti

Le azioni disponibili cambiano dinamicamente in base alla situazione di gioco!

## Screenshot Interfaccia

### Schermata di Connessione
```
┌──────────────────────────────────────────┐
│     ♠ POKER - TEXAS HOLD'EM ♥           │
│                                          │
│  Nome:     [Giocatore________]          │
│  Server:   [localhost________]          │
│  Porta:    [5555_____________]          │
│                                          │
│         [    CONNETTI    ]               │
└──────────────────────────────────────────┘
```

### Schermata di Gioco
```
┌─────────────────────────────────────────────────┐
│ Avversario (D) ➤  Chips: 985  Puntata: 15      │
├─────────────────────────────────────────────────┤
│                   FLOP                          │
│                                                 │
│  Carte Comuni:  [K♠] [9♥] [9♦]                │
│                                                 │
│  💰 Piatto: 25                                 │
│  Puntata corrente: 15                          │
│                                                 │
│  Le Tue Carte:  [A♠] [K♥]                     │
│  🎯 Tua mano: Doppia Coppia (Re e Nove)       │
├─────────────────────────────────────────────────┤
│ 🎮 Alice  Chips: 990  Puntata: 10             │
│                                                 │
│      🎲 È IL TUO TURNO!                        │
│                                                 │
│  [FOLD] [CALL(5)] [RAISE] [ALL-IN(990)]       │
└─────────────────────────────────────────────────┘
```

## Regole del Gioco

### Flusso della Mano

1. **Distribuzione**: Ogni giocatore riceve 2 carte coperte
2. **Blind**: Il dealer paga lo small blind (5), l'altro il big blind (10)
3. **Pre-flop**: Primo giro di puntate
4. **Flop**: 3 carte comuni vengono scoperte sul tavolo
5. **Giro di puntate**
6. **Turn**: 1 carta comune aggiuntiva viene scoperta
7. **Giro di puntate**
8. **River**: L'ultima carta comune viene scoperta
9. **Giro di puntate finale**
10. **Showdown**: I giocatori mostrano le carte e si determina il vincitore

### Vincere una Mano

Vinci una mano se:
- Tutti gli altri giocatori hanno foldato
- Allo showdown, hai la mano migliore (migliore combinazione di 5 carte tra le tue 2 carte private e le 5 comuni)

### Il Dealer Button

- Il **dealer button** (indicato con `(D)`) ruota tra i giocatori dopo ogni mano
- Il dealer paga lo **small blind**
- L'altro giocatore paga il **big blind**
- Nel pre-flop, il dealer è il primo a parlare
- Negli altri giri, parla per primo il giocatore dopo il dealer

## Requisiti

- **Python 3.6+**
- **Tkinter** (incluso nella maggior parte delle installazioni Python)
- Nessuna libreria esterna richiesta (usa solo librerie standard)

> **Nota**: Tkinter è incluso di default in Python su Windows e macOS. Su Linux potrebbe essere necessario installarlo:
> ```bash
> # Ubuntu/Debian
> sudo apt-get install python3-tk
>
> # Fedora
> sudo dnf install python3-tkinter
> ```

## Architettura

### Interfaccia Grafica (Tkinter)

Il client utilizza **Tkinter** per creare una GUI moderna con:

- **Colori tematici**: Verde tavolo da poker, oro per chips, bottoni colorati
- **Layout responsive**: Organizzato in aree (avversario, tavolo, giocatore, azioni)
- **Carte grafiche**: Frame bianchi con valore e seme colorato
- **Aggiornamenti real-time**: Thread separato per la ricezione messaggi
- **Dialog interattivi**: Per raise amount e continuare a giocare
- **Feedback visivo**: Messagebox per eventi importanti

### Comunicazione Client-Server

Il protocollo di comunicazione usa **messaggi JSON** su socket TCP:

#### Messaggi Client → Server
- `{'type': 'join', 'name': 'Alice'}` - Unirsi al gioco
- `{'action': 'fold'}` - Fold
- `{'action': 'check'}` - Check
- `{'action': 'call'}` - Call
- `{'action': 'raise', 'amount': 50}` - Raise
- `{'continue': True/False}` - Continuare a giocare

#### Messaggi Server → Client
- `{'type': 'joined', 'player_id': 0, ...}` - Conferma join
- `{'type': 'deal', 'cards': [...]}` - Carte iniziali
- `{'type': 'game_state', ...}` - Stato del gioco (aggiorna GUI)
- `{'type': 'your_turn'}` - È il tuo turno (mostra bottoni azioni)
- `{'type': 'player_action', ...}` - Notifica azione di un giocatore
- `{'type': 'phase_change', ...}` - Cambio fase (flop/turn/river)
- `{'type': 'hand_result', ...}` - Risultato della mano (dialog con carte)
- `{'type': 'ask_continue'}` - Chiede se continuare (dialog yes/no)
- `{'type': 'game_over', ...}` - Fine partita
- `{'type': 'error', ...}` - Messaggio di errore

### Moduli

#### `poker_game.py`
- `Card`: Rappresenta una carta singola
- `Deck`: Mazzo di 52 carte con shuffle e deal
- `evaluate_hand()`: Valuta la migliore mano di 5 carte
- `compare_hands()`: Confronta due mani
- `hand_description()`: Descrizione testuale della mano

#### `server/server.py`
- `PokerServer`: Gestisce il gioco e le connessioni
- Coordina i turni e i giri di puntate
- Applica le regole del poker
- Determina i vincitori

#### `client/client.py`
- `PokerGUI`: Interfaccia grafica Tkinter per il gioco
- `create_connection_screen()`: Schermata iniziale di connessione
- `create_game_screen()`: Schermata principale di gioco
- `draw_card()`: Disegna una carta grafica
- `update_game_display()`: Aggiorna la visualizzazione del gioco
- `show_action_buttons()`: Mostra bottoni azioni dinamicamente
- Thread separato per ricezione messaggi asincrona

#### `network_utils.py`
- `JSONSocket`: wrapper riutilizzabile per socket TCP con buffer interno, newline framing e timeout opzionali.
- Gestisce anche la chiusura delle connessioni e solleva eccezioni dedicate per disconnessioni.

## Limitazioni

- Supporta esattamente **2 giocatori** (non di più, non di meno)
- Il server deve essere avviato prima dei client
- Non c'è persistenza (il gioco termina quando si chiude il server)
- Non c'è autenticazione o sicurezza

## Possibili Estensioni Future

- 🎮 Supporto per 3-10 giocatori
- 💾 Salvataggio dello stato del gioco e replay
- 🌐 Supporto per partite su rete (non solo localhost)
- 🏆 Sistema di ranking, statistiche e leaderboard
- 🎨 Miglioramenti grafici (immagini carte reali, animazioni)
- 🔐 Autenticazione, login e sicurezza
- 🤖 Bot AI come avversario (machine learning)
- 🎵 Effetti sonori e musica di sottofondo
- 💬 Chat tra giocatori
- 🎁 Tornei e modalità torneo

## Troubleshooting

### "Address already in use"
Il server è già in esecuzione. Chiudi il processo precedente o cambia la porta.

### "Connection refused"
Assicurati che il server sia in esecuzione prima di avviare i client.

### Il gioco si blocca
Premi `Ctrl+C` per interrompere client o server e riavvia.

## Autore

Progetto creato per imparare la programmazione di rete con socket in Python.

## Licenza

Questo progetto è open source e disponibile per scopi educativi.

---

**Buon divertimento! 🃏🎲**
# Poker_PythonSocket
