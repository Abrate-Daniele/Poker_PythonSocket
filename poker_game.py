"""
Modulo per la logica del gioco del poker.
Contiene le classi per le carte, il mazzo e le funzioni per valutare le mani.
"""

import random
from collections import Counter
from enum import IntEnum


class HandRank(IntEnum):
    """Ranking delle mani di poker (dal più basso al più alto)"""
    HIGH_CARD = 1
    PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10


class Card:
    """Rappresenta una singola carta da gioco"""

    SUITS = ['♠', '♥', '♦', '♣']
    SUIT_NAMES = {'♠': 'Picche', '♥': 'Cuori', '♦': 'Quadri', '♣': 'Fiori'}
    VALUES = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    VALUE_MAP = {v: i + 2 for i, v in enumerate(VALUES)}

    def __init__(self, value, suit):
        """
        Inizializza una carta.

        Args:
            value: Valore della carta (2-10, J, Q, K, A)
            suit: Seme della carta (♠, ♥, ♦, ♣)
        """
        if value not in self.VALUES:
            raise ValueError(f"Valore carta non valido: {value}")
        if suit not in self.SUITS:
            raise ValueError(f"Seme carta non valido: {suit}")

        self.value = value
        self.suit = suit
        self.rank = self.VALUE_MAP[value]

    def __str__(self):
        return f"{self.value}{self.suit}"

    def __repr__(self):
        return self.__str__()

    def to_dict(self):
        """Converte la carta in un dizionario per la serializzazione"""
        return {'value': self.value, 'suit': self.suit}

    @classmethod
    def from_dict(cls, data):
        """Crea una carta da un dizionario"""
        return cls(data['value'], data['suit'])


class Deck:
    """Rappresenta un mazzo di 52 carte"""

    def __init__(self):
        """Inizializza e mischia un mazzo completo di carte"""
        self.cards = []
        self.reset()

    def reset(self):
        """Ricrea e mischia il mazzo"""
        self.cards = [Card(value, suit) for suit in Card.SUITS for value in Card.VALUES]
        self.shuffle()

    def shuffle(self):
        """Mischia il mazzo"""
        random.shuffle(self.cards)

    def deal(self, num_cards=1):
        """
        Distribuisce un numero specifico di carte dal mazzo.

        Args:
            num_cards: Numero di carte da distribuire

        Returns:
            Lista di carte distribuite
        """
        if num_cards > len(self.cards):
            raise ValueError("Non ci sono abbastanza carte nel mazzo")

        dealt_cards = []
        for _ in range(num_cards):
            dealt_cards.append(self.cards.pop())
        return dealt_cards

    def cards_remaining(self):
        """Restituisce il numero di carte rimanenti nel mazzo"""
        return len(self.cards)


def evaluate_hand(cards):
    """
    Valuta una mano di poker (migliore combinazione di 5 carte).

    Args:
        cards: Lista di oggetti Card (può essere 5, 6 o 7 carte)

    Returns:
        Tupla (HandRank, lista di valori per il confronto)
    """
    if len(cards) < 5:
        raise ValueError("Servono almeno 5 carte per valutare una mano")

    # Se abbiamo più di 5 carte, troviamo la migliore combinazione di 5
    if len(cards) > 5:
        from itertools import combinations
        best_hand = None
        best_rank = (HandRank.HIGH_CARD, [])

        for combo in combinations(cards, 5):
            hand_rank = _evaluate_five_cards(list(combo))
            if hand_rank > best_rank:
                best_rank = hand_rank
                best_hand = combo

        return best_rank
    else:
        return _evaluate_five_cards(cards)


def _evaluate_five_cards(cards):
    """
    Valuta esattamente 5 carte.

    Returns:
        Tupla (HandRank, lista di valori per il confronto)
    """
    if len(cards) != 5:
        raise ValueError("Questa funzione richiede esattamente 5 carte")

    # Ordina le carte per valore (dal più alto al più basso)
    sorted_cards = sorted(cards, key=lambda c: c.rank, reverse=True)
    ranks = [c.rank for c in sorted_cards]
    suits = [c.suit for c in sorted_cards]

    # Conta le occorrenze di ogni valore
    rank_counts = Counter(ranks)
    count_values = sorted(rank_counts.values(), reverse=True)
    unique_ranks = sorted(rank_counts.keys(), reverse=True)

    # Verifica flush (tutte le carte dello stesso seme)
    is_flush = len(set(suits)) == 1

    # Verifica straight (scala)
    is_straight = False
    straight_high = 0

    # Verifica scala normale
    if len(unique_ranks) == 5 and (max(ranks) - min(ranks) == 4):
        is_straight = True
        straight_high = max(ranks)

    # Verifica scala con Asso basso (A-2-3-4-5)
    if sorted(ranks) == [2, 3, 4, 5, 14]:
        is_straight = True
        straight_high = 5  # In questa scala, il 5 è la carta più alta

    # Scala Reale (10-J-Q-K-A dello stesso seme)
    if is_straight and is_flush and min(ranks) == 10:
        return (HandRank.ROYAL_FLUSH, [14])

    # Scala Colore (scala + flush)
    if is_straight and is_flush:
        return (HandRank.STRAIGHT_FLUSH, [straight_high])

    # Poker (quattro carte dello stesso valore)
    if count_values == [4, 1]:
        four_kind = [r for r, c in rank_counts.items() if c == 4][0]
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return (HandRank.FOUR_OF_A_KIND, [four_kind, kicker])

    # Full (tris + coppia)
    if count_values == [3, 2]:
        three_kind = [r for r, c in rank_counts.items() if c == 3][0]
        pair = [r for r, c in rank_counts.items() if c == 2][0]
        return (HandRank.FULL_HOUSE, [three_kind, pair])

    # Colore (tutte dello stesso seme)
    if is_flush:
        return (HandRank.FLUSH, sorted(ranks, reverse=True))

    # Scala
    if is_straight:
        return (HandRank.STRAIGHT, [straight_high])

    # Tris (tre carte dello stesso valore)
    if count_values == [3, 1, 1]:
        three_kind = [r for r, c in rank_counts.items() if c == 3][0]
        kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
        return (HandRank.THREE_OF_A_KIND, [three_kind] + kickers)

    # Doppia coppia
    if count_values == [2, 2, 1]:
        pairs = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return (HandRank.TWO_PAIR, pairs + [kicker])

    # Coppia
    if count_values == [2, 1, 1, 1]:
        pair = [r for r, c in rank_counts.items() if c == 2][0]
        kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
        return (HandRank.PAIR, [pair] + kickers)

    # Carta alta
    return (HandRank.HIGH_CARD, sorted(ranks, reverse=True))


