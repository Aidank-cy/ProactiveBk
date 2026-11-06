from pathlib import Path
import logging
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.build_graph import GraphBuilder
from analysis.metrics import analyze
from analysis.cases_reports import select_cases, generate_reports


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    cfg = yaml.safe_load((ROOT / 'config.yaml').read_text())
    builder = GraphBuilder(ROOT, cfg).build()
    aggregate, repository_metrics, patterns, components = analyze(builder)
    cases = select_cases(builder, patterns, limit=15)
    generate_reports(builder, aggregate, repository_metrics, patterns, components, cases)
    logging.info('analysis_complete collected_seed=%s cases=%s nodes=%s edges=%s', aggregate['seed_prs'], len(cases), len(builder.nodes), len(builder.edges))


if __name__ == '__main__':
    main()
