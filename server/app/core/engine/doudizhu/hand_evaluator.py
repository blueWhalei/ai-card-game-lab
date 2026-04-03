"""Hand type classification, comparison, and legal-play enumeration for Doudizhu."""

from collections import Counter
from itertools import combinations

from app.core.engine.base import GameAction
from app.core.engine.doudizhu.cards import (
    BLACK_JOKER,
    RED_JOKER,
    ActionType,
    MIN_AIRPLANE_LENGTH,
    MIN_CHAIN_LENGTH,
    MIN_CHAIN_PAIR_LENGTH,
    card_power,
    card_rank,
    sort_cards,
)

# ── Classification ────────────────────────────────────


def classify(cards: list[str]) -> tuple[ActionType, int] | None:
    """Classify a set of cards into an ActionType and its primary power value.

    Returns None if the cards do not form any valid hand type.
    """
    n = len(cards)
    if n == 0:
        return None

    ranks = [card_rank(c) for c in cards]
    powers = sorted(card_power(c) for c in cards)
    rank_counts = Counter(ranks)
    count_groups = Counter(rank_counts.values())

    # Rocket: BJ + RJ
    if n == 2 and set(cards) == {BLACK_JOKER, RED_JOKER}:
        return (ActionType.ROCKET, 15)

    # Single
    if n == 1:
        return (ActionType.SINGLE, powers[0])

    # Pair
    if n == 2 and len(rank_counts) == 1:
        return (ActionType.PAIR, powers[0])

    # Triple
    if n == 3 and len(rank_counts) == 1:
        return (ActionType.TRIPLE, powers[0])

    # Bomb: four of the same rank
    if n == 4 and len(rank_counts) == 1:
        return (ActionType.BOMB, powers[0])

    # Triple + 1
    if n == 4 and count_groups.get(3) == 1 and count_groups.get(1) == 1:
        triple_rank = [r for r, c in rank_counts.items() if c == 3][0]
        return (ActionType.TRIPLE_ONE, _rank_to_power(triple_rank))

    # Triple + 2
    if n == 5 and count_groups.get(3) == 1 and count_groups.get(2) == 1:
        triple_rank = [r for r, c in rank_counts.items() if c == 3][0]
        return (ActionType.TRIPLE_TWO, _rank_to_power(triple_rank))

    # Four + 2 singles
    if n == 6 and count_groups.get(4) == 1 and count_groups.get(1) == 2:
        quad_rank = [r for r, c in rank_counts.items() if c == 4][0]
        return (ActionType.FOUR_TWO, _rank_to_power(quad_rank))

    # Four + 2 pairs
    if n == 8 and count_groups.get(4) == 1 and count_groups.get(2) == 2:
        quad_rank = [r for r, c in rank_counts.items() if c == 4][0]
        return (ActionType.FOUR_TWO, _rank_to_power(quad_rank))

    # Chain (顺子): >= 5 consecutive singles, no 2 or jokers
    if n >= MIN_CHAIN_LENGTH and len(rank_counts) == n and _is_consecutive(powers, n):
        if powers[-1] <= 11:  # A=11 is max in chain, no 2/jokers
            return (ActionType.CHAIN, powers[0])

    # Chain pair (连对): >= 3 consecutive pairs
    pair_count = n // 2
    if (
        n >= MIN_CHAIN_PAIR_LENGTH * 2
        and n % 2 == 0
        and all(c == 2 for c in rank_counts.values())
        and _is_consecutive(_unique_powers(rank_counts), pair_count)
    ):
        uq = _unique_powers(rank_counts)
        if uq[-1] <= 11:
            return (ActionType.CHAIN_PAIR, uq[0])

    # Airplane (飞机): >= 2 consecutive triples
    triple_ranks = sorted(
        [_rank_to_power(r) for r, c in rank_counts.items() if c >= 3]
    )
    if len(triple_ranks) >= MIN_AIRPLANE_LENGTH:
        seq = _longest_consecutive_sub(triple_ranks, max_power=11)
        if seq and len(seq) >= MIN_AIRPLANE_LENGTH:
            num_triples = len(seq)
            remaining = n - num_triples * 3
            if remaining == 0:
                return (ActionType.AIRPLANE, seq[0])
            if remaining == num_triples:
                return (ActionType.AIRPLANE_SOLO, seq[0])
            if remaining == num_triples * 2:
                pair_kickers = [r for r, c in rank_counts.items() if c >= 2 and _rank_to_power(r) not in seq]
                if len(pair_kickers) >= num_triples:
                    return (ActionType.AIRPLANE_PAIR, seq[0])

    return None