def compare_hands(hand1_cards, hand2_cards):
    """
    Confronta due mani di poker.

    Args:
        hand1_cards: Lista di carte del giocatore 1
        hand2_cards: Lista di carte del giocatore 2

    Returns:
        1 se vince il giocatore 1, -1 se vince il giocatore 2, 0 se pareggio
    """
    rank1, values1 = evaluate_hand(hand1_cards)
    rank2, values2 = evaluate_hand(hand2_cards)

    # Prima confronta il ranking della mano
    if rank1 > rank2:
        return 1
    elif rank1 < rank2:
        return -1

    # Stesso ranking, confronta i valori delle carte
    for v1, v2 in zip(values1, values2):
        if v1 > v2:
            return 1
        elif v1 < v2:
            return -1

    # Mani identiche, pareggio
    return 0


def hand_description(cards):
    """
    Restituisce una descrizione testuale della mano.

    Args:
        cards: Lista di carte

    Returns:
        Stringa con la descrizione della mano
    """
    rank, values = evaluate_hand(cards)

    value_names = {14: 'Assi', 13: 'Re', 12: 'Regine', 11: 'Jack',
                   10: 'Dieci', 9: 'Nove', 8: 'Otto', 7: 'Sette',
                   6: 'Sei', 5: 'Cinque', 4: 'Quattro', 3: 'Tre', 2: 'Due'}

    value_names_single = {14: 'Asso', 13: 'Re', 12: 'Regina', 11: 'Jack',
                          10: 'Dieci', 9: 'Nove', 8: 'Otto', 7: 'Sette',
                          6: 'Sei', 5: 'Cinque', 4: 'Quattro', 3: 'Tre', 2: 'Due'}

    if rank == HandRank.ROYAL_FLUSH:
        return "Scala Reale!"
    elif rank == HandRank.STRAIGHT_FLUSH:
        return f"Scala Colore (fino a {value_names_single[values[0]]})"
    elif rank == HandRank.FOUR_OF_A_KIND:
        return f"Poker di {value_names[values[0]]}"
    elif rank == HandRank.FULL_HOUSE:
        return f"Full di {value_names[values[0]]} e {value_names[values[1]]}"
    elif rank == HandRank.FLUSH:
        return "Colore"
    elif rank == HandRank.STRAIGHT:
        return f"Scala (fino a {value_names_single[values[0]]})"
    elif rank == HandRank.THREE_OF_A_KIND:
        return f"Tris di {value_names[values[0]]}"
    elif rank == HandRank.TWO_PAIR:
        return f"Doppia Coppia ({value_names[values[0]]} e {value_names[values[1]]})"
    elif rank == HandRank.PAIR:
        return f"Coppia di {value_names[values[0]]}"
    else:
        return f"Carta Alta ({value_names_single[values[0]]})"


if __name__ == "__main__":
    # Test del modulo
    print("Test del modulo poker_game.py")
    print("-" * 50)

    # Crea un mazzo e distribuisci alcune carte
    deck = Deck()
    print(f"Carte nel mazzo: {deck.cards_remaining()}")

    # Distribuisci 7 carte (come nel Texas Hold'em con 2 carte personali + 5 comuni)
    test_cards = deck.deal(7)
    print(f"\nCarte distribuite: {test_cards}")

    # Valuta la mano
    rank, values = evaluate_hand(test_cards)
    print(f"Valutazione: {hand_description(test_cards)}")
    print(f"Rank: {rank.name}, Values: {values}")

    # Test confronto mani
    deck.reset()
    hand1 = deck.deal(5)
    hand2 = deck.deal(5)

    print(f"\nMano 1: {hand1}")
    print(f"Descrizione: {hand_description(hand1)}")
    print(f"\nMano 2: {hand2}")
    print(f"Descrizione: {hand_description(hand2)}")

    result = compare_hands(hand1, hand2)
    if result > 0:
        print("\nVince la Mano 1!")
    elif result < 0:
        print("\nVince la Mano 2!")
    else:
        print("\nPareggio!")
