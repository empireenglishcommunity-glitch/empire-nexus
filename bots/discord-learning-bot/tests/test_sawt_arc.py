"""Tests for arc-aware story state + lifecycle (spec Phase 4.2 / 4.3).

Pins the serial's spine:
  * old pre-Phase-4 state upgrades without data loss (back-compat);
  * an arc runs its planned 5-7 episodes, opens with exactly one opener, and ends
    with exactly one finale;
  * the finale rotates the series to a NEW, different genre;
  * the audience's winning choices accumulate for the listener-echo.
"""
from src import sawt_arc as arc
from src import sawt_bible as bible


def test_normalize_upgrades_pre_phase4_state_without_loss():
    old = {"episode_number": 4, "recap": "Maya found a key.",
           "winning_choice": "open it"}
    s = arc.normalize(old)
    assert s["episode_number"] == 4
    assert s["recap"] == "Maya found a key."
    assert s["winning_choice"] == "open it"
    # gains a blank arc so the next episode opens arc 1
    assert s["arc"]["arc_id"] == 0
    assert s["arc"]["genre"] is None
    assert s["past_choices"] == []


def test_normalize_handles_none_and_empty():
    for bad in (None, {}, {"arc": {}}):
        s = arc.normalize(bad)
        assert "arc" in s and "episode_number" in s


def _simulate(days):
    """Run `days` episodes from a fresh series; return the per-episode timeline."""
    state = {}
    timeline = []
    for _ in range(days):
        plan = arc.plan_next_episode(state)
        a = plan["arc"]
        timeline.append({
            "gep": plan["episode_number"], "arc_id": a["arc_id"],
            "genre": a["genre"], "ep_in_arc": a["episode_in_arc"],
            "planned": a["planned_episodes"],
            "opener": plan["is_arc_opener"], "finale": plan["is_arc_finale"],
        })
        state = arc.apply_generated(
            plan["state"], recap=f"ep{plan['episode_number']}",
            facts=[f"fact{plan['episode_number']}"],
            was_finale=plan["is_arc_finale"],
            motif_used=(a["episode_in_arc"] == 2))
        state = arc.record_winning_choice(state, f"c{plan['episode_number']}")
    return timeline, state


def test_first_episode_is_an_opener_of_arc_one():
    timeline, _ = _simulate(1)
    t = timeline[0]
    assert t["arc_id"] == 1 and t["ep_in_arc"] == 1
    assert t["opener"] is True and t["finale"] is False


def test_each_completed_arc_runs_its_planned_length_with_one_opener_and_finale():
    timeline, _ = _simulate(20)
    from collections import defaultdict
    lens = defaultdict(int)
    openers = defaultdict(int)
    finales = defaultdict(int)
    for t in timeline:
        lens[t["arc_id"]] += 1
        openers[t["arc_id"]] += t["opener"]
        finales[t["arc_id"]] += t["finale"]
    max_arc = max(lens)
    for aid, length in lens.items():
        if aid < max_arc:                       # only completed arcs
            assert 5 <= length <= 7, f"arc {aid} ran {length} episodes"
            assert openers[aid] == 1, f"arc {aid} had {openers[aid]} openers"
            assert finales[aid] == 1, f"arc {aid} had {finales[aid]} finales"


def test_consecutive_arcs_have_different_genres():
    timeline, _ = _simulate(20)
    genre_of = {}
    for t in timeline:
        genre_of.setdefault(t["arc_id"], t["genre"])
    order = [genre_of[a] for a in sorted(genre_of)]
    for i in range(len(order) - 1):
        assert order[i] != order[i + 1], f"arcs repeated genre: {order}"


def test_finale_opens_the_next_arc_for_tomorrow():
    # advance to exactly a finale, then confirm the NEXT plan is a fresh arc opener
    state = {}
    finale_seen = False
    for _ in range(8):
        plan = arc.plan_next_episode(state)
        was_finale = plan["is_arc_finale"]
        state = arc.apply_generated(plan["state"], recap="r", facts=[],
                                    was_finale=was_finale)
        if was_finale:
            finale_seen = True
            nxt = arc.plan_next_episode(state)
            assert nxt["is_arc_opener"] is True
            assert nxt["arc"]["episode_in_arc"] == 1
            assert nxt["arc"]["arc_id"] == plan["arc"]["arc_id"] + 1
            assert nxt["arc"]["genre"] != plan["arc"]["genre"]
            break
    assert finale_seen


def test_record_winning_choice_builds_listener_echo_history():
    state = {}
    for i in range(1, arc.MAX_PAST_CHOICES + 4):
        state = arc.record_winning_choice(state, f"choice-{i}")
    assert len(state["past_choices"]) == arc.MAX_PAST_CHOICES     # capped
    assert state["past_choices"][-1] == f"choice-{arc.MAX_PAST_CHOICES + 3}"
    assert state["winning_choice"] == f"choice-{arc.MAX_PAST_CHOICES + 3}"


def test_established_facts_accumulate_within_an_arc_and_are_capped():
    _timeline, state = _simulate(3)      # 3 episodes into arc 1 (planned 6)
    facts = state["arc"]["established_facts"]
    assert facts, "facts should accumulate within an arc"
    assert len(facts) <= arc.MAX_FACTS


def test_facts_reset_when_a_new_arc_opens():
    state = {}
    prev_arc_id = None
    for _ in range(8):
        plan = arc.plan_next_episode(state)
        state = arc.apply_generated(plan["state"], recap="r",
                                    facts=["a fact"], was_finale=plan["is_arc_finale"])
        if plan["is_arc_finale"]:
            # after a finale the new arc starts with no established facts
            assert state["arc"]["established_facts"] == []
            assert state["arc"]["arc_id"] == plan["arc"]["arc_id"] + 1
            break