def can_beat(
    last_type: ActionType,
    last_power: int,
    candidate_type: ActionType,
    candidate_power: int,
) -> bool:
    """Return True if the candidate hand beats the last played hand."""
    # Rocket beats everything
    if candidate_type == ActionType.ROCKET:
        return True
    # Bomb beats non-bomb/non-rocket
    if candidate_type == ActionType.BOMB:
        if last_type == ActionType.ROCKET:
            return False
        if last_type == ActionType.BOMB:
            return candidate_power > last_power
        return True
    # Same type, higher power
    if candidate_type == last_type:
        return candidate_power > last_power
    return False


def get_legal_plays(
    hand: list[str],
    last_play: tuple[ActionType, int, list[str]] | None,
    player_id: str,
) -> list[GameAction]:
    """Enumerate all legal plays from *hand* given the last play on the table.

    If *last_play* is None, the player leads and can play any valid combination.
    Always includes PASS (unless leading).
    """
    results: list[GameAction] = []
    hand_sorted = sort_cards(hand)

    if last_play is None:
        # Leading: enumerate all valid combinations
        results.extend(_enumerate_all(hand_sorted, player_id))
    else:
        last_type, last_power, last_cards = last_play
        results.extend(_enumerate_beating(hand_sorted, last_type, last_power, last_cards, player_id))
        results.append(GameAction(player_id=player_id, action_type=ActionType.PASS))

    return results


# ── Private helpers ───────────────────────────────────


def _rank_to_power(rank: str) -> int:
    from app.core.engine.doudizhu.cards import RANK_POWER
    return RANK_POWER[rank]


def _is_consecutive(powers: list[int], length: int) -> bool:
    if len(powers) != length:
        return False
    return powers[-1] - powers[0] == length - 1 and len(set(powers)) == length


def _unique_powers(rank_counts: Counter[str]) -> list[int]:
    return sorted(_rank_to_power(r) for r in rank_counts)


def _longest_consecutive_sub(values: list[int], max_power: int = 11) -> list[int] | None:
    """Find the longest consecutive subsequence within max_power."""
    filtered = [v for v in values if v <= max_power]
    if not filtered:
        return None
    best: list[int] = []
    current: list[int] = [filtered[0]]
    for i in range(1, len(filtered)):
        if filtered[i] == filtered[i - 1] + 1:
            current.append(filtered[i])
        else:
            if len(current) > len(best):
                best = current[:]
            current = [filtered[i]]
    if len(current) > len(best):
        best = current
    return best if len(best) >= MIN_AIRPLANE_LENGTH else None


# Action type priority for sorting (higher = better, shown first)
_ACTION_PRIORITY: dict[ActionType, int] = {
    ActionType.ROCKET: 14,
    ActionType.BOMB: 13,
    ActionType.AIRPLANE_PAIR: 12,
    ActionType.AIRPLANE_SOLO: 11,
    ActionType.AIRPLANE: 10,
    ActionType.FOUR_TWO: 9,
    ActionType.CHAIN_PAIR: 8,
    ActionType.CHAIN: 7,
    ActionType.TRIPLE_TWO: 6,
    ActionType.TRIPLE_ONE: 5,
    ActionType.TRIPLE: 4,
    ActionType.PAIR: 3,
    ActionType.SINGLE: 2,
    ActionType.PASS: 1,
}


def _sort_actions_by_priority(actions: list[GameAction]) -> list[GameAction]:
    """Sort actions by priority (combo types first, singles last)."""
    def sort_key(a: GameAction) -> int:
        return _ACTION_PRIORITY.get(a.action_type, 0)
    return sorted(actions, key=sort_key, reverse=True)


