import random
import os
from collections import Counter
from enum import IntEnum


class HandRank(IntEnum):
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

    SUITS = ['♠', '♥', '♦', '♣']
    SUIT_NAMES = {'♠': 'Picche', '♥': 'Cuori', '♦': 'Quadri', '♣': 'Fiori'}
    VALUES = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    VALUE_MAP = {v: i + 2 for i, v in enumerate(VALUES)}

    def __init__(self, value, suit):
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
        return {'value': self.value, 'suit': self.suit}

    @classmethod
    def from_dict(cls, data):
        return cls(data['value'], data['suit'])


class Deck:

    def __init__(self):
        self.cards = []
        self.reset()

    def reset(self):
        self.cards = [Card(value, suit) for suit in Card.SUITS for value in Card.VALUES]
        self.shuffle()

    def shuffle(self):
        rng = random.SystemRandom()
        for _ in range(3):
            rng.shuffle(self.cards)
        cut = rng.randint(0, len(self.cards)-1)
        self.cards = self.cards[cut:] + self.cards[:cut]

    def deal(self, num_cards=1):
        
        if num_cards > len(self.cards):
            raise ValueError("Non ci sono abbastanza carte nel mazzo")

        dealt_cards = []
        for _ in range(num_cards):
            dealt_cards.append(self.cards.pop())
        return dealt_cards

    def cards_remaining(self):
        return len(self.cards)


def evaluate_hand(cards):
    if len(cards) < 5:
        raise ValueError("Servono almeno 5 carte per valutare una mano")

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
    if len(cards) != 5:
        raise ValueError("Questa funzione richiede esattamente 5 carte")

    sorted_cards = sorted(cards, key=lambda c: c.rank, reverse=True)
    ranks = [c.rank for c in sorted_cards]
    suits = [c.suit for c in sorted_cards]

    rank_counts = Counter(ranks)
    count_values = sorted(rank_counts.values(), reverse=True)
    unique_ranks = sorted(rank_counts.keys(), reverse=True)

    is_flush = len(set(suits)) == 1

    is_straight = False
    straight_high = 0

    if len(unique_ranks) == 5 and (max(ranks) - min(ranks) == 4):
        is_straight = True
        straight_high = max(ranks)

    if sorted(ranks) == [2, 3, 4, 5, 14]:
        is_straight = True
        straight_high = 5 
        
    if is_straight and is_flush and min(ranks) == 10:
        return (HandRank.ROYAL_FLUSH, [14])

    if is_straight and is_flush:
        return (HandRank.STRAIGHT_FLUSH, [straight_high])

    if count_values == [4, 1]:
        four_kind = [r for r, c in rank_counts.items() if c == 4][0]
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return (HandRank.FOUR_OF_A_KIND, [four_kind, kicker])

    if count_values == [3, 2]:
        three_kind = [r for r, c in rank_counts.items() if c == 3][0]
        pair = [r for r, c in rank_counts.items() if c == 2][0]
        return (HandRank.FULL_HOUSE, [three_kind, pair])

    if is_flush:
        return (HandRank.FLUSH, sorted(ranks, reverse=True))

    if is_straight:
        return (HandRank.STRAIGHT, [straight_high])

    if count_values == [3, 1, 1]:
        three_kind = [r for r, c in rank_counts.items() if c == 3][0]
        kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
        return (HandRank.THREE_OF_A_KIND, [three_kind] + kickers)

    if count_values == [2, 2, 1]:
        pairs = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return (HandRank.TWO_PAIR, pairs + [kicker])

    if count_values == [2, 1, 1, 1]:
        pair = [r for r, c in rank_counts.items() if c == 2][0]
        kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
        return (HandRank.PAIR, [pair] + kickers)

    return (HandRank.HIGH_CARD, sorted(ranks, reverse=True))


def compare_hands(hand1_cards, hand2_cards):
    rank1, values1 = evaluate_hand(hand1_cards)
    rank2, values2 = evaluate_hand(hand2_cards)

    if rank1 > rank2:
        return 1
    elif rank1 < rank2:
        return -1

    for v1, v2 in zip(values1, values2):
        if v1 > v2:
            return 1
        elif v1 < v2:
            return -1

    return 0


def hand_description(cards):
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
    print("Test del modulo poker_game.py")
    print("-" * 50)

    deck = Deck()
    print(f"Carte nel mazzo: {deck.cards_remaining()}")

    test_cards = deck.deal(7)
    print(f"\nCarte distribuite: {test_cards}")

    rank, values = evaluate_hand(test_cards)
    print(f"Valutazione: {hand_description(test_cards)}")
    print(f"Rank: {rank.name}, Values: {values}")

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
