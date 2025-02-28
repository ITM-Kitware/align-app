from copy import deepcopy

from swagger_client.models import ActionTypeEnum
from align_system.utils import logging

log = logging.getLogger(__name__)


def filter_actions(current_state, available_actions):
    # scenario_complete = current_state.scenario_complete

    # Tracking these to prevent getting stuck in a loop
    noop_actions = []

    # last_scene_id = None

    available_actions_filtered = []
    for a in available_actions:
        if len(current_state.characters) == 0:
            # Restrict actions that require a character when
            # no characters exist
            if a.action_type in {
                ActionTypeEnum.APPLY_TREATMENT,
                ActionTypeEnum.CHECK_ALL_VITALS,
                ActionTypeEnum.CHECK_PULSE,
                ActionTypeEnum.CHECK_RESPIRATION,
                ActionTypeEnum.MOVE_TO_EVAC,
                ActionTypeEnum.TAG_CHARACTER,
                ActionTypeEnum.CHECK_BLOOD_OXYGEN,
            }:
                log.debug(
                    "No characters in current state, not allowing {} action".format(
                        a.action_type
                    )
                )
                continue

        if a.action_type == ActionTypeEnum.TAG_CHARACTER:
            # Don't let ADM choose to tag a character unless there are
            # still untagged characters
            untagged_characters = [
                c for c in current_state.characters if c.tag is None and not c.unseen
            ]
            if len(untagged_characters) == 0:
                log.debug(
                    "No untagged characters remaining, not allowing {} action".format(
                        ActionTypeEnum.TAG_CHARACTER
                    )
                )
                continue

        unvisited_characters = [
            c
            for c in current_state.characters
            if not c.unseen and (c.visited is None or not c.visited)
        ]
        if a.action_type in {
            ActionTypeEnum.CHECK_ALL_VITALS,
            ActionTypeEnum.CHECK_PULSE,
            ActionTypeEnum.CHECK_RESPIRATION,
            ActionTypeEnum.CHECK_BLOOD_OXYGEN,
        }:
            if len(unvisited_characters) == 0:
                log.debug(
                    "No unvisited characters remaining, not allowing {} action".format(
                        a.action_type
                    )
                )
                continue

        if (
            a.action_type == ActionTypeEnum.APPLY_TREATMENT
            and a.parameters is not None
            and "treatment" in a.parameters
        ):
            treatment_available = False
            for s in current_state.supplies:
                if a.parameters["treatment"] == s.type:
                    if s.quantity > 0:
                        treatment_available = True
                    break

            if not treatment_available:
                log.debug(
                    "Insufficient supplies, not allowing "
                    f"{ActionTypeEnum.APPLY_TREATMENT} action"
                )
                continue

        is_a_noop_action = False
        for noop_action in noop_actions:
            if a == noop_action:
                is_a_noop_action = True

            # HACK: In some cases the ADM can get stuck
            # attempting to use the generic APPLY_TREATMENT
            # action over and over to no affect
            if noop_action.action_type == ActionTypeEnum.APPLY_TREATMENT:
                _tmp_noop_action = deepcopy(noop_action)

                _tmp_noop_action.parameters = None
                _tmp_noop_action.character_id = None

                if a == _tmp_noop_action:
                    is_a_noop_action = True
                    log.debug(
                        "Handled case where ADM might be stuck "
                        "applying treatment over and over to no "
                        "effect, not allowing {} action".format(a.action_type)
                    )

        if is_a_noop_action:
            log.debug(
                "Already took this action and there was no "
                "change in the scenario state, not allowing "
                "{} action".format(a.action_type)
            )
            continue

        available_actions_filtered.append(a)

    return available_actions_filtered
