#!/usr/bin/env python3
"""
Preprocess **olympus_all_txs.csv** to tag card transactions as POS or ATM.

Usage
-----
python preprocess_card_type.py \
    --olympus olympus_all_txs.csv \
    --tribe "UGLYCASH Unit Economics Model - tribe_cards_transactions.csv" \
    --output olympus_all_txs_tagged.csv

The script keeps the original file intact and writes a new CSV with the
column *activity_type* updated from "card" to "card_POS" or "card_ATM"
whenever a match (date, amount) is found in the tribe file.
"""

import argparse
import os
import pandas as pd
from datetime import datetime
from typing import Tuple


def _prepare(df: pd.DataFrame, date_col: str, amount_col: str) -> pd.DataFrame:
    """Return a DataFrame with helper columns 'tx_date' and 'amount_round'."""
    # Parse dates and strip the time component
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

    # Drop timezone (if any) and keep date only
    tx_datetime = df[date_col]
    if tx_datetime.dt.tz is not None:
        tx_datetime = tx_datetime.dt.tz_localize(None)
    df['tx_date'] = tx_datetime.dt.floor('D')

    # Use absolute amount and round to 2 decimals for robust matching
    df['amount_round'] = df[amount_col].astype(float).abs().round(2)
    return df


def tag_card_transactions(
    olympus_path: str,
    tribe_path: str,
    output_path: str,
    ) -> None:
    """Tag card rows in *olympus_path* and write *output_path*."""

    print(f"Loading olympus transactions from {olympus_path} …")
    oly = pd.read_csv(olympus_path, parse_dates=['created_at'])

    print(f"Loading tribe card data from {tribe_path} …")
    tribe = pd.read_csv(tribe_path)

    # Prepare helper cols --------------------------------------------------
    oly = _prepare(oly, 'created_at', 'amount')
    tribe = _prepare(tribe, 'settlementdate', 'card_holder_amount')

    # Extract tag (POS / ATM) from 'Total' column (case-insensitive) ------
    tribe['card_tag'] = tribe['Total'].str.upper().str.contains('ATM').map({True: 'ATM', False: 'POS'})

    # ------------------------------------------------------------------
    # Fuzzy matching: +-1 day, amount within +-0.5 %
    # Expand tribe rows with date shifts -1, 0, +1 day
    shifts = [-1, 0, 1]
    tribe_expanded = pd.concat([
        tribe.assign(tx_date=tribe['tx_date'] + pd.Timedelta(d, unit='D'))
        for d in shifts
    ], ignore_index=True)

    tribe_match = tribe_expanded[['tx_date', 'amount_round', 'card_tag']]

    # Index for fast lookup
    tribe_groups = tribe_match.groupby('tx_date')

    def match_row(row):
        group = tribe_groups.get_group(row['tx_date']) if row['tx_date'] in tribe_groups.groups else None
        if group is None:
            return ''
        tol = 0.005  # 0.5 %
        diffs = (group['amount_round'] - row['amount_round']).abs() / row['amount_round']
        ok = diffs <= tol
        if ok.any():
            return 'ATM' if (group.loc[ok, 'card_tag'] == 'ATM').any() else 'POS'
        return ''

    card_mask = oly['activity_type'] == 'card'
    sub = oly.loc[card_mask, ['tx_date', 'amount_round']]
    tags = sub.apply(match_row, axis=1)

    new_types = oly.loc[card_mask, 'activity_type']
    new_types = new_types.where(tags == '', 'card_' + tags)
    oly.loc[card_mask, 'activity_type'] = new_types

    # Drop helper cols & save ---------------------------------------------
    oly = oly.drop(columns=['tx_date', 'amount_round'])

    oly.to_csv(output_path, index=False)
    print(f"✓ Tagged file written to {output_path} ({len(oly):,} rows)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tag card transactions as POS or ATM.')
    parser.add_argument('--olympus', default='olympus_all_txs.csv', help='Path to olympus_all_txs.csv')
    parser.add_argument('--tribe', required=True, help='Path to tribe_cards_transactions.csv')
    parser.add_argument('--output', default='olympus_all_txs_tagged.csv', help='Output CSV path')
    args = parser.parse_args()

    tag_card_transactions(args.olympus, args.tribe, args.output) 