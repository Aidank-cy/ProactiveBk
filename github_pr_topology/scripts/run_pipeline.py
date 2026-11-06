"""Prepare sample, collect real GitHub evidence, then build graph and reports."""
from prepare_sample import main as prepare
from run_collection import main as collect
from build_graph import main as build
from validate_outputs import validate

if __name__ == '__main__':
    prepare()
    collect()
    build()
    validate()
