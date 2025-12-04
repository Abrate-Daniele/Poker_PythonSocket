import socket     
import sys        
import os        
import time      

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poker_game import Deck, evaluate_hand, compare_hands, hand_description

from network_utils import JSONSocket, ConnectionClosed


class TimeoutAzioneGiocatore(Exception):
    """
    Eccezione sollevata quando un giocatore non compie un'azione entro il tempo limite.
    """
    pass


class ConnessioneGiocatorePersa(Exception):
    """
    Eccezione sollevata quando la connessione con un giocatore si interrompe.
    """
    def __init__(self, id_giocatore):
        self.id_giocatore = id_giocatore
        super().__init__(f"Giocatore {id_giocatore} disconnesso")


class ServerPoker:
    """
    Server per il gioco del poker Texas Hold'em per 2 giocatori.
 
    Il gioco segue le regole standard del Texas Hold'em:
    - Ogni giocatore riceve 2 carte coperte (hole cards)
    - 5 carte comuni vengono rivelate in 3 fasi: flop (3), turn (1), river (1)
    - Vince chi ha la combinazione migliore di 5 carte
    

    """

    def __init__(self, host='0.0.0.0', porta=5555):
        # Parametri di rete
        self.host = host
        self.porta = porta
        self.socket_server = None  # Socket principale del server
        
        self.clients = []
        
        self.stato_gioco = {
            'giocatori': {},        
            'mazzo': None,          
            'carte_comuni': [],    
            'piatto': 0,            
            'puntata_corrente': 0,  
            'dealer_button': 0,     
            'fase': 'attesa',       
            'giocatore_attivo': 0,  
        }
        
       
        self.piccolo_blind = 5      
        self.grande_blind = 10      
        self.chips_iniziali = 1000  
        self.timeout_azione = 45    

    def avvia(self):
        """
        Avvia il server e attende la connessione dei giocatori.
        
        Questo metodo:
        1. Crea il socket TCP del server
        2. Lo associa all'indirizzo e porta specificati
        3. Si mette in ascolto per connessioni in entrata
        4. Accetta esattamente 2 giocatori
        5. Avvia il gioco quando entrambi sono connessi
        """
        self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.socket_server.bind((self.host, self.porta))
        
        self.socket_server.listen(2)

        print(f"Server in ascolto su {self.host}:{self.porta}")
        print("In attesa di 2 giocatori...")

        while len(self.clients) < 2:
            socket_client, indirizzo = self.socket_server.accept()
            print(f"Connessione da {indirizzo}")

            canale = JSONSocket(socket_client)
            
            try:
                dati = canale.receive(timeout=10)
            except TimeoutError:
                print("Nessun messaggio di join ricevuto: connessione chiusa")
                canale.close()
                continue
            except ConnectionClosed:
                canale.close()
                continue

            if dati and dati.get('type') == 'join':
                nome_giocatore = dati.get('name', 'Sconosciuto')
                id_giocatore = len(self.clients)
                
                self.clients.append({
                    'socket': socket_client,
                    'indirizzo': indirizzo,
                    'nome': nome_giocatore,
                    'canale': canale,
                    'connesso': True
                })

                self.stato_gioco['giocatori'][id_giocatore] = {
                    'nome': nome_giocatore,
                    'chips': self.chips_iniziali,
                    'carte': [],           
                    'puntata': 0,          
                    'foldato': False,      
                    'all_in': False,       
                    'statistiche': {       
                        'mani_giocate': 0,
                        'mani_vinte': 0
                    }
                }

                self.invia_messaggio(id_giocatore, {
                    'type': 'joined',
                    'player_id': id_giocatore,
                    'message': f"Benvenuto {nome_giocatore}! Sei il giocatore {id_giocatore + 1}"
                })

                print(f"Giocatore {id_giocatore + 1}: {nome_giocatore}")
            else:
                print("Richiesta di join non valida. Chiudo la connessione.")
                canale.close()

        print("\nTutti i giocatori sono connessi. Inizio il gioco!")
        self.inizia_partita()

    def inizia_partita(self):
        try:
            while True:
                self.nuova_mano()
                self.gioca_mano()

                if not self.chiedi_continua():
                    break

                for id_giocatore, giocatore in self.stato_gioco['giocatori'].items():
                    if giocatore['chips'] <= 0:
                        id_vincitore = 1 - id_giocatore 
                        vincitore = self.stato_gioco['giocatori'][id_vincitore]
                        self.broadcast({
                            'type': 'game_over',
                            'winner': vincitore['nome'],
                            'message': f"{vincitore['nome']} ha vinto la partita!"
                        })
                        return

        except ConnessioneGiocatorePersa as errore:
            self.gestisci_disconnessione(errore.id_giocatore)
        except Exception as errore:
            print(f"Errore durante il gioco: {errore}")
            import traceback
            traceback.print_exc()
        finally:
            self.chiudi()

    def nuova_mano(self):
        print("\n" + "=" * 60)
        print("NUOVA MANO")
        print("=" * 60)

        self.stato_gioco['mazzo'] = Deck() 
        self.stato_gioco['carte_comuni'] = []
        self.stato_gioco['piatto'] = 0
        self.stato_gioco['puntata_corrente'] = 0
        self.stato_gioco['fase'] = 'pre_flop' 

        for giocatore in self.stato_gioco['giocatori'].values():
            giocatore['carte'] = []
            giocatore['puntata'] = 0
            giocatore['foldato'] = False
            giocatore['all_in'] = False
            giocatore.setdefault('statistiche', {'mani_giocate': 0, 'mani_vinte': 0})
            giocatore['statistiche']['mani_giocate'] += 1

        self.stato_gioco['dealer_button'] = 1 - self.stato_gioco['dealer_button']

        for id_giocatore in range(2):
            carte = self.stato_gioco['mazzo'].deal(2)  # Pesco 2 carte
            self.stato_gioco['giocatori'][id_giocatore]['carte'] = carte

        for id_giocatore in range(len(self.clients)):
            self.invia_messaggio(id_giocatore, {
                'type': 'deal',
                'cards': [c.to_dict() for c in self.stato_gioco['giocatori'][id_giocatore]['carte']],
                'dealer_button': self.stato_gioco['dealer_button']
            })

        self.pubblica_blind()

        time.sleep(1)
        self.broadcast_stato_gioco()

    def pubblica_blind(self):
       
        dealer = self.stato_gioco['dealer_button']
        giocatore_piccolo = dealer      
        giocatore_grande = 1 - dealer   

        importo_piccolo = min(
            self.piccolo_blind, 
            self.stato_gioco['giocatori'][giocatore_piccolo]['chips']
        )
        self.stato_gioco['giocatori'][giocatore_piccolo]['chips'] -= importo_piccolo
        self.stato_gioco['giocatori'][giocatore_piccolo]['puntata'] = importo_piccolo
        self.stato_gioco['piatto'] += importo_piccolo

        importo_grande = min(
            self.grande_blind, 
            self.stato_gioco['giocatori'][giocatore_grande]['chips']
        )
        self.stato_gioco['giocatori'][giocatore_grande]['chips'] -= importo_grande
        self.stato_gioco['giocatori'][giocatore_grande]['puntata'] = importo_grande
        self.stato_gioco['piatto'] += importo_grande

        self.stato_gioco['puntata_corrente'] = importo_grande

        self.stato_gioco['giocatore_attivo'] = dealer

        print(f"{self.stato_gioco['giocatori'][giocatore_piccolo]['nome']} paga small blind: {importo_piccolo}")
        print(f"{self.stato_gioco['giocatori'][giocatore_grande]['nome']} paga big blind: {importo_grande}")

    def gioca_mano(self):
        
        if not self.giro_puntate():
            return 

        if self.stato_gioco['fase'] == 'pre_flop':
            self.stato_gioco['carte_comuni'] = self.stato_gioco['mazzo'].deal(3)
            self.stato_gioco['fase'] = 'flop'
            print(f"\nFLOP: {self.stato_gioco['carte_comuni']}")
  
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

        self.showdown()

    def giro_puntate(self):
        for giocatore in self.stato_gioco['giocatori'].values():
            giocatore['puntata'] = 0 if self.stato_gioco['fase'] != 'pre_flop' else giocatore['puntata']

        if self.stato_gioco['fase'] != 'pre_flop':
            self.stato_gioco['puntata_corrente'] = 0
            self.stato_gioco['giocatore_attivo'] = 1 - self.stato_gioco['dealer_button']

        contatore_azioni = 0
        giocatori_agiti = set()

        while True:
            attivi_che_possono_agire = [
                pid for pid, g in self.stato_gioco['giocatori'].items()
                if not g['foldato'] and not g['all_in']
            ]
            
            if len(attivi_che_possono_agire) == 0:
                break

            if len(attivi_che_possono_agire) == 1:
                id_rimasto = attivi_che_possono_agire[0]
                rimasto = self.stato_gioco['giocatori'][id_rimasto]
                if rimasto['puntata'] >= self.stato_gioco['puntata_corrente']:
                    break

            id_giocatore = self.stato_gioco['giocatore_attivo']
            giocatore = self.stato_gioco['giocatori'][id_giocatore]

            if giocatore['foldato'] or giocatore['all_in']:
                self.stato_gioco['giocatore_attivo'] = 1 - id_giocatore
                continue

            if len(giocatori_agiti) == 2 and all(
                self.stato_gioco['giocatori'][p]['puntata'] == self.stato_gioco['puntata_corrente']
                or self.stato_gioco['giocatori'][p]['foldato']
                or self.stato_gioco['giocatori'][p]['all_in']
                for p in range(2)
            ):
                break

            self.invia_messaggio(id_giocatore, {'type': 'your_turn'})

            try:
                dati_azione = self.ricevi_messaggio(id_giocatore, timeout=self.timeout_azione)
            except TimeoutAzioneGiocatore:
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

            if azione == 'fold':
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

                giocatori_rimasti = [g for g in self.stato_gioco['giocatori'].values() if not g['foldato']]
                if len(giocatori_rimasti) == 1:
                    id_vincitore = [i for i, g in self.stato_gioco['giocatori'].items() if not g['foldato']][0]
                    self.assegna_piatto(id_vincitore, "fold")
                    return False

            elif azione == 'check':
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
                da_chiamare = self.stato_gioco['puntata_corrente'] - giocatore['puntata']
                da_chiamare = min(da_chiamare, giocatore['chips'])  # Non più di quello che ho
                
                giocatore['chips'] -= da_chiamare
                giocatore['puntata'] += da_chiamare
                self.stato_gioco['piatto'] += da_chiamare
                print(f"{giocatore['nome']} ha chiamato {da_chiamare}")

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
                rilancio_minimo = self.stato_gioco['puntata_corrente'] * 2 - giocatore['puntata']
                
                if importo < rilancio_minimo and importo < giocatore['chips']:
                    self.invia_messaggio(id_giocatore, {
                        'type': 'error',
                        'message': f'Il rilancio minimo è {rilancio_minimo}'
                    })
                    continue

                importo = min(importo, giocatore['chips'])
                giocatore['chips'] -= importo
                self.stato_gioco['piatto'] += importo
                giocatore['puntata'] += importo
                self.stato_gioco['puntata_corrente'] = giocatore['puntata']
                
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
        giocatore = self.stato_gioco['giocatori'][id_giocatore]
        if giocatore['foldato']:
            return False 

        giocatore['foldato'] = True
        giocatore['all_in'] = False

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
        print("\n" + "=" * 60)
        print("SHOWDOWN")
        print("=" * 60)

        for id_giocatore, giocatore in self.stato_gioco['giocatori'].items():
            if not giocatore['foldato']:
                print(f"\n{giocatore['nome']}: {giocatore['carte']}")

        mani = {}
        for id_giocatore, giocatore in self.stato_gioco['giocatori'].items():
            if not giocatore['foldato']:
                tutte_carte = giocatore['carte'] + self.stato_gioco['carte_comuni']
                mani[id_giocatore] = evaluate_hand(tutte_carte)
                descrizione = hand_description(tutte_carte)
                print(f"{giocatore['nome']}: {descrizione}")

        if len(mani) == 1:
            id_vincitore = list(mani.keys())[0]
        else:
            ids_giocatori = list(mani.keys())
            carte_0 = self.stato_gioco['giocatori'][ids_giocatori[0]]['carte'] + self.stato_gioco['carte_comuni']
            carte_1 = self.stato_gioco['giocatori'][ids_giocatori[1]]['carte'] + self.stato_gioco['carte_comuni']
            risultato = compare_hands(carte_0, carte_1)

            if risultato > 0:
                id_vincitore = ids_giocatori[0]
            elif risultato < 0:
                id_vincitore = ids_giocatori[1]
            else:
                self.dividi_piatto(ids_giocatori)
                return

        self.assegna_piatto(id_vincitore, "showdown")

    def assegna_piatto(self, id_vincitore, motivo):
        vincitore = self.stato_gioco['giocatori'][id_vincitore]
        vincitore['chips'] += self.stato_gioco['piatto']
        vincitore.setdefault('statistiche', {'mani_giocate': 0, 'mani_vinte': 0})
        vincitore['statistiche']['mani_vinte'] += 1

        print(f"\n{vincitore['nome']} vince {self.stato_gioco['piatto']} chips ({motivo})!")

        dati_risultato = {
            'type': 'hand_result',
            'winner_id': id_vincitore,
            'winner_name': vincitore['nome'],
            'pot': self.stato_gioco['piatto'],
            'reason': motivo,
            'all_cards': {},
            'stats': {pid: giocatore.get('statistiche', {}) for pid, giocatore in self.stato_gioco['giocatori'].items()}
        }

        for pid, giocatore in self.stato_gioco['giocatori'].items():
            dati_risultato['all_cards'][pid] = [c.to_dict() for c in giocatore['carte']]

        self.broadcast(dati_risultato)
        self.broadcast_stato_gioco()

        self.stato_gioco['piatto'] = 0

    def dividi_piatto(self, ids_giocatori):
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
        self.broadcast({'type': 'ask_continue'})

        risposte = []
        for id_giocatore in range(len(self.clients)):
            try:
                dati = self.ricevi_messaggio(id_giocatore, timeout=30)
            except TimeoutAzioneGiocatore:
                risposte.append(False) 
                continue
            risposte.append(bool(dati.get('continue', False)))

        return all(risposte) 

    def gestisci_disconnessione(self, id_giocatore):
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

        altro_id = 1 - id_giocatore if len(self.clients) > 1 else None
        if altro_id is not None and altro_id in self.stato_gioco['giocatori']:
            vincitore = self.stato_gioco['giocatori'][altro_id]
            
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
        for id_giocatore, client in enumerate(self.clients):
            if not client.get('connesso', True):
                continue

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
        escludi = set(escludi or [])
        for id_giocatore, client in enumerate(self.clients):
            if id_giocatore in escludi or not client.get('connesso', True):
                continue
            self.invia_messaggio(id_giocatore, messaggio)

    def invia_messaggio(self, id_giocatore, messaggio):
        client = self.clients[id_giocatore]
        if not client.get('connesso', True):
            return
        try:
            client['canale'].send(messaggio)
        except ConnectionClosed as errore:
            client['connesso'] = False
            raise ConnessioneGiocatorePersa(id_giocatore) from errore

    def ricevi_messaggio(self, id_giocatore, timeout=None):
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
        print("\nChiusura del server...")
        
        for client in self.clients:
            try:
                client['canale'].close()
            except Exception:
                pass

        if self.socket_server:
            self.socket_server.close()


# =============================================================================
# PUNTO DI INGRESSO DEL PROGRAMMA
# =============================================================================

if __name__ == "__main__":
    host = os.environ.get('POKER_HOST') or (sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0')
    try:
        porta = int(os.environ.get('POKER_PORT') or (sys.argv[2] if len(sys.argv) > 2 else 5555))
    except ValueError:
        porta = 5555
    server = ServerPoker(host=host, porta=porta)
    
    try:
        server.avvia()
    except KeyboardInterrupt:
        print("\n\nServer interrotto dall'utente")
        server.chiudi()
    except Exception as errore:
        print(f"\nErrore fatale: {errore}")
        import traceback
        traceback.print_exc()
        server.chiudi()