def _enumerate_all(hand: list[str], player_id: str) -> list[GameAction]:
    """Enumerate every valid hand type from the given cards (for leading).

    Returns actions sorted by priority: combo types (rockets, bombs, airplanes, chains)
    come first, then triples/pairs, and singles last.
    """
    results: list[GameAction] = []
    rank_counts = Counter(card_rank(c) for c in hand)
    cards_by_rank: dict[str, list[str]] = {}
    for c in hand:
        cards_by_rank.setdefault(card_rank(c), []).append(c)

    # Singles
    for r, cards in cards_by_rank.items():
        results.append(GameAction(player_id=player_id, action_type=ActionType.SINGLE, cards=[cards[0]]))

    # Pairs
    for r, cards in cards_by_rank.items():
        if len(cards) >= 2:
            results.append(GameAction(player_id=player_id, action_type=ActionType.PAIR, cards=cards[:2]))

    # Triples
    for r, cards in cards_by_rank.items():
        if len(cards) >= 3:
            triple = cards[:3]
            results.append(GameAction(player_id=player_id, action_type=ActionType.TRIPLE, cards=triple))
            # Triple + 1
            for kr, kcards in cards_by_rank.items():
                if kr != r:
                    results.append(GameAction(
                        player_id=player_id,
                        action_type=ActionType.TRIPLE_ONE,
                        cards=triple + [kcards[0]],
                    ))
            # Triple + 2
            for kr, kcards in cards_by_rank.items():
                if kr != r and len(kcards) >= 2:
                    results.append(GameAction(
                        player_id=player_id,
                        action_type=ActionType.TRIPLE_TWO,
                        cards=triple + kcards[:2],
                    ))

    # Bombs
    for r, cards in cards_by_rank.items():
        if len(cards) == 4:
            results.append(GameAction(player_id=player_id, action_type=ActionType.BOMB, cards=cards[:4]))

    # Rocket
    if BLACK_JOKER in hand and RED_JOKER in hand:
        results.append(GameAction(
            player_id=player_id,
            action_type=ActionType.ROCKET,
            cards=[BLACK_JOKER, RED_JOKER],
        ))

    # Chains (顺子): 5+ consecutive singles
    power_ranks = sorted(set(
        _rank_to_power(r) for r in rank_counts if _rank_to_power(r) <= 11
    ))
    for chain in _find_consecutive_seqs(power_ranks, MIN_CHAIN_LENGTH):
        chain_cards = []
        for p in chain:
            r = _power_to_rank(p)
            chain_cards.append(cards_by_rank[r][0])
        results.append(GameAction(
            player_id=player_id,
            action_type=ActionType.CHAIN,
            cards=chain_cards,
        ))

    # Chain pairs (连对): 3+ consecutive pairs
    pair_powers = sorted(set(
        _rank_to_power(r) for r, c in rank_counts.items() if c >= 2 and _rank_to_power(r) <= 11
    ))
    for chain in _find_consecutive_seqs(pair_powers, MIN_CHAIN_PAIR_LENGTH):
        chain_cards = []
        for p in chain:
            r = _power_to_rank(p)
            chain_cards.extend(cards_by_rank[r][:2])
        results.append(GameAction(
            player_id=player_id,
            action_type=ActionType.CHAIN_PAIR,
            cards=chain_cards,
        ))

    # Airplanes (飞机): 2+ consecutive triples
    triple_powers = sorted(set(
        _rank_to_power(r) for r, c in rank_counts.items() if c >= 3 and _rank_to_power(r) <= 11
    ))
    for chain in _find_consecutive_seqs(triple_powers, MIN_AIRPLANE_LENGTH):
        plane_cards: list[str] = []
        used_ranks = set()
        for p in chain:
            r = _power_to_rank(p)
            plane_cards.extend(cards_by_rank[r][:3])
            used_ranks.add(r)
        results.append(GameAction(
            player_id=player_id,
            action_type=ActionType.AIRPLANE,
            cards=plane_cards,
        ))
        # Airplane + solo wings
        kicker_ranks = [r for r in rank_counts if r not in used_ranks]
        if len(kicker_ranks) >= len(chain):
            for combo in combinations(kicker_ranks, len(chain)):
                kicker_cards = [cards_by_rank[r][0] for r in combo]
                results.append(GameAction(
                    player_id=player_id,
                    action_type=ActionType.AIRPLANE_SOLO,
                    cards=plane_cards + kicker_cards,
                ))
        # Airplane + pair wings
        pair_kicker_ranks = [r for r, c in rank_counts.items() if c >= 2 and r not in used_ranks]
        if len(pair_kicker_ranks) >= len(chain):
            for combo in combinations(pair_kicker_ranks, len(chain)):
                kicker_cards = []
                for r in combo:
                    kicker_cards.extend(cards_by_rank[r][:2])
                results.append(GameAction(
                    player_id=player_id,
                    action_type=ActionType.AIRPLANE_PAIR,
                    cards=plane_cards + kicker_cards,
                ))

    # Four + 2 singles
    for r, cards in cards_by_rank.items():
        if len(cards) == 4:
            other_ranks = [k for k in cards_by_rank if k != r]
            for combo in combinations(other_ranks, 2):
                kicker_cards = [cards_by_rank[combo[0]][0], cards_by_rank[combo[1]][0]]
                results.append(GameAction(
                    player_id=player_id,
                    action_type=ActionType.FOUR_TWO,
                    cards=cards[:4] + kicker_cards,
                ))
            # Four + 2 pairs
            pair_ranks = [k for k in cards_by_rank if k != r and len(cards_by_rank[k]) >= 2]
            for combo in combinations(pair_ranks, 2):
                kicker_cards = cards_by_rank[combo[0]][:2] + cards_by_rank[combo[1]][:2]
                results.append(GameAction(
                    player_id=player_id,
                    action_type=ActionType.FOUR_TWO,
                    cards=cards[:4] + kicker_cards,
                ))

    # Sort by priority: combo types first, singles last
    return _sort_actions_by_priority(results)


