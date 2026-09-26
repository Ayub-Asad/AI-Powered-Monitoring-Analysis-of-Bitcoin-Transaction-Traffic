"""Offline ML commands; evaluation never fits or recalibrates a model."""
import argparse
import json
from pathlib import Path
from .schema import ROOT, load_config
from .workflow import training_run, evaluate_run, score_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    train = commands.add_parser('train')
    train.add_argument('--config', type=Path, default=ROOT/'configs/ml_baseline.json')
    evaluation = commands.add_parser('evaluate')
    evaluation.add_argument('--run', type=Path, required=True)
    score = commands.add_parser('score')
    score.add_argument('--run', type=Path, required=True)
    score.add_argument('--input', type=Path, required=True)
    score.add_argument('--out', type=Path, required=True)
    score.add_argument('--seed', type=int)
    args = parser.parse_args()
    if args.command == 'train':
        result = training_run(load_config(args.config))
        print(json.dumps({'status': result['status'], 'feature_shapes': result['feature_shapes'], 'timings': result['timings']}, indent=2))
    elif args.command == 'evaluate':
        result = evaluate_run(args.run)
        print(json.dumps({'reference_model': result['reference_model'], 'seed_summary': result['seed_summary'], 'evaluation_total_seconds': result['evaluation_total_seconds']}, indent=2))
    else:
        print(json.dumps(score_file(args.run, args.input, args.out, args.seed), indent=2))


if __name__ == '__main__':
    main()
