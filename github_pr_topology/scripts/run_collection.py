import logging
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from collector.collect import collect_all

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "collection.log")])
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    collect_all(ROOT, cfg)


if __name__ == "__main__":
    main()