def _enumerate_beating(
    hand: list[str],
    last_type: ActionType,
    last_power: int,
    last_cards: list[str],
    player_id: str,
) -> list[GameAction]:
    """Enumerate hands from *hand* that beat the given (last_type, last_power, last_cards).

    For variable-length hand types (CHAIN, CHAIN_PAIR, AIRPLANE, etc.), the length
    must match exactly per game rules.
    """
    results: list[GameAction] = []
    rank_counts = Counter(card_rank(c) for c in hand)
    cards_by_rank: dict[str, list[str]] = {}
    for c in hand:
        cards_by_rank.setdefault(card_rank(c), []).append(c)

    if last_type == ActionType.SINGLE:
        for r, cards in cards_by_rank.items():
            if _rank_to_power(r) > last_power:
                results.append(GameAction(player_id=player_id, action_type=ActionType.SINGLE, cards=[cards[0]]))

    elif last_type == ActionType.PAIR:
        for r, cards in cards_by_rank.items():
            if len(cards) >= 2 and _rank_to_power(r) > last_power:
                results.append(GameAction(player_id=player_id, action_type=ActionType.PAIR, cards=cards[:2]))

    elif last_type == ActionType.TRIPLE:
        for r, cards in cards_by_rank.items():
            if len(cards) >= 3 and _rank_to_power(r) > last_power:
                results.append(GameAction(player_id=player_id, action_type=ActionType.TRIPLE, cards=cards[:3]))

    elif last_type == ActionType.TRIPLE_ONE:
        for r, cards in cards_by_rank.items():
            if len(cards) >= 3 and _rank_to_power(r) > last_power:
                triple = cards[:3]
                for kr, kcards in cards_by_rank.items():
                    if kr != r:
                        results.append(GameAction(
                            player_id=player_id,
                            action_type=ActionType.TRIPLE_ONE,
                            cards=triple + [kcards[0]],
                        ))

    elif last_type == ActionType.TRIPLE_TWO:
        for r, cards in cards_by_rank.items():
            if len(cards) >= 3 and _rank_to_power(r) > last_power:
                triple = cards[:3]
                for kr, kcards in cards_by_rank.items():
                    if kr != r and len(kcards) >= 2:
                        results.append(GameAction(
                            player_id=player_id,
                            action_type=ActionType.TRIPLE_TWO,
                            cards=triple + kcards[:2],
                        ))

    elif last_type == ActionType.CHAIN:
        # Must find SAME-LENGTH chain with higher starting power
        last_length = len(last_cards)
        _add_chains_beating(results, rank_counts, cards_by_rank, last_power, last_length, player_id)

    elif last_type == ActionType.CHAIN_PAIR:
        # Must find same-length chain pair
        last_pair_count = len(last_cards) // 2
        _add_chain_pairs_beating(results, rank_counts, cards_by_rank, last_power, last_pair_count, player_id)

    elif last_type == ActionType.AIRPLANE:
        # Must find same-length airplane
        last_triple_count = len(last_cards) // 3
        _add_airplanes_beating(results, rank_counts, cards_by_rank, last_power, last_triple_count, player_id)

    elif last_type == ActionType.AIRPLANE_SOLO:
        # Airplane + solo wings: 4 cards per triple (3 + 1)
        last_triple_count = len(last_cards) // 4
        _add_airplane_solos_beating(results, rank_counts, cards_by_rank, last_power, last_triple_count, player_id)

    elif last_type == ActionType.AIRPLANE_PAIR:
        # Airplane + pair wings: 5 cards per triple (3 + 2)
        last_triple_count = len(last_cards) // 5
        _add_airplane_pairs_beating(results, rank_counts, cards_by_rank, last_power, last_triple_count, player_id)

    elif last_type == ActionType.FOUR_TWO:
        for r, cards in cards_by_rank.items():
            if len(cards) == 4 and _rank_to_power(r) > last_power:
                # Four + 2 singles
                other_ranks = [k for k in cards_by_rank if k != r]
                if len(other_ranks) >= 2:
                    for combo in combinations(other_ranks, 2):
                        kicker_cards = [cards_by_rank[combo[0]][0], cards_by_rank[combo[1]][0]]
                        results.append(GameAction(
                            player_id=player_id,
                            action_type=ActionType.FOUR_TWO,
                            cards=cards[:4] + kicker_cards,
                        ))
                # Four + 2 pairs
                pair_ranks = [k for k in cards_by_rank if k != r and len(cards_by_rank[k]) >= 2]
                if len(pair_ranks) >= 2:
                    for combo in combinations(pair_ranks, 2):
                        kicker_cards = cards_by_rank[combo[0]][:2] + cards_by_rank[combo[1]][:2]
                        results.append(GameAction(
                            player_id=player_id,
                            action_type=ActionType.FOUR_TWO,
                            cards=cards[:4] + kicker_cards,
                        ))

    elif last_type == ActionType.BOMB:
        for r, cards in cards_by_rank.items():
            if len(cards) == 4 and _rank_to_power(r) > last_power:
                results.append(GameAction(player_id=player_id, action_type=ActionType.BOMB, cards=cards[:4]))

    # Bombs always beat non-bombs (except rocket)
    if last_type not in (ActionType.BOMB, ActionType.ROCKET):
        for r, cards in cards_by_rank.items():
            if len(cards) == 4:
                results.append(GameAction(player_id=player_id, action_type=ActionType.BOMB, cards=cards[:4]))

    # Rocket always available
    if BLACK_JOKER in hand and RED_JOKER in hand:
        results.append(GameAction(
            player_id=player_id,
            action_type=ActionType.ROCKET,
            cards=[BLACK_JOKER, RED_JOKER],
        ))

    # Sort by priority: combo types first
    return _sort_actions_by_priority(results)


