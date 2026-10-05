"""Ví dụ: python radarChartPlot.py --p1 norris --p2 max_verstappen --season 2025."""
import argparse
from pathlib import Path
from f1lab.analysis import AnalysisService
from f1lab.analysis.plots import radar_figure
from f1lab.db import Database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--p1', required=True, help='driver_id trong driver_season.csv')
    parser.add_argument('--p2', required=True)
    parser.add_argument('--season', type=int, default=2025)
    parser.add_argument('--Attribute', nargs='+', default=None)
    parser.add_argument('--output', type=Path, default=Path('deliverables/radar.png'))
    args = parser.parse_args()
    db = Database()
    try:
        service = AnalysisService(db.engine)
        profiles = service.profiles(service.results(), args.season)
        fig = radar_figure(profiles, [args.p1, args.p2], args.Attribute)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.output, dpi=160)
        print(args.output)
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        db.close()


if __name__ == '__main__':
    main()
