"""Starter fixture suite for the pseudonymiser. Per its docstring
(app/modules/ai_gateway/pseudonymiser.py), this is meant to grow into the real spec --
covering names embedded in free text ("Mrs T. was visited by her daughter Susan"),
partial names, and other NER-only cases the regex layer can't catch -- before Phase 1
is considered done."""

from app.modules.ai_gateway.pseudonymiser import Pseudonymiser


class _FakeMappingRepository:
    async def get_or_create_token(self, care_home_id, resident_id) -> str:
        return "RESIDENT_TEST"


async def test_strips_nhs_number():
    pseudonymiser = Pseudonymiser(_FakeMappingRepository())
    _, text = await pseudonymiser.pseudonymise("home", "resident", "NHS number 485 777 3456 on file.")
    assert "485 777 3456" not in text


async def test_strips_uk_phone_number():
    pseudonymiser = Pseudonymiser(_FakeMappingRepository())
    _, text = await pseudonymiser.pseudonymise("home", "resident", "Call next of kin on 0161 496 0000.")
    assert "0161 496 0000" not in text


async def test_substitutes_resident_placeholder():
    pseudonymiser = Pseudonymiser(_FakeMappingRepository())
    token, text = await pseudonymiser.pseudonymise("home", "resident", "{{RESIDENT}} ate well today.")
    assert token in text
    assert "{{RESIDENT}}" not in text


def test_re_identify_restores_real_name():
    pseudonymiser = Pseudonymiser(_FakeMappingRepository())
    result = pseudonymiser.re_identify("RESIDENT_TEST", "Margaret Baker", "RESIDENT_TEST slept well.")
    assert result == "Margaret Baker slept well."