def _add_chains_beating(
    results: list[GameAction],
    rank_counts: Counter[str],
    cards_by_rank: dict[str, list[str]],
    last_power: int,
    last_length: int,
    player_id: str,
) -> None:
    """Find chains that beat the given chain (same length, higher starting power)."""
    available = sorted(set(
        _rank_to_power(r) for r in rank_counts if _rank_to_power(r) <= 11
    ))
    # Only find chains of EXACTLY the same length
    for seq in _find_consecutive_seqs_exact(available, last_length):
        if seq[0] > last_power:
            chain_cards = [cards_by_rank[_power_to_rank(p)][0] for p in seq]
            results.append(GameAction(
                player_id=player_id,
                action_type=ActionType.CHAIN,
                cards=chain_cards,
            ))


def _add_chain_pairs_beating(
    results: list[GameAction],
    rank_counts: Counter[str],
    cards_by_rank: dict[str, list[str]],
    last_power: int,
    last_pair_count: int,
    player_id: str,
) -> None:
    """Find chain pairs that beat the given chain pair (same length, higher power)."""
    pair_powers = sorted(set(
        _rank_to_power(r) for r, c in rank_counts.items() if c >= 2 and _rank_to_power(r) <= 11
    ))
    # Only find chain pairs of EXACTLY the same length
    for seq in _find_consecutive_seqs_exact(pair_powers, last_pair_count):
        if seq[0] > last_power:
            chain_cards: list[str] = []
            for p in seq:
                chain_cards.extend(cards_by_rank[_power_to_rank(p)][:2])
            results.append(GameAction(
                player_id=player_id,
                action_type=ActionType.CHAIN_PAIR,
                cards=chain_cards,
            ))


def _add_airplanes_beating(
    results: list[GameAction],
    rank_counts: Counter[str],
    cards_by_rank: dict[str, list[str]],
    last_power: int,
    last_triple_count: int,
    player_id: str,
) -> None:
    """Find airplanes that beat the given airplane (same length, higher power)."""
    triple_powers = sorted(set(
        _rank_to_power(r) for r, c in rank_counts.items() if c >= 3 and _rank_to_power(r) <= 11
    ))
    for seq in _find_consecutive_seqs_exact(triple_powers, last_triple_count):
        if seq[0] > last_power:
            plane_cards: list[str] = []
            for p in seq:
                r = _power_to_rank(p)
                plane_cards.extend(cards_by_rank[r][:3])
            results.append(GameAction(
                player_id=player_id,
                action_type=ActionType.AIRPLANE,
                cards=plane_cards,
            ))


