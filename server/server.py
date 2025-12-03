"""
=============================================================================
SERVER POKER TEXAS HOLD'EM - Progetto di Sistemi e Reti
=============================================================================

Autore: Studente V anno Informatica
Data: Dicembre 2024

DESCRIZIONE:
    Questo modulo implementa il server per un gioco di poker Texas Hold'em
    multiplayer. Il server gestisce la connessione di 2 giocatori tramite
    socket TCP e coordina tutte le fasi del gioco.

CONCETTI UTILIZZATI:
    - Socket TCP/IP per la comunicazione client-server
    - Protocollo JSON per lo scambio di messaggi strutturati
    - Gestione dei timeout per evitare blocchi del gioco
    - Pattern di gioco: dealer button, blind, fasi di puntata

FUNZIONAMENTO:
    1. Il server si mette in ascolto sulla porta specificata
    2. Accetta connessioni da 2 client (giocatori)
    3. Gestisce il loop di gioco: distribuzione carte, puntate, showdown
    4. Comunica lo stato del gioco ai client tramite messaggi JSON
"""

# =============================================================================
# IMPORTAZIONE LIBRERIE
# =============================================================================

import socket      # Libreria per la comunicazione di rete tramite socket
import sys         # Per manipolare il path di sistema
import os          # Per operazioni sul filesystem
import time        # Per le pause temporizzate nel gioco

# Aggiungo la directory parent al path Python così posso importare i moduli
# che si trovano nella cartella principale del progetto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importo le classi per la logica del poker (mazzo, valutazione mani)
from poker_game import Deck, evaluate_hand, compare_hands, hand_description

# Importo le utility di rete per la comunicazione JSON via socket
from network_utils import JSONSocket, ConnectionClosed


# =============================================================================
# ECCEZIONI PERSONALIZZATE
# =============================================================================

class TimeoutAzioneGiocatore(Exception):
    """
    Eccezione sollevata quando un giocatore non compie un'azione entro il tempo limite.
    
    Nel poker online è fondamentale avere un timeout per evitare che un giocatore
    blocchi indefinitamente la partita. Quando scade il tempo, il giocatore viene
    forzato al fold.
    """
    pass


class ConnessioneGiocatorePersa(Exception):
    """
    Eccezione sollevata quando la connessione con un giocatore si interrompe.
    
    Può succedere per vari motivi:
    - Il client si è disconnesso volontariamente
    - Problemi di rete
    - Crash del programma client
    
    Attributi:
        id_giocatore: L'ID del giocatore che si è disconnesso (0 o 1)
    """
    def __init__(self, id_giocatore):
        self.id_giocatore = id_giocatore
        super().__init__(f"Giocatore {id_giocatore} disconnesso")


# =============================================================================
# CLASSE PRINCIPALE DEL SERVER
# =============================================================================

