import socket
import sys
import os
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, font as tkfont

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poker_game import Card, hand_description
from network_utils import JSONSocket, ConnectionClosed


class PokerGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("Poker - Client")
        self.root.geometry("1000x700")
        self.root.minsize(900, 640)
        self.root.configure(bg="#153e2e")

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
        frame = tk.Frame(self.root, padx=16, pady=16, bg="#1f2e2a")
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
             bg="#2e8b57", fg="black", font=self.button_font,
             activebackground="#349e6e", activeforeground="black", padx=12, pady=8, width=16)
        self.connect_btn.grid(row=3, column=0, columnspan=2, pady=12)

        self.status_label = tk.Label(frame, text="", bg="#1f2e2a", fg="#ddd")
        self.status_label.grid(row=4, column=0, columnspan=2)

        self.root.bind('<Return>', lambda e: self.connect_to_server())

    def connect_to_server(self):
        name = self.name_entry.get().strip()
        host = self.host_entry.get().strip()
        port = self.port_entry.get().strip()
        self._last_action_fold = False

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

        top = tk.Frame(self.root, pady=8, bg="#2b3a36")
        top.pack(fill='x')

        left = tk.Frame(top, bg="#2b3a36")
        left.pack(side='left', anchor='w', padx=8)
        center = tk.Frame(top, bg="#2b3a36")
        center.pack(side='left', expand=True)
        right = tk.Frame(top, bg="#2b3a36")
        right.pack(side='right', anchor='e', padx=8)

        self.my_name_label = tk.Label(left, text=self.player_name or "Tu", font=('TkDefaultFont', 10, 'bold'), bg="#2b3a36", fg="#eee")
        self.my_name_label.pack(anchor='w')
        self.my_chips_label = tk.Label(left, text="Chips: -", bg="#2b3a36", fg="#ddd")
        self.my_chips_label.pack(anchor='w')

        self.phase_label = tk.Label(center, text="Fase: -", bg="#2b3a36", fg="#eee")
        self.phase_label.pack()
        self.pot_label = tk.Label(center, text="Piatto: 0", bg="#2b3a36", fg="#eee")
        self.pot_label.pack()

        self.opponent_name_label = tk.Label(right, text="Avversario", font=('TkDefaultFont', 10, 'bold'), bg="#2b3a36", fg="#eee")
        self.opponent_name_label.pack(anchor='e')
        self.opponent_chips_label = tk.Label(right, text="Chips: -", bg="#2b3a36", fg="#ddd")
        self.opponent_chips_label.pack(anchor='e')

        self.winner_label = tk.Label(self.root, text="", fg='green', font=('TkDefaultFont', 11, 'bold'), bg="#153e2e")
        self.winner_label.pack(pady=(2, 6))

        log_frame = tk.Frame(self.root, bg="#1f2e2a")
        tk.Label(log_frame, text="Log azioni:", bg="#1f2e2a", fg="#eee").pack(anchor='w')
        self.log_text = tk.Text(log_frame, height=6, state='disabled', bg="#2b3a36", fg="#eee")
        self.log_text.pack(fill='x')

        mid = tk.Frame(self.root, pady=8, bg="#1f2e2a")
        mid.pack(fill='x')
        tk.Label(mid, text="Carte comuni:", bg="#1f2e2a", fg="#eee").pack()
        self.community_frame = tk.Frame(mid, bg="#1f2e2a")
        self.community_frame.pack()

        bottom = tk.Frame(self.root, pady=8, bg="#1f2e2a")
        bottom.pack(fill='x')
        tk.Label(bottom, text="Le tue carte:", bg="#1f2e2a", fg="#eee").pack()
        self.mycards_frame = tk.Frame(bottom, bg="#1f2e2a")
        self.mycards_frame.pack()

        self.actions_container = tk.Frame(self.root, pady=12, bg="#2b3a36")
        self.actions_container.pack(fill='x')
        self.suggestion_label = tk.Label(self.actions_container, text="", bg="#2b3a36", fg="#ffd700", font=('TkDefaultFont', 10, 'bold'))
        self.suggestion_label.pack(pady=(0,6))
        self.actions_frame = tk.Frame(self.actions_container, bg="#2b3a36")
        self.actions_frame.pack()

        log_frame.pack(fill='x', padx=8, pady=8)
        self._show_waiting()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _show_waiting(self):
        for w in self.actions_frame.winfo_children():
            w.destroy()
        tk.Label(self.actions_frame, text="In attesa...", fg="#bbb", bg="#2b3a36").pack()

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
            if self._last_action_fold and not resp:
                self.running = False
                self.cleanup_connection()
                try:
                    self.root.destroy()
                except Exception:
                    pass
            return

    def _log(self, text_line):
        try:
            self.log_text.config(state='normal')
            self.log_text.insert('end', text_line + '\n')
            self.log_text.see('end')
            self.log_text.config(state='disabled')
        except Exception:
            pass

    def update_game_display(self):
        for w in self.community_frame.winfo_children():
            w.destroy()
        for c in (self.game_state or {}).get('community_cards', []):
            card = Card.from_dict(c)
            tk.Label(self.community_frame, text=f"{card.value}{card.suit}").pack(side='left', padx=4)

        for w in self.mycards_frame.winfo_children():
            w.destroy()
        for c in self.my_cards:
            tk.Label(self.mycards_frame, text=str(c)).pack(side='left', padx=4)

        if self.game_state:
            self.phase_label.config(text=f"Fase: {self.game_state.get('phase')}")
            self.pot_label.config(text=f"Piatto: {self.game_state.get('pot',0)}")
            players = self.game_state.get('players', {})
            norm = {}
            for k, v in players.items():
                try:
                    k_int = int(k)
                except Exception:
                    k_int = k
                norm[k_int] = v

            my_info = norm.get(self.player_id)
            if my_info:
                self.my_name_label.config(text=my_info.get('name', self.player_name or 'Tu'))
                self.my_chips_label.config(text=f"Chips: {my_info.get('chips', '?')}")

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
        self._update_suggestion()

        tk.Button(self.actions_frame, text="Fold", command=lambda: self._on_fold(),
              bg="#c0392b", fg="black", activebackground="#e74c3c", activeforeground="black", padx=12, pady=6, width=12).pack(side='left', padx=6)
        tk.Button(self.actions_frame, text="Check/Call", command=lambda: self.send_action('call'),
              bg="#2980b9", fg="black", activebackground="#3498db", activeforeground="black", padx=12, pady=6, width=12).pack(side='left', padx=6)
        tk.Button(self.actions_frame, text="Raise", command=self._ask_raise,
              bg="#27ae60", fg="black", activebackground="#2ecc71", activeforeground="black", padx=12, pady=6, width=12).pack(side='left', padx=6)

    def _ask_raise(self):
        amt = simpledialog.askinteger("Raise", "Inserisci importo:")
        if amt is not None:
            self.send_action('raise', amt)

    def _on_fold(self):
        self._last_action_fold = True
        self.send_action('fold')

    def _update_suggestion(self):
        """Mostra la descrizione esatta della mano (es. 'Carta alta', 'Scala', 'Coppia di Jack')."""
        try:
            if not self.game_state:
                self.suggestion_label.config(text="")
                return
            commons = [Card.from_dict(c) for c in self.game_state.get('community_cards', [])]
            hole = self.my_cards[:]
            if not hole:
                self.suggestion_label.config(text="")
                return
            all_cards = hole + commons
            desc = hand_description(all_cards)
            self.suggestion_label.config(text=f"Suggerimento: {desc}")
        except Exception:
            self.suggestion_label.config(text="")

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
