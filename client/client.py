"""Semplice client Tkinter per Poker (versione snellita).

Questa versione rimuove styling e funzionalità non essenziali
lasciando una GUI minima per connettersi e ricevere aggiornamenti.
"""

import socket
import sys
import os
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, font as tkfont

# Assicura import locale dei moduli del progetto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poker_game import Card, hand_description
from network_utils import JSONSocket, ConnectionClosed


class PokerGUI:
    """Versione minimale dell'interfaccia client."""

    def __init__(self, root):
        self.root = root
        self.root.title("Poker - Client (semplice)")
        # Layout e colori base
        self.root.geometry("900x640")
        self.root.configure(bg="#153e2e")

        # Font semplici per migliorare la leggibilità
        self.heading_font = tkfont.Font(family="Helvetica", size=12, weight="bold")
        self.label_font = tkfont.Font(family="Helvetica", size=10)
        self.small_font = tkfont.Font(family="Helvetica", size=9)
        self.button_font = tkfont.Font(family="Helvetica", size=10, weight="bold")

        self.player_id = None
        self.player_name = ""
        self.game_state = None
        self.my_cards = []

        self.socket = None
        self.channel = None
        self.running = False

        self._build_connect_ui()

    def _build_connect_ui(self):
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.pack(fill='both', expand=True)

        tk.Label(frame, text="Nome:").grid(row=0, column=0, sticky='e')
        self.name_entry = tk.Entry(frame)
        self.name_entry.grid(row=0, column=1, pady=5)
        self.name_entry.insert(0, "Giocatore")

        tk.Label(frame, text="Server:").grid(row=1, column=0, sticky='e')
        self.host_entry = tk.Entry(frame)
        self.host_entry.grid(row=1, column=1, pady=5)
        self.host_entry.insert(0, "localhost")

        tk.Label(frame, text="Porta:").grid(row=2, column=0, sticky='e')
        self.port_entry = tk.Entry(frame)
        self.port_entry.grid(row=2, column=1, pady=5)
        self.port_entry.insert(0, "5555")

        self.connect_btn = tk.Button(frame, text="Connetti", command=self.connect_to_server,
                         bg="#2e8b57", fg="white", font=self.button_font, activebackground="#256b46")
        self.connect_btn.grid(row=3, column=0, columnspan=2, pady=10)

        self.status_label = tk.Label(frame, text="")
        self.status_label.grid(row=4, column=0, columnspan=2)

        self.root.bind('<Return>', lambda e: self.connect_to_server())

    def connect_to_server(self):
        name = self.name_entry.get().strip()
        host = self.host_entry.get().strip()
        port = self.port_entry.get().strip()

        if not name:
            self.status_label.config(text="Inserisci un nome")
            return
        try:
            port = int(port)
        except ValueError:
            self.status_label.config(text="Porta non valida")
            return

        self.player_name = name
        self.status_label.config(text=f"Connessione a {host}:{port}...")
        self.connect_btn.config(state='disabled')

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.channel = JSONSocket(self.socket)
        except Exception as e:
            self.status_label.config(text="Connessione fallita")
            self.connect_btn.config(state='normal')
            self.cleanup_connection()
            return

        self.send_message({'type': 'join', 'name': name})
        response = self.receive_message()
        if response and response.get('type') == 'joined':
            self.player_id = response['player_id']
            self.status_label.config(text="Connesso")
            self._build_game_ui()
            self.running = True
            threading.Thread(target=self.receive_messages, daemon=True).start()
        else:
            self.status_label.config(text="Impossibile unirsi")
            self.connect_btn.config(state='normal')
            self.cleanup_connection()

    def _build_game_ui(self):
        for w in self.root.winfo_children():
            w.destroy()

        # Top bar: sinistra=tu, centro=fase/piatto, destra=avversario
        top = tk.Frame(self.root, pady=8)
        top.pack(fill='x')

        left = tk.Frame(top)
        left.pack(side='left', anchor='w', padx=8)
        center = tk.Frame(top)
        center.pack(side='left', expand=True)
        right = tk.Frame(top)
        right.pack(side='right', anchor='e', padx=8)

        # Tu (sinistra)
        self.my_name_label = tk.Label(left, text=self.player_name or "Tu", font=('TkDefaultFont', 10, 'bold'))
        self.my_name_label.pack(anchor='w')
        self.my_chips_label = tk.Label(left, text="Chips: -")
        self.my_chips_label.pack(anchor='w')

        # Centro: fase e piatto
        self.phase_label = tk.Label(center, text="Fase: -")
        self.phase_label.pack()
        self.pot_label = tk.Label(center, text="Piatto: 0")
        self.pot_label.pack()

        # Avversario (destra)
        self.opponent_name_label = tk.Label(right, text="Avversario", font=('TkDefaultFont', 10, 'bold'))
        self.opponent_name_label.pack(anchor='e')
        self.opponent_chips_label = tk.Label(right, text="Chips: -")
        self.opponent_chips_label.pack(anchor='e')

        # Label per ultimo vincitore (sotto la top bar)
        self.winner_label = tk.Label(self.root, text="", fg='green', font=('TkDefaultFont', 11, 'bold'))
        self.winner_label.pack(pady=(2, 6))

        # Area log azioni giocatori
        log_frame = tk.Frame(self.root)
        log_frame.pack(fill='x', padx=8)
        tk.Label(log_frame, text="Log azioni:").pack(anchor='w')
        self.log_text = tk.Text(log_frame, height=6, state='disabled')
        self.log_text.pack(fill='x')

        mid = tk.Frame(self.root, pady=8)
        mid.pack(fill='x')
        tk.Label(mid, text="Carte comuni:").pack()
        self.community_frame = tk.Frame(mid)
        self.community_frame.pack()

        bottom = tk.Frame(self.root, pady=8)
        bottom.pack(fill='x')
        tk.Label(bottom, text="Le tue carte:").pack()
        self.mycards_frame = tk.Frame(bottom)
        self.mycards_frame.pack()

        self.actions_frame = tk.Frame(self.root, pady=8)
        self.actions_frame.pack()
        self._show_waiting()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _show_waiting(self):
        for w in self.actions_frame.winfo_children():
            w.destroy()
        tk.Label(self.actions_frame, text="In attesa...").pack()

    def receive_messages(self):
        while self.running:
            try:
                msg = self.receive_message()
                if not msg:
                    self.running = False
                    self.cleanup_connection()
                    self.root.after(0, lambda: messagebox.showerror("Errore", "Connessione persa"))
                    break
                self.root.after(0, lambda m=msg: self.handle_message(m))
            except Exception:
                if self.running:
                    self.cleanup_connection()
                break

    def handle_message(self, message):
        """Gestisce messaggi dal server e aggiorna UI (semplice)."""
        t = message.get('type')

        if t == 'player_action':
            text = message.get('message') or f"{message.get('player_name', 'Giocatore')} {message.get('action', '')}"
            if 'amount' in message:
                try:
                    amt = int(message.get('amount', 0))
                    text = f"{text} ({amt})"
                except Exception:
                    pass
            self._log(text)
            return

        if t == 'deal':
            self.my_cards = [Card.from_dict(c) for c in message.get('cards', [])]
            self.update_game_display()
            return

        if t == 'game_state':
            self.player_id = message.get('your_id', self.player_id)
            self.game_state = message
            self.update_game_display()
            return

        if t == 'your_turn':
            self.show_action_buttons()
            return

        if t == 'hand_result':
            winner = message.get('winner_name') or message.get('winner') or 'Pareggio'
            pot = message.get('pot')
            reason = message.get('reason')
            text = f"{winner} vince {pot}" if pot is not None else f"{winner}"
            if reason:
                text += f" ({reason})"
            messagebox.showinfo("Risultato mano", text)
            try:
                if pot is not None:
                    self.winner_label.config(text=f"Ultimo vincitore: {winner} (+{pot})")
                else:
                    self.winner_label.config(text=f"Ultimo vincitore: {winner}")
            except Exception:
                pass
            return

        if t == 'game_over':
            info = message.get('message', '') or f"Vincitore: {message.get('winner', '')}"
            if self.game_state and 'players' in self.game_state:
                players = self.game_state.get('players', {})
                s = "\n\nConti finali:\n"
                for pid, p in players.items():
                    name = p.get('name', f'Giocatore {pid}')
                    chips = p.get('chips', '?')
                    s += f"  {name}: {chips}\n"
                info += s
            messagebox.showinfo("Fine partita", info)
            try:
                winner_display = message.get('winner') or message.get('winner_name') or ''
                if winner_display:
                    self.winner_label.config(text=f"Vincitore della partita: {winner_display}")
            except Exception:
                pass
            self.running = False
            return

        if t == 'error':
            messagebox.showerror("Errore", message.get('message', ''))
            return

        if t == 'ask_continue':
            resp = messagebox.askyesno("Continua?", "Vuoi giocare un'altra mano?")
            try:
                self.send_message({'continue': resp})
            except Exception:
                pass
            return

    def _log(self, text_line):
        """Aggiunge una riga al log delle azioni in modo thread-safe."""
        try:
            self.log_text.config(state='normal')
            self.log_text.insert('end', text_line + '\n')
            self.log_text.see('end')
            self.log_text.config(state='disabled')
        except Exception:
            pass

    def update_game_display(self):
        # Aggiorna carte comuni
        for w in self.community_frame.winfo_children():
            w.destroy()
        for c in (self.game_state or {}).get('community_cards', []):
            card = Card.from_dict(c)
            tk.Label(self.community_frame, text=f"{card.value}{card.suit}").pack(side='left', padx=4)

        # Le mie carte
        for w in self.mycards_frame.winfo_children():
            w.destroy()
        for c in self.my_cards:
            tk.Label(self.mycards_frame, text=str(c)).pack(side='left', padx=4)

        if self.game_state:
            self.phase_label.config(text=f"Fase: {self.game_state.get('phase')}")
            self.pot_label.config(text=f"Piatto: {self.game_state.get('pot',0)}")
            # Aggiorna nomi e chips dei giocatori se presenti
            players = self.game_state.get('players', {})
            # Normalizza chiavi (possono essere stringhe)
            norm = {}
            for k, v in players.items():
                try:
                    k_int = int(k)
                except Exception:
                    k_int = k
                norm[k_int] = v

            # Aggiorna informazioni personali
            my_info = norm.get(self.player_id)
            if my_info:
                self.my_name_label.config(text=my_info.get('name', self.player_name or 'Tu'))
                self.my_chips_label.config(text=f"Chips: {my_info.get('chips', '?')}")

            # Trova avversario
            opponent_info = None
            for pid, info in norm.items():
                if pid != self.player_id:
                    opponent_info = info
                    break
            if opponent_info:
                self.opponent_name_label.config(text=opponent_info.get('name', 'Avversario'))
                self.opponent_chips_label.config(text=f"Chips: {opponent_info.get('chips', '?')}")

    def show_action_buttons(self):
        for w in self.actions_frame.winfo_children():
            w.destroy()

        tk.Button(self.actions_frame, text="Fold", command=lambda: self.send_action('fold')).pack(side='left', padx=5)
        tk.Button(self.actions_frame, text="Check/Call", command=lambda: self.send_action('call')).pack(side='left', padx=5)
        tk.Button(self.actions_frame, text="Raise", command=self._ask_raise).pack(side='left', padx=5)

    def _ask_raise(self):
        amt = simpledialog.askinteger("Raise", "Inserisci importo:")
        if amt is not None:
            self.send_action('raise', amt)

    def send_action(self, action, amount=None):
        msg = {'action': action}
        if amount is not None:
            msg['amount'] = amount
        self.send_message(msg)
        self._show_waiting()

    def send_message(self, message):
        if not self.channel:
            return
        try:
            self.channel.send(message)
        except ConnectionClosed:
            self.running = False

    def receive_message(self):
        if not self.channel:
            return None
        try:
            return self.channel.receive()
        except ConnectionClosed:
            return None

    def cleanup_connection(self):
        try:
            if self.channel:
                self.channel.close()
        except Exception:
            pass
        try:
            if self.socket:
                self.socket.close()
        except Exception:
            pass
        self.channel = None
        self.socket = None

    def on_closing(self):
        if messagebox.askokcancel("Esci", "Vuoi uscire?"):
            self.running = False
            self.cleanup_connection()
            self.root.destroy()


def main():
    root = tk.Tk()
    app = PokerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