class ServerPoker:
    """
    Server per il gioco del poker Texas Hold'em per 2 giocatori.
    
    Questa classe gestisce tutto il ciclo di vita di una partita:
    - Accettazione delle connessioni dei giocatori
    - Distribuzione delle carte
    - Gestione dei turni e delle puntate
    - Determinazione del vincitore
    
    Il gioco segue le regole standard del Texas Hold'em:
    - Ogni giocatore riceve 2 carte coperte (hole cards)
    - 5 carte comuni vengono rivelate in 3 fasi: flop (3), turn (1), river (1)
    - Vince chi ha la combinazione migliore di 5 carte
    
    Attributi di classe:
        host: Indirizzo IP su cui il server ascolta
        porta: Porta TCP su cui il server ascolta
        clients: Lista dei client connessi con le loro info
        stato_gioco: Dizionario con tutto lo stato corrente della partita
    """

    def __init__(self, host='localhost', porta=5555):
        """
        Inizializza il server con i parametri di rete.
        
        Args:
            host: Indirizzo IP del server (default: localhost per test locali)
            porta: Porta su cui il server ascolta (default: 5555)
        
        Il costruttore imposta anche tutti i parametri del gioco:
        - Valore dei blind (piccolo e grande)
        - Chips iniziali per ogni giocatore
        - Timeout per le azioni
        """
        # Parametri di rete
        self.host = host
        self.porta = porta
        self.socket_server = None  # Socket principale del server
        
        # Lista dei client connessi
        # Ogni elemento contiene: socket, indirizzo, nome, canale JSON, stato connessione
        self.clients = []
        
        # Stato completo del gioco - questo dizionario contiene TUTTO
        # È la "single source of truth" per lo stato della partita
        self.stato_gioco = {
            'giocatori': {},        # Info su ogni giocatore (chips, carte, puntata, ecc.)
            'mazzo': None,          # Oggetto Deck per le carte
            'carte_comuni': [],     # Le 5 carte sul tavolo
            'piatto': 0,            # Totale chips nel piatto
            'puntata_corrente': 0,  # Puntata da pareggiare
            'dealer_button': 0,     # Chi è il dealer (0 o 1)
            'fase': 'attesa',       # Fase corrente del gioco
            'giocatore_attivo': 0,  # Chi deve agire
        }
        
        # Parametri del gioco - configurabili
        self.piccolo_blind = 5      # Small blind (metà del big blind)
        self.grande_blind = 10      # Big blind (puntata obbligatoria)
        self.chips_iniziali = 1000  # Chips di partenza per giocatore
        self.timeout_azione = 45    # Secondi per decidere l'azione

    # =========================================================================
    # METODI PER LA GESTIONE DELLA RETE
    # =========================================================================

    def avvia(self):
        """
        Avvia il server e attende la connessione dei giocatori.
        
        Questo metodo:
        1. Crea il socket TCP del server
        2. Lo associa all'indirizzo e porta specificati
        3. Si mette in ascolto per connessioni in entrata
        4. Accetta esattamente 2 giocatori
        5. Avvia il gioco quando entrambi sono connessi
        
        La funzione setsockopt con SO_REUSEADDR permette di riutilizzare
        la porta immediatamente dopo la chiusura del server (utile per i test).
        """
        # Creo il socket TCP (AF_INET = IPv4, SOCK_STREAM = TCP)
        self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Permetto il riutilizzo immediato della porta dopo la chiusura
        # Senza questa opzione, dovremmo aspettare che il SO rilasci la porta
        self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Associo il socket all'indirizzo e porta
        self.socket_server.bind((self.host, self.porta))
        
        # Mi metto in ascolto, con coda massima di 2 connessioni
        self.socket_server.listen(2)

        print(f"Server in ascolto su {self.host}:{self.porta}")
        print("In attesa di 2 giocatori...")

        # Ciclo di accettazione connessioni - continuo finché non ho 2 giocatori
        while len(self.clients) < 2:
            # accept() è BLOCCANTE: il programma si ferma qui finché
            # non arriva una nuova connessione
            socket_client, indirizzo = self.socket_server.accept()
            print(f"Connessione da {indirizzo}")

            # Creo un canale JSON per comunicare con questo client
            # JSONSocket incapsula il socket e gestisce l'invio/ricezione di JSON
            canale = JSONSocket(socket_client)
            
            try:
                # Aspetto che il client invii il messaggio di join (max 10 secondi)
                dati = canale.receive(timeout=10)
            except TimeoutError:
                print("Nessun messaggio di join ricevuto: connessione chiusa")
                canale.close()
                continue
            except ConnectionClosed:
                canale.close()
                continue

            # Verifico che il messaggio sia di tipo 'join'
            if dati and dati.get('type') == 'join':
                nome_giocatore = dati.get('name', 'Sconosciuto')
                id_giocatore = len(self.clients)  # 0 per il primo, 1 per il secondo
                
                # Salvo le info del client
                self.clients.append({
                    'socket': socket_client,
                    'indirizzo': indirizzo,
                    'nome': nome_giocatore,
                    'canale': canale,
                    'connesso': True
                })

                # Inizializzo lo stato del giocatore nel gioco
                self.stato_gioco['giocatori'][id_giocatore] = {
                    'nome': nome_giocatore,
                    'chips': self.chips_iniziali,
                    'carte': [],           # Le 2 carte personali
                    'puntata': 0,          # Quanto ha puntato in questo giro
                    'foldato': False,      # Se ha abbandonato la mano
                    'all_in': False,       # Se ha puntato tutto
                    'statistiche': {       # Statistiche per la sessione
                        'mani_giocate': 0,
                        'mani_vinte': 0
                    }
                }

                # Invio conferma al client con il suo ID
                self.invia_messaggio(id_giocatore, {
                    'type': 'joined',
                    'player_id': id_giocatore,
                    'message': f"Benvenuto {nome_giocatore}! Sei il giocatore {id_giocatore + 1}"
                })

                print(f"Giocatore {id_giocatore + 1}: {nome_giocatore}")
            else:
                print("Richiesta di join non valida. Chiudo la connessione.")
                canale.close()

        # Quando ho 2 giocatori, inizio il gioco!
        print("\nTutti i giocatori sono connessi. Inizio il gioco!")
        self.inizia_partita()

    # =========================================================================
    # METODI PER LA LOGICA DEL GIOCO
    # =========================================================================

    def inizia_partita(self):
        """
        Loop principale della partita.
        
        Questo metodo gestisce il ciclo di gioco:
        1. Inizia una nuova mano
        2. Gioca la mano (puntate, showdown)
        3. Chiede se i giocatori vogliono continuare
        4. Controlla se qualcuno ha finito le chips
        
        Il ciclo continua finché i giocatori vogliono giocare
        e nessuno ha esaurito le chips.
        """
        try:
            while True:
                # Preparo e gioco una nuova mano
                self.nuova_mano()
                self.gioca_mano()

                # Chiedo ai giocatori se vogliono continuare
                if not self.chiedi_continua():
                    break

                # Controllo se qualcuno ha finito i soldi
                for id_giocatore, giocatore in self.stato_gioco['giocatori'].items():
                    if giocatore['chips'] <= 0:
                        # Questo giocatore ha perso tutto!
                        id_vincitore = 1 - id_giocatore  # L'altro è il vincitore
                        vincitore = self.stato_gioco['giocatori'][id_vincitore]
                        self.broadcast({
                            'type': 'game_over',
                            'winner': vincitore['nome'],
                            'message': f"{vincitore['nome']} ha vinto la partita!"
                        })
                        return

        except ConnessioneGiocatorePersa as errore:
            # Un giocatore si è disconnesso
            self.gestisci_disconnessione(errore.id_giocatore)
        except Exception as errore:
            # Errore generico - stampo il traceback per debug
            print(f"Errore durante il gioco: {errore}")
            import traceback
            traceback.print_exc()
        finally:
            # In ogni caso, chiudo tutto pulitamente
            self.chiudi()

    def nuova_mano(self):
        """
        Prepara una nuova mano di poker.
        
        Operazioni eseguite:
        1. Crea un nuovo mazzo mescolato
        2. Resetta le carte comuni e il piatto
        3. Resetta lo stato dei giocatori (carte, puntate, fold)
        4. Ruota il dealer button (importante per l'ordine di gioco)
        5. Distribuisce 2 carte a ogni giocatore
        6. Pubblica i blind
        """
        print("\n" + "=" * 60)
        print("NUOVA MANO")
        print("=" * 60)

        # Reset dello stato del gioco
        self.stato_gioco['mazzo'] = Deck()  # Nuovo mazzo mescolato
        self.stato_gioco['carte_comuni'] = []
        self.stato_gioco['piatto'] = 0
        self.stato_gioco['puntata_corrente'] = 0
        self.stato_gioco['fase'] = 'pre_flop'  # Prima fase: solo carte personali

        # Reset dello stato di ogni giocatore
        for giocatore in self.stato_gioco['giocatori'].values():
            giocatore['carte'] = []
            giocatore['puntata'] = 0
            giocatore['foldato'] = False
            giocatore['all_in'] = False
            # Inizializzo le statistiche se non esistono
            giocatore.setdefault('statistiche', {'mani_giocate': 0, 'mani_vinte': 0})
            giocatore['statistiche']['mani_giocate'] += 1

        # Ruoto il dealer button: alterna tra 0 e 1
        # Nel Texas Hold'em, il dealer button determina chi paga i blind
        self.stato_gioco['dealer_button'] = 1 - self.stato_gioco['dealer_button']

        # Distribuisco 2 carte a ogni giocatore
        for id_giocatore in range(2):
            carte = self.stato_gioco['mazzo'].deal(2)  # Pesco 2 carte
            self.stato_gioco['giocatori'][id_giocatore]['carte'] = carte

        # Invio le carte ai giocatori (ogni giocatore vede solo le sue!)
        for id_giocatore in range(len(self.clients)):
            self.invia_messaggio(id_giocatore, {
                'type': 'deal',
                'cards': [c.to_dict() for c in self.stato_gioco['giocatori'][id_giocatore]['carte']],
                'dealer_button': self.stato_gioco['dealer_button']
            })

        # Pubblica i blind (puntate obbligatorie)
        self.pubblica_blind()

        # Piccola pausa per permettere alla GUI di visualizzare le carte
        time.sleep(1)
        self.broadcast_stato_gioco()

    def pubblica_blind(self):
        """
        Gestisce la pubblicazione dei blind.
        
        Nel Texas Hold'em heads-up (2 giocatori):
        - Il dealer paga lo small blind
        - L'altro giocatore paga il big blind
        - Il primo a parlare nel pre-flop è il dealer (small blind)
        
        I blind sono puntate obbligatorie che garantiscono sempre
        un minimo nel piatto, incentivando l'azione.
        """
        dealer = self.stato_gioco['dealer_button']
        giocatore_piccolo = dealer       # Il dealer paga lo small blind
        giocatore_grande = 1 - dealer    # L'altro paga il big blind

        # Small blind - il minimo tra il blind e le chips disponibili
        importo_piccolo = min(
            self.piccolo_blind, 
            self.stato_gioco['giocatori'][giocatore_piccolo]['chips']
        )
        self.stato_gioco['giocatori'][giocatore_piccolo]['chips'] -= importo_piccolo
        self.stato_gioco['giocatori'][giocatore_piccolo]['puntata'] = importo_piccolo
        self.stato_gioco['piatto'] += importo_piccolo

        # Big blind
        importo_grande = min(
            self.grande_blind, 
            self.stato_gioco['giocatori'][giocatore_grande]['chips']
        )
        self.stato_gioco['giocatori'][giocatore_grande]['chips'] -= importo_grande
        self.stato_gioco['giocatori'][giocatore_grande]['puntata'] = importo_grande
        self.stato_gioco['piatto'] += importo_grande

        # La puntata da pareggiare è il big blind
        self.stato_gioco['puntata_corrente'] = importo_grande

        # Nel pre-flop, il primo a parlare è il dealer (che ha messo lo small blind)
        self.stato_gioco['giocatore_attivo'] = dealer

        # Log per debug
        print(f"{self.stato_gioco['giocatori'][giocatore_piccolo]['nome']} paga small blind: {importo_piccolo}")
        print(f"{self.stato_gioco['giocatori'][giocatore_grande]['nome']} paga big blind: {importo_grande}")

    def gioca_mano(self):
        """
        Gestisce tutte le fasi di una mano di poker.
        
        Le fasi del Texas Hold'em sono:
        1. PRE-FLOP: Solo le carte personali, primo giro di puntate
        2. FLOP: Si rivelano 3 carte comuni
        3. TURN: Si rivela la 4a carta comune
        4. RIVER: Si rivela la 5a carta comune
        5. SHOWDOWN: Si confrontano le mani (se più di un giocatore è rimasto)
        
        Dopo ogni fase (tranne pre-flop) c'è un giro di puntate.
        Se un giocatore folda, la mano finisce e l'altro vince.
        """
        # PRE-FLOP - Primo giro di puntate (carte personali)
        if not self.giro_puntate():
            return  # Qualcuno ha foldato

        # FLOP - Rivelo 3 carte comuni
        if self.stato_gioco['fase'] == 'pre_flop':
            self.stato_gioco['carte_comuni'] = self.stato_gioco['mazzo'].deal(3)
            self.stato_gioco['fase'] = 'flop'
            print(f"\nFLOP: {self.stato_gioco['carte_comuni']}")

            # Notifico i client del cambio fase
            self.broadcast({
                'type': 'phase_change',
                'phase': 'flop',
                'message': 'Flop: 3 carte comuni rivelate!'
            })
            time.sleep(0.5)
            self.broadcast_stato_gioco()
            time.sleep(0.5)

            if not self.giro_puntate():
                return

        # TURN - Rivelo la 4a carta
        if self.stato_gioco['fase'] == 'flop':
            self.stato_gioco['carte_comuni'].extend(self.stato_gioco['mazzo'].deal(1))
            self.stato_gioco['fase'] = 'turn'
            print(f"\nTURN: {self.stato_gioco['carte_comuni'][-1]}")

            self.broadcast({
                'type': 'phase_change',
                'phase': 'turn',
                'message': 'Turn: quarta carta comune rivelata!'
            })
            time.sleep(0.5)
            self.broadcast_stato_gioco()
            time.sleep(0.5)

            if not self.giro_puntate():
                return

        # RIVER - Rivelo la 5a e ultima carta
        if self.stato_gioco['fase'] == 'turn':
            self.stato_gioco['carte_comuni'].extend(self.stato_gioco['mazzo'].deal(1))
            self.stato_gioco['fase'] = 'river'
            print(f"\nRIVER: {self.stato_gioco['carte_comuni'][-1]}")

            self.broadcast({
                'type': 'phase_change',
                'phase': 'river',
                'message': 'River: ultima carta comune rivelata!'
            })
            time.sleep(0.5)
            self.broadcast_stato_gioco()
            time.sleep(0.5)

            if not self.giro_puntate():
                return

        # SHOWDOWN - Confronto finale delle mani
        self.showdown()

    def giro_puntate(self):
        """
        Esegue un giro completo di puntate.
        
        Regole del giro di puntate:
        - Ogni giocatore può: fold, check, call, raise, all-in
        - Il giro finisce quando tutti hanno pareggiato la puntata
        - Se qualcuno rilancia, gli altri devono reagire
        - Un giocatore all-in non può più agire
        
        Returns:
            True se il gioco deve continuare
            False se c'è un vincitore (tutti gli altri hanno foldato)
        """
        # Reset delle puntate all'inizio di ogni fase (tranne pre-flop)
        for giocatore in self.stato_gioco['giocatori'].values():
            giocatore['puntata'] = 0 if self.stato_gioco['fase'] != 'pre_flop' else giocatore['puntata']

        if self.stato_gioco['fase'] != 'pre_flop':
            self.stato_gioco['puntata_corrente'] = 0
            # Dopo il pre-flop, il primo a parlare è chi è dopo il dealer
            self.stato_gioco['giocatore_attivo'] = 1 - self.stato_gioco['dealer_button']

        contatore_azioni = 0
        giocatori_agiti = set()  # Tiene traccia di chi ha già agito

        while True:
            # Controllo se tutti sono all-in o hanno foldato
            # In questo caso non serve continuare a chiedere azioni
            attivi_che_possono_agire = [
                pid for pid, g in self.stato_gioco['giocatori'].items()
                if not g['foldato'] and not g['all_in']
            ]
            
            if len(attivi_che_possono_agire) == 0:
                # Nessuno può più agire - il giro finisce
                break

            if len(attivi_che_possono_agire) == 1:
                # Solo uno può agire - controllo se ha già pareggiato
                id_rimasto = attivi_che_possono_agire[0]
                rimasto = self.stato_gioco['giocatori'][id_rimasto]
                if rimasto['puntata'] >= self.stato_gioco['puntata_corrente']:
                    break

            id_giocatore = self.stato_gioco['giocatore_attivo']
            giocatore = self.stato_gioco['giocatori'][id_giocatore]

            # Salto i giocatori che hanno foldato o sono all-in
            if giocatore['foldato'] or giocatore['all_in']:
                self.stato_gioco['giocatore_attivo'] = 1 - id_giocatore
                continue

            # Controllo se tutti hanno agito e le puntate sono pari
            if len(giocatori_agiti) == 2 and all(
                self.stato_gioco['giocatori'][p]['puntata'] == self.stato_gioco['puntata_corrente']
                or self.stato_gioco['giocatori'][p]['foldato']
                or self.stato_gioco['giocatori'][p]['all_in']
                for p in range(2)
            ):
                break

            # Chiedo l'azione al giocatore
            self.invia_messaggio(id_giocatore, {'type': 'your_turn'})

            # Ricevo l'azione (con timeout!)
            try:
                dati_azione = self.ricevi_messaggio(id_giocatore, timeout=self.timeout_azione)
            except TimeoutAzioneGiocatore:
                # Tempo scaduto! Forzo il fold
                if self.gestisci_fold_forzato(id_giocatore, 'timeout'):
                    return False
                continue
            except ConnessioneGiocatorePersa as errore:
                self.gestisci_disconnessione(errore.id_giocatore)
                return False

            if not dati_azione:
                continue

            azione = dati_azione.get('action')
            importo = dati_azione.get('amount', 0)

            # Processo l'azione ricevuta
            if azione == 'fold':
                # Il giocatore abbandona la mano
                giocatore['foldato'] = True
                print(f"{giocatore['nome']} ha foldato")

                self.broadcast({
                    'type': 'player_action',
                    'player_id': id_giocatore,
                    'player_name': giocatore['nome'],
                    'action': 'fold',
                    'message': f"{giocatore['nome']} ha foldato"
                })
                time.sleep(0.3)
                self.broadcast_stato_gioco()

                # Controllo se c'è un vincitore
                giocatori_rimasti = [g for g in self.stato_gioco['giocatori'].values() if not g['foldato']]
                if len(giocatori_rimasti) == 1:
                    id_vincitore = [i for i, g in self.stato_gioco['giocatori'].items() if not g['foldato']][0]
                    self.assegna_piatto(id_vincitore, "fold")
                    return False

            elif azione == 'check':
                # Check: passa senza puntare (solo se non c'è puntata da chiamare)
                if giocatore['puntata'] < self.stato_gioco['puntata_corrente']:
                    self.invia_messaggio(id_giocatore, {
                        'type': 'error',
                        'message': 'Non puoi fare check, devi chiamare o rilanciare'
                    })
                    continue
                    
                print(f"{giocatore['nome']} ha fatto check")
                self.broadcast({
                    'type': 'player_action',
                    'player_id': id_giocatore,
                    'player_name': giocatore['nome'],
                    'action': 'check',
                    'message': f"{giocatore['nome']} ha fatto check"
                })
                time.sleep(0.3)

            elif azione == 'call':
                # Call: pareggia la puntata corrente
                da_chiamare = self.stato_gioco['puntata_corrente'] - giocatore['puntata']
                da_chiamare = min(da_chiamare, giocatore['chips'])  # Non più di quello che ho
                
                giocatore['chips'] -= da_chiamare
                giocatore['puntata'] += da_chiamare
                self.stato_gioco['piatto'] += da_chiamare
                print(f"{giocatore['nome']} ha chiamato {da_chiamare}")

                # Se ho finito le chips, sono all-in
                if giocatore['chips'] == 0:
                    giocatore['all_in'] = True
                    print(f"{giocatore['nome']} è all-in!")

                self.broadcast({
                    'type': 'player_action',
                    'player_id': id_giocatore,
                    'player_name': giocatore['nome'],
                    'action': 'call',
                    'amount': da_chiamare,
                    'message': f"{giocatore['nome']} ha chiamato {da_chiamare}"
                })
                time.sleep(0.3)

            elif azione == 'raise':
                # Raise: rilancio - aumento la puntata
                # Il rilancio deve essere almeno il doppio della puntata corrente
                rilancio_minimo = self.stato_gioco['puntata_corrente'] * 2 - giocatore['puntata']
                
                if importo < rilancio_minimo and importo < giocatore['chips']:
                    self.invia_messaggio(id_giocatore, {
                        'type': 'error',
                        'message': f'Il rilancio minimo è {rilancio_minimo}'
                    })
                    continue

                # Non posso puntare più di quello che ho
                importo = min(importo, giocatore['chips'])
                giocatore['chips'] -= importo
                self.stato_gioco['piatto'] += importo
                giocatore['puntata'] += importo
                self.stato_gioco['puntata_corrente'] = giocatore['puntata']
                
                # Reset: l'altro giocatore deve reagire al rilancio
                giocatori_agiti = {id_giocatore}

                e_all_in = giocatore['chips'] == 0
                if e_all_in:
                    giocatore['all_in'] = True
                    print(f"{giocatore['nome']} è all-in con {importo}!")
                else:
                    print(f"{giocatore['nome']} ha rilanciato a {giocatore['puntata']}")

                testo_azione = 'all-in' if e_all_in else 'raise'
                messaggio = f"{giocatore['nome']} è ALL-IN con {importo}!" if e_all_in else f"{giocatore['nome']} ha rilanciato a {giocatore['puntata']}"

                self.broadcast({
                    'type': 'player_action',
                    'player_id': id_giocatore,
                    'player_name': giocatore['nome'],
                    'action': testo_azione,
                    'amount': importo,
                    'message': messaggio
                })
                time.sleep(0.3)

            giocatori_agiti.add(id_giocatore)
            self.broadcast_stato_gioco()

            # Passo al prossimo giocatore
            self.stato_gioco['giocatore_attivo'] = 1 - id_giocatore
            contatore_azioni += 1

        return True

    def gestisci_fold_forzato(self, id_giocatore, motivo):
        """
        Forza il fold di un giocatore (per timeout o altra penalità).
        
        Args:
            id_giocatore: ID del giocatore da forzare
            motivo: Stringa che spiega il motivo del fold forzato
            
        Returns:
            True se la mano è finita (l'altro ha vinto)
            False se il gioco può continuare
        """
        giocatore = self.stato_gioco['giocatori'][id_giocatore]
        if giocatore['foldato']:
            return False  # Già foldato, nulla da fare

        giocatore['foldato'] = True
        giocatore['all_in'] = False

        # Creo il messaggio appropriato
        testo_motivo = {
            'timeout': f"{giocatore['nome']} ha esaurito il tempo e viene forzato al fold"
        }.get(motivo, f"{giocatore['nome']} è stato forzato al fold")

        self.broadcast({
            'type': 'player_action',
            'player_id': id_giocatore,
            'player_name': giocatore['nome'],
            'action': 'forced_fold',
            'message': testo_motivo
        })
        time.sleep(0.3)
        self.broadcast_stato_gioco()

        # Controllo se c'è un vincitore
        giocatori_attivi = [pid for pid, dati in self.stato_gioco['giocatori'].items() if not dati['foldato']]
        if len(giocatori_attivi) == 1:
            self.assegna_piatto(giocatori_attivi[0], motivo)
            return True
        return False

    def showdown(self):
        """
        Determina il vincitore confrontando le mani.
        
        Nel Texas Hold'em, ogni giocatore può usare qualsiasi combinazione
        di 5 carte tra le sue 2 personali e le 5 comuni per formare
        la mano migliore.
        
        Il confronto avviene tramite la funzione compare_hands che
        valuta la forza di ogni combinazione.
        """
        print("\n" + "=" * 60)
        print("SHOWDOWN")
        print("=" * 60)

        # Mostro le carte di tutti i giocatori ancora in gioco
        for id_giocatore, giocatore in self.stato_gioco['giocatori'].items():
            if not giocatore['foldato']:
                print(f"\n{giocatore['nome']}: {giocatore['carte']}")

        # Valuto le mani di chi non ha foldato
        mani = {}
        for id_giocatore, giocatore in self.stato_gioco['giocatori'].items():
            if not giocatore['foldato']:
                tutte_carte = giocatore['carte'] + self.stato_gioco['carte_comuni']
                mani[id_giocatore] = evaluate_hand(tutte_carte)
                descrizione = hand_description(tutte_carte)
                print(f"{giocatore['nome']}: {descrizione}")

        # Determino il vincitore
        if len(mani) == 1:
            # Solo uno rimasto (l'altro ha foldato)
            id_vincitore = list(mani.keys())[0]
        else:
            # Confronto le mani
            ids_giocatori = list(mani.keys())
            carte_0 = self.stato_gioco['giocatori'][ids_giocatori[0]]['carte'] + self.stato_gioco['carte_comuni']
            carte_1 = self.stato_gioco['giocatori'][ids_giocatori[1]]['carte'] + self.stato_gioco['carte_comuni']
            risultato = compare_hands(carte_0, carte_1)

            if risultato > 0:
                id_vincitore = ids_giocatori[0]
            elif risultato < 0:
                id_vincitore = ids_giocatori[1]
            else:
                # Pareggio! Dividiamo il piatto
                self.dividi_piatto(ids_giocatori)
                return

        self.assegna_piatto(id_vincitore, "showdown")

    def assegna_piatto(self, id_vincitore, motivo):
        """
        Assegna il piatto al vincitore e notifica tutti.
        
        Args:
            id_vincitore: ID del giocatore vincitore
            motivo: Come ha vinto ('fold', 'showdown', 'timeout', ecc.)
        """
        vincitore = self.stato_gioco['giocatori'][id_vincitore]
        vincitore['chips'] += self.stato_gioco['piatto']
        vincitore.setdefault('statistiche', {'mani_giocate': 0, 'mani_vinte': 0})
        vincitore['statistiche']['mani_vinte'] += 1

        print(f"\n{vincitore['nome']} vince {self.stato_gioco['piatto']} chips ({motivo})!")

        # Preparo i dati del risultato
        dati_risultato = {
            'type': 'hand_result',
            'winner_id': id_vincitore,
            'winner_name': vincitore['nome'],
            'pot': self.stato_gioco['piatto'],
            'reason': motivo,
            'all_cards': {},
            'stats': {pid: giocatore.get('statistiche', {}) for pid, giocatore in self.stato_gioco['giocatori'].items()}
        }

        # Includo le carte di tutti (per il replay)
        for pid, giocatore in self.stato_gioco['giocatori'].items():
            if not giocatore['foldato']:
                dati_risultato['all_cards'][pid] = [c.to_dict() for c in giocatore['carte']]

        self.broadcast(dati_risultato)
        self.broadcast_stato_gioco()

        # Reset del piatto
        self.stato_gioco['piatto'] = 0

    def dividi_piatto(self, ids_giocatori):
        """
        Divide il piatto equamente in caso di pareggio.
        
        Args:
            ids_giocatori: Lista degli ID dei giocatori che hanno pareggiato
        """
        importo_per_giocatore = self.stato_gioco['piatto'] // len(ids_giocatori)

        for id_giocatore in ids_giocatori:
            giocatore = self.stato_gioco['giocatori'][id_giocatore]
            giocatore['chips'] += importo_per_giocatore
            giocatore.setdefault('statistiche', {'mani_giocate': 0, 'mani_vinte': 0})
            giocatore['statistiche']['mani_vinte'] += 1

        nomi = [self.stato_gioco['giocatori'][pid]['nome'] for pid in ids_giocatori]
        print(f"\nPareggio! {' e '.join(nomi)} si dividono il piatto di {self.stato_gioco['piatto']} chips")

        self.broadcast({
            'type': 'hand_result',
            'winner_id': -1,
            'winner_name': 'Pareggio',
            'pot': self.stato_gioco['piatto'],
            'reason': 'split',
            'all_cards': {pid: [c.to_dict() for c in self.stato_gioco['giocatori'][pid]['carte']]
                          for pid in ids_giocatori},
            'stats': {pid: self.stato_gioco['giocatori'][pid].get('statistiche', {}) 
                      for pid in self.stato_gioco['giocatori']}
        })

        self.stato_gioco['piatto'] = 0

    def chiedi_continua(self):
        """
        Chiede ai giocatori se vogliono continuare a giocare.
        
        Returns:
            True se ENTRAMBI i giocatori vogliono continuare
            False altrimenti
        """
        self.broadcast({'type': 'ask_continue'})

        risposte = []
        for id_giocatore in range(len(self.clients)):
            try:
                dati = self.ricevi_messaggio(id_giocatore, timeout=30)
            except TimeoutAzioneGiocatore:
                risposte.append(False)  # Nessuna risposta = non vuole continuare
                continue
            risposte.append(bool(dati.get('continue', False)))

        return all(risposte)  # Continua solo se TUTTI dicono sì

    def gestisci_disconnessione(self, id_giocatore):
        """
        Gestisce la disconnessione improvvisa di un giocatore.
        
        Notifica l'altro giocatore e assegna la vittoria per forfait.
        
        Args:
            id_giocatore: ID del giocatore disconnesso
        """
        if id_giocatore >= len(self.clients):
            return

        client = self.clients[id_giocatore]
        client['connesso'] = False
        try:
            client['canale'].close()
        except OSError:
            pass

        nome_giocatore = self.stato_gioco['giocatori'].get(id_giocatore, {}).get('nome', client['nome'])
        print(f"\n{nome_giocatore} si è disconnesso. La partita termina.")

        # Notifico l'altro giocatore
        altro_id = 1 - id_giocatore if len(self.clients) > 1 else None
        if altro_id is not None and altro_id in self.stato_gioco['giocatori']:
            vincitore = self.stato_gioco['giocatori'][altro_id]
            
            # Assegno il piatto rimasto al vincitore
            if self.stato_gioco['piatto'] > 0:
                vincitore['chips'] += self.stato_gioco['piatto']
                vincitore['statistiche']['mani_vinte'] += 1
                self.stato_gioco['piatto'] = 0

            messaggio = {
                'type': 'game_over',
                'winner': vincitore['nome'],
                'message': f"{nome_giocatore} si è disconnesso. {vincitore['nome']} vince per forfait."
            }

            try:
                self.invia_messaggio(altro_id, messaggio)
            except ConnessioneGiocatorePersa:
                pass  # Anche l'altro si è disconnesso

    # =========================================================================
    # METODI DI COMUNICAZIONE DI RETE
    # =========================================================================

    def broadcast_stato_gioco(self):
        """
        Invia lo stato corrente del gioco a tutti i giocatori.
        
        Questo metodo sincronizza i client con lo stato del server.
        Ogni giocatore riceve le stesse informazioni pubbliche
        (piatto, carte comuni, chips, ecc.)
        """
        for id_giocatore, client in enumerate(self.clients):
            if not client.get('connesso', True):
                continue  # Salto i disconnessi

            # Preparo i dati dello stato
            dati_stato = {
                'type': 'game_state',
                'phase': self.stato_gioco['fase'],
                'pot': self.stato_gioco['piatto'],
                'community_cards': [c.to_dict() for c in self.stato_gioco['carte_comuni']],
                'current_bet': self.stato_gioco['puntata_corrente'],
                'players': {},
                'your_id': id_giocatore,
                'active_player': self.stato_gioco['giocatore_attivo'],
                'dealer_button': self.stato_gioco['dealer_button']
            }

            # Aggiungo le info di ogni giocatore
            for pid, giocatore in self.stato_gioco['giocatori'].items():
                dati_stato['players'][pid] = {
                    'name': giocatore['nome'],
                    'chips': giocatore['chips'],
                    'bet': giocatore['puntata'],
                    'folded': giocatore['foldato'],
                    'all_in': giocatore['all_in'],
                    'stats': giocatore.get('statistiche', {})
                }

            self.invia_messaggio(id_giocatore, dati_stato)

    def broadcast(self, messaggio, escludi=None):
        """
        Invia un messaggio a tutti i client connessi.
        
        Args:
            messaggio: Dizionario con il messaggio da inviare
            escludi: Lista di ID giocatori da escludere (opzionale)
        """
        escludi = set(escludi or [])
        for id_giocatore, client in enumerate(self.clients):
            if id_giocatore in escludi or not client.get('connesso', True):
                continue
            self.invia_messaggio(id_giocatore, messaggio)

    def invia_messaggio(self, id_giocatore, messaggio):
        """
        Invia un messaggio JSON a un client specifico.
        
        Usa il canale JSONSocket per serializzare e inviare il messaggio.
        Se la connessione è persa, solleva un'eccezione.
        
        Args:
            id_giocatore: ID del destinatario
            messaggio: Dizionario da inviare
        """
        client = self.clients[id_giocatore]
        if not client.get('connesso', True):
            return
        try:
            client['canale'].send(messaggio)
        except ConnectionClosed as errore:
            client['connesso'] = False
            raise ConnessioneGiocatorePersa(id_giocatore) from errore

    def ricevi_messaggio(self, id_giocatore, timeout=None):
        """
        Riceve un messaggio JSON da un client con gestione timeout.
        
        Args:
            id_giocatore: ID del mittente
            timeout: Secondi di attesa massima (None = infinito)
            
        Returns:
            Dizionario con il messaggio ricevuto
            
        Raises:
            TimeoutAzioneGiocatore: Se scade il timeout
            ConnessioneGiocatorePersa: Se la connessione cade
        """
        client = self.clients[id_giocatore]
        if not client.get('connesso', True):
            raise ConnessioneGiocatorePersa(id_giocatore)

        try:
            return client['canale'].receive(timeout=timeout)
        except TimeoutError as errore:
            raise TimeoutAzioneGiocatore(id_giocatore) from errore
        except ConnectionClosed as errore:
            client['connesso'] = False
            raise ConnessioneGiocatorePersa(id_giocatore) from errore

    def chiudi(self):
        """
        Chiude tutte le connessioni e termina il server.
        
        Questo metodo viene chiamato alla fine del gioco
        per liberare le risorse di rete.
        """
        print("\nChiusura del server...")
        
        # Chiudo tutte le connessioni client
        for client in self.clients:
            try:
                client['canale'].close()
            except Exception:
                pass

        # Chiudo il socket del server
        if self.socket_server:
            self.socket_server.close()


# =============================================================================
# PUNTO DI INGRESSO DEL PROGRAMMA
# =============================================================================

if __name__ == "__main__":
    # Creo e avvio il server
    server = ServerPoker()
    
    try:
        server.avvia()
    except KeyboardInterrupt:
        # L'utente ha premuto Ctrl+C
        print("\n\nServer interrotto dall'utente")
        server.chiudi()
    except Exception as errore:
        # Errore critico
        print(f"\nErrore fatale: {errore}")
        import traceback
        traceback.print_exc()
        server.chiudi()
