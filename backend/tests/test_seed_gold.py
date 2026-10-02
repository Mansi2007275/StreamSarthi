from app.services.calibration import load_items
from app.services.game import gold_rows_from_calibration
from scripts.seed_gold import new_rows

ROWS = gold_rows_from_calibration(load_items())


def test_everything_is_new_against_an_empty_table():
    assert len(new_rows(ROWS, [])) == len(ROWS)


def test_running_twice_inserts_nothing_the_second_time():
    assert new_rows(ROWS, ROWS) == []


def test_only_the_missing_rows_are_inserted():
    pending = new_rows(ROWS, ROWS[:1])
    assert len(pending) == len(ROWS) - 1
    assert ROWS[0] not in pending


def test_a_retired_gold_item_is_not_re_added():
    # matched on (indicator_id, image_path), so deactivating one does not resurrect it
    retired = [{**ROWS[0], "active": False}]
    assert ROWS[0] not in new_rows(ROWS, retired)
