#!/usr/bin/env python
"""只跑 preprocess 步骤，生成 stage='init' 的 EvaluationSample。

用法:
    cd RCAgentEval
    uv run python scripts/preprocess_only.py
    uv run python scripts/preprocess_only.py --exp_id thinkdepthai_init --config_name rcabench_langgraph
"""
import argparse

from sota_rca.config import ConfigLoader
from sota_rca.eval import BaseBenchmark


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_name", type=str, default="rcabench_langgraph",
                        help="configs/eval/ 下的配置名")
    parser.add_argument("--exp_id", type=str, default="thinkdepthai_init",
                        help="EvaluationSample 的 exp_id")
    args = parser.parse_args()

    config = ConfigLoader.load_eval_config(args.config_name)
    config.exp_id = args.exp_id

    runner = BaseBenchmark(config)
    results = runner.preprocess()
    print(f"Done: {len(results)} samples with stage='init', exp_id='{args.exp_id}'")


if __name__ == "__main__":
    main()
