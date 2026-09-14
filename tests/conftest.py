import pytest
from rotowire_bench.config import load_config
from rotowire_bench.schemas import EvaluationGold, InferenceInput
from rotowire_bench.data import parse_table_line


@pytest.fixture
def config():
    return load_config("configs/main.yaml")


@pytest.fixture
def gold():
    # Synthetic fixture exclusively for logic tests; not benchmark data.
    return EvaluationGold(sample_id="synthetic",original_index=0,tables=parse_table_line(
        "Team: <NEWLINE> |  | Total points | <NEWLINE> | Owls | 100 | <NEWLINE> "
        "Player: <NEWLINE> |  | Points | Total rebounds | <NEWLINE> | Alice Smith | 24 | 7 | <NEWLINE> | Bob Jones | 9 |  |"))


@pytest.fixture
def item():
    return InferenceInput(sample_id="synthetic",full_text="Alice Smith recorded twenty four points and seven rebounds. Bob Jones scored nine points. The Owls scored one hundred points.")
