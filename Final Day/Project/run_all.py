"""
One-shot runner: generate the dataset, then run the full analytics pipeline.

    python run_all.py            # generate data + run pipeline
    python run_all.py --skip-gen # keep existing CSVs, just re-run analytics

After this, start the dashboard with:  python app.py
"""
import sys
from data_generator import generate_data
from src import pipeline


def main():
    if "--skip-gen" not in sys.argv:
        generate_data.main()
        print()
    pipeline.run()
    print("\nAll done. Launch the dashboard with:  python app.py")


if __name__ == "__main__":
    main()
