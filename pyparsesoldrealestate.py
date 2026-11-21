"""Entry point for parsing sold realestate.com.au listings."""

from __future__ import annotations

import argparse

from pyparserealestate import ParseSummary, parse_all_realestate


SOLD_SEARCH_URL = (
    "https://www.realestate.com.au/sold/map-1?"
    "boundingBox=-27.29308591361328%2C152.6743119059878%2C"
    "-27.985313321663025%2C153.26482704270654"
    "&source=refinement&sourcePage=map&sourceElement=location-tile-search"
)


def parse_all_sold_realestate(
    search_url: str = SOLD_SEARCH_URL,
    *,
    batch_size: int = 25,
    max_scrolls: int = 100,
    stable_rounds: int = 5,
    delay_min: float = 2.0,
    delay_max: float = 5.0,
    batch_pause: float = 120.0,
) -> ParseSummary:
    """Parse the sold-map results and force every row's status to sold."""
    return parse_all_realestate(
        search_url,
        listing_kind="sold",
        listing_status="sold",
        batch_size=batch_size,
        max_scrolls=max_scrolls,
        stable_rounds=stable_rounds,
        delay_min=delay_min,
        delay_max=delay_max,
        batch_pause=batch_pause,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse sold listings from a realestate.com.au map search."
    )
    parser.add_argument("--search-url", default=SOLD_SEARCH_URL)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-scrolls", type=int, default=100)
    parser.add_argument("--stable-rounds", type=int, default=5)
    parser.add_argument("--delay-min", type=float, default=2.0)
    parser.add_argument("--delay-max", type=float, default=5.0)
    parser.add_argument("--batch-pause", type=float, default=120.0)
    args = parser.parse_args()

    summary = parse_all_sold_realestate(
        args.search_url,
        batch_size=args.batch_size,
        max_scrolls=args.max_scrolls,
        stable_rounds=args.stable_rounds,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        batch_pause=args.batch_pause,
    )
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
