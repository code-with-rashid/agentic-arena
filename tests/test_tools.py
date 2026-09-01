from arena.tools import calculator, dispatch, search


def test_calculator_basic():
    assert calculator("17 * 23 + 4") == "395"
    assert calculator("144 / 12 - 5") == "7"
    assert calculator("2 ** 10") == "1024"


def test_calculator_float_formatting():
    assert calculator("330 * 3.28084").startswith("1082.6")


def test_calculator_rejects_names_and_calls():
    assert calculator("__import__('os')").startswith("ERROR")
    assert calculator("foo + 1").startswith("ERROR")


def test_search_finds_corpus_fact():
    out = search("Eiffel Tower completed")
    assert "1889" in out


def test_search_no_results():
    assert search("zzz nonexistent qwxyz") == "No results."


def test_dispatch_json_args():
    assert dispatch("calculator", '{"expr": "6*7"}') == "42"
    assert dispatch("unknown", {}).startswith("ERROR")
