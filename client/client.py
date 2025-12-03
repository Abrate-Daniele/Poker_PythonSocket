"""
Client per il gioco del poker tramite socket con interfaccia Tkinter.
Permette di connettersi al server e giocare a poker con una GUI migliorata.
"""

import socket
import sys
import os
import threading
import tkinter as tk
from tkinter import messagebox, font as tkfont

# Aggiungi la directory parent al path per importare poker_game
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poker_game import Card, hand_description
from network_utils import JSONSocket, ConnectionClosed


class PokerGUI:
    """Interfaccia grafica Tkinter per il gioco del poker"""

    # Palette colori
    DARK_GREEN = "#0a4d1c"
    TABLE_GREEN = "#116530"
    FELT_GREEN = "#1a8b47"
    GOLD = "#ffd700"
    GOLD_DARK = "#b8960f"
    WHITE = "#ffffff"
    OFF_WHITE = "#f0f0f0"
    CARD_SHADOW = "#0a3012"
    
    # Colori bottoni
    BTN_FOLD = "#c0392b"
    BTN_FOLD_HOVER = "#e74c3c"
    BTN_CHECK = "#f39c12"
    BTN_CHECK_HOVER = "#f1c40f"
    BTN_CALL = "#2980b9"
    BTN_CALL_HOVER = "#3498db"
    BTN_RAISE = "#27ae60"
    BTN_RAISE_HOVER = "#2ecc71"
    BTN_ALLIN = "#8e44ad"
    BTN_ALLIN_HOVER = "#9b59b6"
    
    # Colori carte
    CARD_RED = "#e74c3c"
    CARD_BLACK = "#2c3e50"

    # Timeout per turno (sincronizzato con server)
    TURN_TIMEOUT = 45

    def __init__(self, root):
        self.root = root
        self.root.title("♠ Poker Texas Hold'em ♥")
        self.root.geometry("1100x750")
        self.root.configure(bg=self.DARK_GREEN)
        self.root.resizable(True, True)
        self.root.minsize(900, 650)

        # Font personalizzati
        self.title_font = tkfont.Font(family="Helvetica", size=36, weight="bold")
        self.heading_font = tkfont.Font(family="Helvetica", size=18, weight="bold")
        self.label_font = tkfont.Font(family="Helvetica", size=13)
        self.card_font = tkfont.Font(family="Arial", size=24, weight="bold")
        self.button_font = tkfont.Font(family="Helvetica", size=13, weight="bold")
        self.small_font = tkfont.Font(family="Helvetica", size=11)

        # Stato
        self.player_id = None
        self.player_name = ""
        self.game_state = None
        self.my_cards = []
        self.running = False
        self.socket = None
        self.channel = None
        
        # Timer
        self.timer_seconds = 0
        self.timer_job = None
        self.is_my_turn = False

        # Slider raise
        self.raise_var = tk.IntVar(value=0)

        self.create_connection_screen()

    def create_connection_screen(self):
        """Schermata di connessione con design moderno"""
        self.connection_frame = tk.Frame(self.root, bg=self.DARK_GREEN)
        self.connection_frame.pack(expand=True, fill='both')

        # Container centrale
        center_frame = tk.Frame(self.connection_frame, bg=self.TABLE_GREEN, padx=60, pady=40)
        center_frame.place(relx=0.5, rely=0.5, anchor='center')

        # Titolo con simboli carte
        title = tk.Label(
            center_frame,
            text="♠ ♥ POKER ♦ ♣",
            font=self.title_font,
            bg=self.TABLE_GREEN,
            fg=self.GOLD
        )
        title.pack(pady=(0, 5))

        subtitle = tk.Label(
            center_frame,
            text="Texas Hold'em",
            font=self.heading_font,
            bg=self.TABLE_GREEN,
            fg=self.WHITE
        )
        subtitle.pack(pady=(0, 30))

        # Form container
        form_frame = tk.Frame(center_frame, bg=self.TABLE_GREEN)
        form_frame.pack(pady=10)

        # Stile comune per le entry
        entry_style = {'font': self.label_font, 'width': 22, 'relief': 'flat', 
                       'highlightthickness': 2, 'highlightcolor': self.GOLD,
                       'highlightbackground': self.FELT_GREEN}

        # Nome
        self._create_form_row(form_frame, "👤 Nome", 0)
        self.name_entry = tk.Entry(form_frame, **entry_style)
        self.name_entry.grid(row=0, column=1, padx=15, pady=12)
        self.name_entry.insert(0, "Giocatore")

        # Server
        self._create_form_row(form_frame, "🖥️ Server", 1)
        self.host_entry = tk.Entry(form_frame, **entry_style)
        self.host_entry.grid(row=1, column=1, padx=15, pady=12)
        self.host_entry.insert(0, "localhost")

        # Porta
        self._create_form_row(form_frame, "🔌 Porta", 2)
        self.port_entry = tk.Entry(form_frame, **entry_style)
        self.port_entry.grid(row=2, column=1, padx=15, pady=12)
        self.port_entry.insert(0, "5555")

        # Bottone connetti
        self.connect_btn = tk.Button(
            center_frame,
            text="🎮  ENTRA NEL GIOCO",
            font=self.button_font,
            bg=self.GOLD,
            fg=self.DARK_GREEN,
            activebackground=self.GOLD_DARK,
            activeforeground=self.DARK_GREEN,
            cursor="hand2",
            relief='flat',
            padx=40,
            pady=15,
            command=self.connect_to_server
        )
        self.connect_btn.pack(pady=30)
        self._add_button_hover(self.connect_btn, self.GOLD, self.GOLD_DARK)

        # Status
        self.status_label = tk.Label(
            center_frame,
            text="",
            font=self.small_font,
            bg=self.TABLE_GREEN,
            fg=self.GOLD
        )
        self.status_label.pack(pady=5)

        # Bind Enter key
        self.root.bind('<Return>', lambda e: self.connect_to_server())

    def _create_form_row(self, parent, label_text, row):
        """Crea una riga del form"""
        tk.Label(
            parent,
            text=label_text,
            font=self.label_font,
            bg=self.TABLE_GREEN,
            fg=self.WHITE,
            anchor='e',
            width=10
        ).grid(row=row, column=0, padx=15, pady=12, sticky='e')

    def _add_button_hover(self, button, normal_bg, hover_bg, normal_fg=None, hover_fg=None):
        """Aggiunge effetto hover ai bottoni"""
        normal_fg = normal_fg or button.cget('fg')
        hover_fg = hover_fg or normal_fg
        
        def on_enter(e):
            button.config(bg=hover_bg, fg=hover_fg)
        
        def on_leave(e):
            button.config(bg=normal_bg, fg=normal_fg)
        
        button.bind('<Enter>', on_enter)
        button.bind('<Leave>', on_leave)

    def connect_to_server(self):
        """Connette al server"""
        name = self.name_entry.get().strip()
        host = self.host_entry.get().strip()
        port = self.port_entry.get().strip()

        if not name:
            self.status_label.config(text="⚠️ Inserisci un nome!", fg="#e74c3c")
            return

        try:
            port = int(port)
        except ValueError:
            self.status_label.config(text="⚠️ Porta non valida!", fg="#e74c3c")
            return

        self.player_name = name
        self.status_label.config(text=f"⏳ Connessione a {host}:{port}...", fg=self.GOLD)
        self.connect_btn.config(state='disabled')
        self.root.update()

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.channel = JSONSocket(self.socket)
        except Exception as e:
            self.status_label.config(text=f"❌ Connessione fallita", fg="#e74c3c")
            self.connect_btn.config(state='normal')
            self.cleanup_connection()
            return

        self.send_message({'type': 'join', 'name': name})
        response = self.receive_message()
        
        if response and response.get('type') == 'joined':
            self.player_id = response['player_id']
            self.status_label.config(text="✅ Connesso! In attesa dell'avversario...", fg="#2ecc71")
            self.root.update()
            
            self.running = True
            threading.Thread(target=self.receive_messages, daemon=True).start()
            self.root.after(500, self.create_game_screen)
        else:
            self.status_label.config(text="❌ Impossibile unirsi al gioco", fg="#e74c3c")
            self.connect_btn.config(state='normal')
            self.cleanup_connection()

    def create_game_screen(self):
        """Schermata di gioco principale"""
        self.connection_frame.destroy()
        self.root.unbind('<Return>')

        # Container principale
        self.main_frame = tk.Frame(self.root, bg=self.TABLE_GREEN)
        self.main_frame.pack(expand=True, fill='both', padx=15, pady=15)

        # === AREA AVVERSARIO (top) ===
        self.opponent_frame = self._create_player_bar(self.main_frame, is_opponent=True)
        self.opponent_frame.pack(fill='x', pady=(0, 10))

        # === TAVOLO CENTRALE ===
        table_container = tk.Frame(self.main_frame, bg=self.FELT_GREEN, relief='ridge', bd=4)
        table_container.pack(expand=True, fill='both', pady=5)

        # Fase del gioco
        phase_frame = tk.Frame(table_container, bg=self.FELT_GREEN)
        phase_frame.pack(fill='x', pady=(15, 5))
        
        self.phase_label = tk.Label(
            phase_frame,
            text="🎯 IN ATTESA",
            font=self.heading_font,
            bg=self.FELT_GREEN,
            fg=self.GOLD
        )
        self.phase_label.pack()

        # Carte comuni
        community_frame = tk.Frame(table_container, bg=self.FELT_GREEN)
        community_frame.pack(expand=True, fill='both', pady=10)
        
        tk.Label(
            community_frame,
            text="CARTE COMUNI",
            font=self.small_font,
            bg=self.FELT_GREEN,
            fg=self.OFF_WHITE
        ).pack(pady=(10, 5))

        self.community_cards_frame = tk.Frame(community_frame, bg=self.FELT_GREEN)
        self.community_cards_frame.pack(pady=10)
        self._show_empty_community_cards()

        # Piatto
        pot_frame = tk.Frame(table_container, bg=self.FELT_GREEN)
        pot_frame.pack(pady=10)

        self.pot_label = tk.Label(
            pot_frame,
            text="💰 PIATTO: 0",
            font=self.heading_font,
            bg=self.DARK_GREEN,
            fg=self.GOLD,
            padx=30,
            pady=8,
            relief='ridge',
            bd=2
        )
        self.pot_label.pack()

        self.current_bet_label = tk.Label(
            pot_frame,
            text="Puntata da chiamare: 0",
            font=self.small_font,
            bg=self.FELT_GREEN,
            fg=self.OFF_WHITE
        )
        self.current_bet_label.pack(pady=5)

        # Le tue carte
        my_cards_container = tk.Frame(table_container, bg=self.FELT_GREEN)
        my_cards_container.pack(pady=10)

        tk.Label(
            my_cards_container,
            text="LE TUE CARTE",
            font=self.small_font,
            bg=self.FELT_GREEN,
            fg=self.OFF_WHITE
        ).pack(pady=(10, 5))

        self.my_cards_frame = tk.Frame(my_cards_container, bg=self.FELT_GREEN)
        self.my_cards_frame.pack(pady=5)

        self.hand_eval_label = tk.Label(
            my_cards_container,
            text="",
            font=self.label_font,
            bg=self.FELT_GREEN,
            fg="#2ecc71"
        )
        self.hand_eval_label.pack(pady=5)

        # === AREA GIOCATORE (bottom) ===
        self.player_frame = self._create_player_bar(self.main_frame, is_opponent=False)
        self.player_frame.pack(fill='x', pady=(10, 0))

        # === AREA AZIONI ===
        self.actions_container = tk.Frame(self.main_frame, bg=self.TABLE_GREEN)
        self.actions_container.pack(fill='x', pady=10)

        self.actions_frame = tk.Frame(self.actions_container, bg=self.TABLE_GREEN)
        self.actions_frame.pack()

        self._show_waiting_message()

    def _create_player_bar(self, parent, is_opponent=False):
        """Crea barra info giocatore"""
        frame = tk.Frame(parent, bg=self.DARK_GREEN, relief='ridge', bd=2)
        
        inner = tk.Frame(frame, bg=self.DARK_GREEN, padx=15, pady=10)
        inner.pack(fill='x')

        # Nome e indicatore turno
        name_frame = tk.Frame(inner, bg=self.DARK_GREEN)
        name_frame.pack(side='left')

        if is_opponent:
            self.opponent_turn_indicator = tk.Label(name_frame, text="", font=("Arial", 16), bg=self.DARK_GREEN, fg=self.GOLD)
            self.opponent_turn_indicator.pack(side='left')
            self.opponent_name_label = tk.Label(name_frame, text="Avversario", font=self.label_font, bg=self.DARK_GREEN, fg=self.WHITE)
            self.opponent_name_label.pack(side='left', padx=5)
            self.opponent_dealer_label = tk.Label(name_frame, text="", font=self.small_font, bg=self.DARK_GREEN, fg=self.GOLD)
            self.opponent_dealer_label.pack(side='left', padx=3)
        else:
            self.player_turn_indicator = tk.Label(name_frame, text="", font=("Arial", 16), bg=self.DARK_GREEN, fg=self.GOLD)
            self.player_turn_indicator.pack(side='left')
            self.player_name_label = tk.Label(name_frame, text=f"👤 {self.player_name}", font=self.label_font, bg=self.DARK_GREEN, fg=self.WHITE)
            self.player_name_label.pack(side='left', padx=5)
            self.player_dealer_label = tk.Label(name_frame, text="", font=self.small_font, bg=self.DARK_GREEN, fg=self.GOLD)
            self.player_dealer_label.pack(side='left', padx=3)

        # Stats a destra
        stats_frame = tk.Frame(inner, bg=self.DARK_GREEN)
        stats_frame.pack(side='right')

        if is_opponent:
            self.opponent_status_label = tk.Label(stats_frame, text="", font=self.label_font, bg=self.DARK_GREEN, fg="#e74c3c")
            self.opponent_status_label.pack(side='right', padx=10)
            self.opponent_stats_label = tk.Label(stats_frame, text="📊 0/0", font=self.small_font, bg=self.DARK_GREEN, fg=self.OFF_WHITE)
            self.opponent_stats_label.pack(side='right', padx=10)
            self.opponent_bet_label = tk.Label(stats_frame, text="🎯 0", font=self.label_font, bg=self.DARK_GREEN, fg=self.GOLD)
            self.opponent_bet_label.pack(side='right', padx=10)
            self.opponent_chips_label = tk.Label(stats_frame, text="💰 1000", font=self.label_font, bg=self.DARK_GREEN, fg=self.GOLD)
            self.opponent_chips_label.pack(side='right', padx=10)
        else:
            self.player_stats_label = tk.Label(stats_frame, text="📊 0/0", font=self.small_font, bg=self.DARK_GREEN, fg=self.OFF_WHITE)
            self.player_stats_label.pack(side='right', padx=10)
            self.player_bet_label = tk.Label(stats_frame, text="🎯 0", font=self.label_font, bg=self.DARK_GREEN, fg=self.GOLD)
            self.player_bet_label.pack(side='right', padx=10)
            self.player_chips_label = tk.Label(stats_frame, text="💰 1000", font=self.label_font, bg=self.DARK_GREEN, fg=self.GOLD)
            self.player_chips_label.pack(side='right', padx=10)
            
            # Timer
            self.timer_label = tk.Label(stats_frame, text="", font=self.heading_font, bg=self.DARK_GREEN, fg=self.GOLD)
            self.timer_label.pack(side='right', padx=15)

        return frame

    def _show_empty_community_cards(self):
        """Mostra placeholder per carte comuni"""
        for widget in self.community_cards_frame.winfo_children():
            widget.destroy()
        
        for i in range(5):
            self._draw_card_placeholder(self.community_cards_frame)

    def _draw_card_placeholder(self, parent):
        """Disegna placeholder carta"""
        frame = tk.Frame(parent, bg="#0d3d1a", width=65, height=95, relief='ridge', bd=2)
        frame.pack(side='left', padx=4)
        frame.pack_propagate(False)
        
        tk.Label(frame, text="?", font=("Arial", 28), bg="#0d3d1a", fg="#1a5c2e").place(relx=0.5, rely=0.5, anchor='center')
        return frame

    def draw_card(self, parent, card, size="normal", animate=False):
        """Disegna una carta"""
        if size == "normal":
            width, height = 65, 95
            value_font = ("Arial", 22, "bold")
            suit_font = ("Arial", 18)
        else:
            width, height = 50, 75
            value_font = ("Arial", 16, "bold")
            suit_font = ("Arial", 14)

        # Colore in base al seme
        if card:
            suit_color = self.CARD_RED if card.suit in ['♥', '♦'] else self.CARD_BLACK
            bg_color = self.WHITE
        else:
            suit_color = self.WHITE
            bg_color = "#2c3e82"

        frame = tk.Frame(parent, bg=bg_color, width=width, height=height, relief='raised', bd=2)
        frame.pack(side='left', padx=4)
        frame.pack_propagate(False)

        if card:
            # Valore
            tk.Label(
                frame, text=card.value, font=value_font, bg=bg_color, fg=suit_color
            ).place(relx=0.5, rely=0.35, anchor='center')
            
            # Seme
            tk.Label(
                frame, text=card.suit, font=suit_font, bg=bg_color, fg=suit_color
            ).place(relx=0.5, rely=0.7, anchor='center')
        else:
            # Dorso carta
            tk.Label(
                frame, text="🂠", font=("Arial", 32), bg=bg_color, fg=self.WHITE
            ).place(relx=0.5, rely=0.5, anchor='center')

        return frame

    def _show_waiting_message(self, text="In attesa dell'avversario..."):
        """Mostra messaggio di attesa"""
        for widget in self.actions_frame.winfo_children():
            widget.destroy()
        
        tk.Label(
            self.actions_frame,
            text=text,
            font=self.label_font,
            bg=self.TABLE_GREEN,
            fg=self.OFF_WHITE
        ).pack(pady=15)

    def update_game_display(self):
        """Aggiorna visualizzazione"""
        if not self.game_state:
            return

        state = self.game_state

        # Fase
        phase_icons = {
            'pre_flop': '🃏 PRE-FLOP',
            'flop': '🎴 FLOP',
            'turn': '🎯 TURN',
            'river': '🏆 RIVER',
            'showdown': '👀 SHOWDOWN',
            'waiting': '⏳ IN ATTESA'
        }
        self.phase_label.config(text=phase_icons.get(state['phase'], state['phase'].upper()))

        # Piatto
        self.pot_label.config(text=f"💰 PIATTO: {state['pot']}")
        self.current_bet_label.config(text=f"Puntata da chiamare: {state['current_bet']}")

        # Carte comuni
        for widget in self.community_cards_frame.winfo_children():
            widget.destroy()

        cards_shown = 0
        if state['community_cards']:
            for card_data in state['community_cards']:
                card = Card.from_dict(card_data)
                self.draw_card(self.community_cards_frame, card)
                cards_shown += 1
        
        # Placeholder per carte restanti
        for _ in range(5 - cards_shown):
            self._draw_card_placeholder(self.community_cards_frame)

        # Le mie carte
        for widget in self.my_cards_frame.winfo_children():
            widget.destroy()

        if self.my_cards:
            for card in self.my_cards:
                self.draw_card(self.my_cards_frame, card)
            
            if len(state['community_cards']) >= 3:
                all_cards = self.my_cards + [Card.from_dict(c) for c in state['community_cards']]
                desc = hand_description(all_cards)
                self.hand_eval_label.config(text=f"🎯 {desc}")
            else:
                self.hand_eval_label.config(text="")
        else:
            self.hand_eval_label.config(text="")

        # Info giocatori
        for pid, player in state['players'].items():
            try:
                pid_int = int(pid)
            except (TypeError, ValueError):
                pid_int = pid

            is_me = (pid_int == self.player_id)
            is_active = (pid_int == state['active_player'])
            is_dealer = (pid_int == state['dealer_button'])
            
            stats = player.get('stats', {})
            wins = stats.get('hands_won', 0)
            played = stats.get('hands_played', 0)

            if is_me:
                self.player_chips_label.config(text=f"💰 {player['chips']}")
                self.player_bet_label.config(text=f"🎯 {player['bet']}")
                self.player_stats_label.config(text=f"📊 {wins}/{played}")
                self.player_dealer_label.config(text="🎲 DEALER" if is_dealer else "")
                self.player_turn_indicator.config(text="▶ " if is_active else "")
            else:
                self.opponent_name_label.config(text=f"👤 {player['name']}")
                self.opponent_chips_label.config(text=f"💰 {player['chips']}")
                self.opponent_bet_label.config(text=f"🎯 {player['bet']}")
                self.opponent_stats_label.config(text=f"📊 {wins}/{played}")
                self.opponent_dealer_label.config(text="🎲 DEALER" if is_dealer else "")
                self.opponent_turn_indicator.config(text="▶ " if is_active else "")
                
                status = ""
                if player['folded']:
                    status = "❌ FOLD"
                elif player['all_in']:
                    status = "🔥 ALL-IN"
                self.opponent_status_label.config(text=status)

    def show_action_buttons(self):
        """Mostra bottoni azione con slider raise"""
        if not self.game_state:
            return

        self.is_my_turn = True
        self._start_timer()

        for widget in self.actions_frame.winfo_children():
            widget.destroy()

        player = self.game_state['players'][self.player_id]
        current_bet = self.game_state['current_bet']
        to_call = current_bet - player['bet']
        my_chips = player['chips']

        # Turno label
        tk.Label(
            self.actions_frame,
            text="🎲 È IL TUO TURNO!",
            font=self.heading_font,
            bg=self.TABLE_GREEN,
            fg=self.GOLD
        ).pack(pady=(5, 15))

        # Container bottoni
        buttons_frame = tk.Frame(self.actions_frame, bg=self.TABLE_GREEN)
        buttons_frame.pack(pady=10)

        # Stile bottoni - più grandi e visibili
        btn_config = {
            'font': tkfont.Font(family="Helvetica", size=15, weight="bold"),
            'cursor': 'hand2',
            'relief': 'raised',
            'padx': 35,
            'pady': 15,
            'bd': 3,
            'width': 12
        }

        # FOLD
        if to_call > 0:
            fold_btn = tk.Button(
                buttons_frame, text="❌ FOLD", bg=self.BTN_FOLD, fg=self.WHITE,
                activebackground=self.BTN_FOLD_HOVER, activeforeground=self.WHITE,
                command=lambda: self.send_action('fold'), **btn_config
            )
            fold_btn.pack(side='left', padx=10, pady=5)
            self._add_button_hover(fold_btn, self.BTN_FOLD, self.BTN_FOLD_HOVER)

        # CHECK
        if to_call == 0:
            check_btn = tk.Button(
                buttons_frame, text="✓ CHECK", bg=self.BTN_CHECK, fg=self.WHITE,
                activebackground=self.BTN_CHECK_HOVER, activeforeground=self.WHITE,
                command=lambda: self.send_action('check'), **btn_config
            )
            check_btn.pack(side='left', padx=10, pady=5)
            self._add_button_hover(check_btn, self.BTN_CHECK, self.BTN_CHECK_HOVER)

        # CALL
        if to_call > 0 and my_chips >= to_call:
            call_btn = tk.Button(
                buttons_frame, text=f"📞 CALL {to_call}", bg=self.BTN_CALL, fg=self.WHITE,
                activebackground=self.BTN_CALL_HOVER, activeforeground=self.WHITE,
                command=lambda: self.send_action('call'), **btn_config
            )
            call_btn.pack(side='left', padx=10, pady=5)
            self._add_button_hover(call_btn, self.BTN_CALL, self.BTN_CALL_HOVER)

        # RAISE con slider
        min_raise = max(current_bet * 2 - player['bet'], to_call + self.game_state.get('big_blind', 10))
        if my_chips > to_call and my_chips >= min_raise:
            raise_frame = tk.Frame(self.actions_frame, bg=self.TABLE_GREEN)
            raise_frame.pack(pady=10)

            self.raise_var.set(min_raise)

            # Label valore
            self.raise_value_label = tk.Label(
                raise_frame,
                text=f"Rilancio: {min_raise}",
                font=self.label_font,
                bg=self.TABLE_GREEN,
                fg=self.WHITE
            )
            self.raise_value_label.pack()

            # Slider
            slider_frame = tk.Frame(raise_frame, bg=self.TABLE_GREEN)
            slider_frame.pack(pady=5)

            tk.Label(slider_frame, text=f"{min_raise}", font=self.small_font, bg=self.TABLE_GREEN, fg=self.OFF_WHITE).pack(side='left', padx=5)
            
            self.raise_slider = tk.Scale(
                slider_frame,
                from_=min_raise,
                to=my_chips,
                orient='horizontal',
                length=250,
                showvalue=False,
                variable=self.raise_var,
                command=self._update_raise_label,
                bg=self.FELT_GREEN,
                fg=self.WHITE,
                troughcolor=self.DARK_GREEN,
                highlightthickness=0
            )
            self.raise_slider.pack(side='left', padx=5)
            
            tk.Label(slider_frame, text=f"{my_chips}", font=self.small_font, bg=self.TABLE_GREEN, fg=self.OFF_WHITE).pack(side='left', padx=5)

            # Bottoni raise e all-in
            raise_btns = tk.Frame(raise_frame, bg=self.TABLE_GREEN)
            raise_btns.pack(pady=15)

            raise_btn = tk.Button(
                raise_btns, text="📈 RAISE", bg=self.BTN_RAISE, fg=self.WHITE,
                activebackground=self.BTN_RAISE_HOVER, activeforeground=self.WHITE,
                command=lambda: self.send_action('raise', self.raise_var.get()), **btn_config
            )
            raise_btn.pack(side='left', padx=10, pady=5)
            self._add_button_hover(raise_btn, self.BTN_RAISE, self.BTN_RAISE_HOVER)

            allin_btn = tk.Button(
                raise_btns, text=f"🔥 ALL-IN ({my_chips})", bg=self.BTN_ALLIN, fg=self.WHITE,
                activebackground=self.BTN_ALLIN_HOVER, activeforeground=self.WHITE,
                command=lambda: self.send_action('raise', my_chips), **btn_config
            )
            allin_btn.pack(side='left', padx=10, pady=5)
            self._add_button_hover(allin_btn, self.BTN_ALLIN, self.BTN_ALLIN_HOVER)

        elif my_chips > 0 and my_chips <= to_call:
            # Solo all-in disponibile
            allin_btn = tk.Button(
                buttons_frame, text=f"🔥 ALL-IN ({my_chips})", bg=self.BTN_ALLIN, fg=self.WHITE,
                activebackground=self.BTN_ALLIN_HOVER, activeforeground=self.WHITE,
                command=lambda: self.send_action('raise', my_chips), **btn_config
            )
            allin_btn.pack(side='left', padx=10, pady=5)
            self._add_button_hover(allin_btn, self.BTN_ALLIN, self.BTN_ALLIN_HOVER)

    def _update_raise_label(self, val):
        """Aggiorna label del raise"""
        self.raise_value_label.config(text=f"Rilancio: {int(float(val))}")

    def _start_timer(self):
        """Avvia timer turno"""
        self._stop_timer()
        self.timer_seconds = self.TURN_TIMEOUT
        self._update_timer()

    def _stop_timer(self):
        """Ferma timer"""
        if self.timer_job:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None
        self.timer_label.config(text="")
        self.is_my_turn = False

    def _update_timer(self):
        """Aggiorna display timer"""
        if not self.is_my_turn:
            return
        
        if self.timer_seconds <= 0:
            self.timer_label.config(text="⏰ 0s", fg="#e74c3c")
            return
        
        color = self.GOLD if self.timer_seconds > 10 else "#e74c3c"
        self.timer_label.config(text=f"⏰ {self.timer_seconds}s", fg=color)
        self.timer_seconds -= 1
        self.timer_job = self.root.after(1000, self._update_timer)

    def send_action(self, action, amount=None):
        """Invia azione al server"""
        self._stop_timer()
        
        message = {'action': action}
        if amount is not None:
            message['amount'] = amount

        self.send_message(message)
        self._show_waiting_message()

    def receive_messages(self):
        """Thread ricezione messaggi"""
        while self.running:
            try:
                message = self.receive_message()
                if not message:
                    self.running = False
                    self.cleanup_connection()
                    self.root.after(0, lambda: messagebox.showerror("Errore", "Connessione al server persa"))
                    break
                self.root.after(0, lambda msg=message: self.handle_message(msg))
            except Exception as e:
                if self.running:
                    print(f"Errore ricezione: {e}")
                    self.cleanup_connection()
                break

    def handle_message(self, message):
        """Gestisce messaggi dal server"""
        msg_type = message.get('type')

        if msg_type == 'deal':
            self.my_cards = [Card.from_dict(c) for c in message['cards']]
            # Non mostrare messagebox, la UI si aggiorna automaticamente

        elif msg_type == 'game_state':
            message['players'] = self._normalize_player_keys(message.get('players', {}))
            self.game_state = message
            self.update_game_display()

        elif msg_type == 'your_turn':
            self.show_action_buttons()

        elif msg_type == 'hand_result':
            self._stop_timer()
            message['all_cards'] = self._normalize_player_keys(message.get('all_cards', {}))
            if 'stats' in message:
                message['stats'] = self._normalize_player_keys(message.get('stats', {}))
            self.display_hand_result(message)

        elif msg_type == 'ask_continue':
            self._stop_timer()
            self.ask_continue()

        elif msg_type == 'game_over':
            self._stop_timer()
            messagebox.showinfo("🏆 Fine Partita", message['message'])
            self.running = False
            self.root.quit()

        elif msg_type == 'error':
            messagebox.showerror("Errore", message['message'])

        elif msg_type == 'player_action':
            if message.get('action') == 'forced_fold':
                self._stop_timer()
                # Toast notification invece di messagebox
                self._show_toast(message.get('message', 'Fold forzato'))

        elif msg_type == 'phase_change':
            pass  # Già gestito da game_state

    def _show_toast(self, message, duration=3000):
        """Mostra notifica temporanea"""
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes('-topmost', True)
        
        # Posiziona in alto al centro
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - 150
        y = self.root.winfo_y() + 100
        toast.geometry(f"300x50+{x}+{y}")
        
        frame = tk.Frame(toast, bg="#2c3e50", padx=20, pady=10)
        frame.pack(fill='both', expand=True)
        
        tk.Label(frame, text=message, font=self.label_font, bg="#2c3e50", fg=self.WHITE).pack()
        
        toast.after(duration, toast.destroy)

    def display_hand_result(self, message):
        """Mostra risultato mano"""
        result_text = ""
        community_cards = []
        if self.game_state:
            community_cards = [Card.from_dict(c) for c in self.game_state.get('community_cards', [])]

        if 'all_cards' in message and message['all_cards']:
            result_text += "🃏 Carte dei giocatori:\n\n"
            for pid, cards_data in message['all_cards'].items():
                cards = [Card.from_dict(c) for c in cards_data]
                player_name = None
                if self.game_state and self.game_state.get('players'):
                    player_info = self.game_state['players'].get(pid, {})
                    player_name = player_info.get('name')
                if not player_name:
                    player_name = f"Giocatore {int(pid) + 1}"

                all_cards = cards + community_cards
                desc = hand_description(all_cards) if len(all_cards) >= 5 else "N/A"
                cards_str = ' '.join([str(c) for c in cards])
                result_text += f"  {player_name}: {cards_str}\n  → {desc}\n\n"

        if message['reason'] == 'split':
            result_text += f"\n💰 PAREGGIO!\nIl piatto di {message['pot']} viene diviso"
        else:
            reason_text = {
                'fold': ' (fold)',
                'timeout': ' (timeout)',
                'disconnect': ' (disconnessione)'
            }.get(message.get('reason'), '')
            result_text += f"\n🏆 {message['winner_name']} vince {message['pot']} chips{reason_text}!"

        stats = message.get('stats')
        if stats:
            result_text += "\n\n📊 Statistiche:\n"
            for pid, values in stats.items():
                if isinstance(values, dict):
                    wins = values.get('hands_won', 0)
                    played = values.get('hands_played', 0)
                else:
                    wins = played = 0
                player_name = None
                if self.game_state and self.game_state.get('players'):
                    info = self.game_state['players'].get(pid, {})
                    player_name = info.get('name')
                if not player_name:
                    player_name = f"Giocatore {int(pid) + 1}"
                result_text += f"  • {player_name}: {wins}/{played} vittorie\n"

        messagebox.showinfo("🎯 Risultato", result_text)

    def ask_continue(self):
        """Chiede se continuare"""
        response = messagebox.askyesno("🎲 Continua?", "Vuoi giocare un'altra mano?")
        self.send_message({'continue': response})
        if not response:
            self.running = False
            self.root.quit()

    def cleanup_connection(self):
        """Chiude connessione"""
        if self.channel:
            try:
                self.channel.close()
            except Exception:
                pass
        elif self.socket:
            try:
                self.socket.close()
            except OSError:
                pass
        self.channel = None
        self.socket = None

    @staticmethod
    def _normalize_player_keys(payload):
        """Normalizza chiavi dizionario"""
        if not isinstance(payload, dict):
            return payload
        normalized = {}
        for key, value in payload.items():
            try:
                normalized[int(key)] = value
            except (TypeError, ValueError):
                normalized[key] = value
        return normalized

    def send_message(self, message):
        """Invia messaggio"""
        if not self.channel:
            return
        try:
            self.channel.send(message)
        except ConnectionClosed as e:
            print(f"Errore invio: {e}")
            self.running = False

    def receive_message(self):
        """Riceve messaggio"""
        if not self.channel:
            return None
        try:
            return self.channel.receive()
        except ConnectionClosed:
            return None

    def on_closing(self):
        """Chiusura finestra"""
        self._stop_timer()
        if messagebox.askokcancel("Esci", "Vuoi uscire dal gioco?"):
            self.running = False
            self.cleanup_connection()
            self.root.destroy()


def main():
    root = tk.Tk()
    app = PokerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