def _add_airplane_solos_beating(
    results: list[GameAction],
    rank_counts: Counter[str],
    cards_by_rank: dict[str, list[str]],
    last_power: int,
    last_triple_count: int,
    player_id: str,
) -> None:
    """Find airplane+solo that beat the given airplane+solo."""
    triple_powers = sorted(set(
        _rank_to_power(r) for r, c in rank_counts.items() if c >= 3 and _rank_to_power(r) <= 11
    ))
    for seq in _find_consecutive_seqs_exact(triple_powers, last_triple_count):
        if seq[0] > last_power:
            plane_cards: list[str] = []
            used_ranks = set()
            for p in seq:
                r = _power_to_rank(p)
                plane_cards.extend(cards_by_rank[r][:3])
                used_ranks.add(r)
            # Find kickers
            kicker_ranks = [r for r in rank_counts if r not in used_ranks]
            if len(kicker_ranks) >= last_triple_count:
                for combo in combinations(kicker_ranks, last_triple_count):
                    kicker_cards = [cards_by_rank[r][0] for r in combo]
                    results.append(GameAction(
                        player_id=player_id,
                        action_type=ActionType.AIRPLANE_SOLO,
                        cards=plane_cards + kicker_cards,
                    ))


def _add_airplane_pairs_beating(
    results: list[GameAction],
    rank_counts: Counter[str],
    cards_by_rank: dict[str, list[str]],
    last_power: int,
    last_triple_count: int,
    player_id: str,
) -> None:
    """Find airplane+pair that beat the given airplane+pair."""
    triple_powers = sorted(set(
        _rank_to_power(r) for r, c in rank_counts.items() if c >= 3 and _rank_to_power(r) <= 11
    ))
    for seq in _find_consecutive_seqs_exact(triple_powers, last_triple_count):
        if seq[0] > last_power:
            plane_cards: list[str] = []
            used_ranks = set()
            for p in seq:
                r = _power_to_rank(p)
                plane_cards.extend(cards_by_rank[r][:3])
                used_ranks.add(r)
            # Find pair kickers
            pair_kicker_ranks = [r for r, c in rank_counts.items() if c >= 2 and r not in used_ranks]
            if len(pair_kicker_ranks) >= last_triple_count:
                for combo in combinations(pair_kicker_ranks, last_triple_count):
                    kicker_cards: list[str] = []
                    for r in combo:
                        kicker_cards.extend(cards_by_rank[r][:2])
                    results.append(GameAction(
                        player_id=player_id,
                        action_type=ActionType.AIRPLANE_PAIR,
                        cards=plane_cards + kicker_cards,
                    ))

def _find_consecutive_seqs(values: list[int], min_length: int) -> list[list[int]]:
    """Find all consecutive subsequences of at least min_length."""
    if not values:
        return []
    results: list[list[int]] = []
    seqs = _split_consecutive(values)
    for seq in seqs:
        for start in range(len(seq)):
            for end in range(start + min_length, len(seq) + 1):
                results.append(seq[start:end])
    return results


def _find_consecutive_seqs_exact(values: list[int], length: int) -> list[list[int]]:
    """Find all consecutive subsequences of exactly *length*."""
    if not values:
        return []
    results: list[list[int]] = []
    seqs = _split_consecutive(values)
    for seq in seqs:
        for start in range(len(seq) - length + 1):
            results.append(seq[start : start + length])
    return results


def _split_consecutive(values: list[int]) -> list[list[int]]:
    """Split sorted values into groups of consecutive integers."""
    if not values:
        return []
    groups: list[list[int]] = [[values[0]]]
    for i in range(1, len(values)):
        if values[i] == values[i - 1] + 1:
            groups[-1].append(values[i])
        else:
            groups.append([values[i]])
    return groups


def _power_to_rank(power: int) -> str:
    """Convert numeric power back to rank string."""
    from app.core.engine.doudizhu.cards import RANKS
    if power == 13:
        return BLACK_JOKER
    if power == 14:
        return RED_JOKER
    return RANKS[power]
