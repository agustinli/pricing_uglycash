#!/usr/bin/env python3
"""Tag card transactions as ATM or POS using ATM list from tribe file.

Rules
-----
1. Read tribe file and keep only rows whose 'Total' contains 'ATM'.
2. Build lookup by tx_date (floor to day) -> list of amounts (abs, 2 decimals).
   Also include dates shifted -1 and +1 day for tolerance in dates.
3. Stream-read olympus file. For each row where activity_type == 'card':
   a. Get tx_date and amount_abs (2 decimals).
   b. If within ±0.1 % of any amount in lookup for that date, tag as card_ATM.
      Otherwise tag as card_POS.
4. Non card rows remain unchanged.
5. Write output CSV.

Usage:
python preprocess_card_type_atm_first.py \
   --olympus olympus_all_txs.csv \
   --tribe "UGLYCASH Unit Economics Model - tribe_cards_transactions.csv" \
   --output olympus_all_txs_tagged_atm.csv
"""
import argparse
import pandas as pd
import numpy as np
from collections import Counter, defaultdict

def build_atm_lookup(tribe_path: str):
    """Create lookup of ATM amounts per date.

    The Tribe cards export changed schema over time:
    • Old format had a column named ``Total`` which included the string "ATM" for ATM cash withdrawals.
    • New format replaced this with a column ``transaction_type`` that takes the value "ATM".

    This helper detects the available schema and filters ATM rows accordingly so that the rest of the
    pipeline remains unchanged.
    """
    print("Loading tribe file…")

    # Inspect header first to decide which columns to load
    header_cols = pd.read_csv(tribe_path, nrows=0).columns.str.lower().tolist()

    has_total = 'total' in header_cols
    has_tx_type = 'transaction_type' in header_cols

    if not (has_total or has_tx_type):
        raise ValueError("Tribe file must contain either a 'Total' or 'transaction_type' column to identify ATM rows")

    # Columns required in all cases
    base_cols = ['settlementdate', 'card_holder_amount']

    if has_total:
        cols = base_cols + ['Total']
        df = pd.read_csv(tribe_path, usecols=cols)
        atm_mask = df['Total'].str.upper().str.contains('ATM', na=False)
    else:  # new schema with transaction_type
        cols = base_cols + ['transaction_type']
        df = pd.read_csv(tribe_path, usecols=cols)
        atm_mask = df['transaction_type'].str.upper() == 'ATM'

    df = df.loc[atm_mask].copy()

    # Prepare date and amount
    dt = pd.to_datetime(df['settlementdate'], errors='coerce')
    df['tx_date'] = dt.dt.tz_localize(None).dt.date
    df['amt_cents'] = (df['card_holder_amount'].astype(float).abs() * 100).round().astype('int64')

    # Build Counter per date (allows single use of each amount)
    lookup: dict = defaultdict(Counter)
    for _, row in df.iterrows():
        lookup[row['tx_date']][row['amt_cents']] += 1

    total_refs = df.shape[0]
    print(f"ATM reference built: {total_refs} rows across {len(lookup)} dates")
    return lookup

def tag_file(olympus_path: str, output_path: str, atm_lookup: dict):
    print("Tagging olympus file…")
    reader = pd.read_csv(olympus_path, chunksize=250_000, parse_dates=['created_at'])
    first = True
    tol_pct = 0.001  # 0.1 %

    for chunk_idx, chunk in enumerate(reader):
        card_mask = chunk['activity_type'] == 'card'
        if card_mask.any():
            sub = chunk.loc[card_mask, ['created_at', 'amount']].copy()
            dt = pd.to_datetime(sub['created_at'], errors='coerce')
            sub['tx_date'] = dt.dt.tz_localize(None).dt.date
            # Asegurar que amount sea numérico (puede venir como str)
            amt = pd.to_numeric(sub['amount'], errors='coerce').fillna(0).abs()
            sub['amt_cents'] = (amt * 100).round().astype('int64')

            tags = []
            for date, amt in zip(sub['tx_date'], sub['amt_cents']):
                match = False
                amounts = atm_lookup.get(date)
                if amounts:
                    tol = max(1, int(round(amt * tol_pct)))
                    # iterate over reference amounts
                    for ref_amt, cnt in amounts.items():
                        if cnt==0:
                            continue
                        if abs(ref_amt - amt) <= tol:
                            match = True
                            amounts[ref_amt]-=1  # consume
                            if amounts[ref_amt]==0:
                                del amounts[ref_amt]
                            break
                tags.append('card_ATM' if match else 'card_POS')
            chunk.loc[card_mask, 'activity_type'] = tags
        chunk.to_csv(output_path, mode='w' if first else 'a', index=False, header=first)
        first = False
        print(f"Processed chunk {chunk_idx+1}")

    print("✓ Tagging complete →", output_path)


def main():
    parser = argparse.ArgumentParser(description="Tag card ATM/POS with ATM-first approach")
    parser.add_argument('--olympus', default='olympus_all_txs.csv')
    parser.add_argument('--tribe', required=True)
    parser.add_argument('--output', default='olympus_all_txs_tagged_atm.csv')
    args = parser.parse_args()

    lookup = build_atm_lookup(args.tribe)
    tag_file(args.olympus, args.output, lookup)

if __name__ == '__main__':
    main() 