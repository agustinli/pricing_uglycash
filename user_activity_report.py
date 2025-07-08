#!/usr/bin/env python3
"""User Activity Report
========================
Calculates key activity metrics for a list of users using the raw transactions
file (``olympus_all_txs_tagged_atm.csv`` by default).

Usage
-----
    python user_activity_report.py --users u1 u2 u3 \
        [--txfile olympus_all_txs_tagged_atm.csv] [--out report.csv]

The script streams the CSV in chunks so it can handle very large datasets.
It outputs a CSV/TSV (or prints to console) with the following columns:

| Column                               | Description                                    |
|--------------------------------------|------------------------------------------------|
| user_id                              | User UUID                                      |
| avg_balance                          | Average end balance (from user_segments_monthly)|
| btceth_trade_volume                  | Total absolute volume BTC+ETH buy/sell         |
| fiat_deposit_volume                  | Total fiat deposit volume (cash_load credit)    |
| fiat_deposit_count                   | Number of fiat deposit txs                     |
| fiat_withdraw_volume                 | Total fiat withdrawal volume (cash_* debit)    |
| fiat_withdraw_count                  | Number of fiat withdrawal txs                  |
| crypto_deposit_volume                | Volume incoming_crypto                         |
| crypto_deposit_count                 | Count incoming_crypto                          |
| crypto_withdraw_volume               | Volume withdraw_crypto                         |
| crypto_withdraw_count                | Count withdraw_crypto                          |
| atm_withdraw_volume                  | Volume card_ATM                                |
| atm_withdraw_count                   | Count card_ATM                                 |
| card_pos_volume                      | Volume card_POS                                |
| card_pos_count                       | Count card_POS                                 |

The balance information comes from ``segmentation_outputs/user_segments_monthly.csv``.
If the file is missing, the ``avg_balance`` column will be NaN.
"""

import argparse
import os
from typing import List, Dict
import pandas as pd
from collections import defaultdict

CHUNK_SIZE = 250_000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_avg_balances(users: List[str], seg_file: str = 'segmentation_outputs/user_segments_monthly.csv') -> Dict[str, float]:
    """Return average end_balance per user from segmentation file (if present)."""
    if not os.path.isfile(seg_file):
        return {u: float('nan') for u in users}

    df = pd.read_csv(seg_file, usecols=['user_id', 'end_balance'])
    df = df[df['user_id'].isin(users)]
    return df.groupby('user_id')['end_balance'].mean().to_dict()


def update_metrics(row: pd.Series, metrics: Dict[str, Dict[str, float]]):
    """Update metrics dict for a single row (already filtered by user)."""
    uid = row['user_id']
    m = metrics[uid]
    atype = row['activity_type']
    amt = abs(row['amount'])  # always positive volume

    # Categorise ------------------------------------------------------
    if atype == 'incoming_crypto':
        m['crypto_deposit_volume'] += amt
        m['crypto_deposit_count'] += 1
    elif atype == 'withdraw_crypto':
        m['crypto_withdraw_volume'] += amt
        m['crypto_withdraw_count'] += 1
    elif atype in ('cash_load', 'cash_withdrawal'):
        if row['amount'] > 0:  # deposit (credit)
            m['fiat_deposit_volume'] += amt
            m['fiat_deposit_count'] += 1
        else:                  # withdrawal (debit)
            m['fiat_withdraw_volume'] += amt
            m['fiat_withdraw_count'] += 1
    elif atype == 'card_ATM':
        m['atm_withdraw_volume'] += amt
        m['atm_withdraw_count'] += 1
    elif atype == 'card_POS':
        m['card_pos_volume'] += amt
        m['card_pos_count'] += 1
    elif atype == 'crypto_investment' and str(row['currency']).upper() in {'BTC', 'ETH'}:
        m['btceth_trade_volume'] += amt


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description='Generate activity metrics for given users.')
    p.add_argument('--users', nargs='+', required=True, help='List of user UUIDs')
    p.add_argument('--txfile', default='olympus_all_txs_tagged_atm.csv', help='Transactions CSV')
    p.add_argument('--out', default='-', help='Output CSV file ("-" for stdout)')
    return p.parse_args()


def main():
    args = parse_args()
    users = args.users

    # Prepare metrics dict -------------------------------------------
    keys = [
        'btceth_trade_volume',
        'fiat_deposit_volume', 'fiat_deposit_count',
        'fiat_withdraw_volume', 'fiat_withdraw_count',
        'crypto_deposit_volume', 'crypto_deposit_count',
        'crypto_withdraw_volume', 'crypto_withdraw_count',
        'atm_withdraw_volume', 'atm_withdraw_count',
        'card_pos_volume', 'card_pos_count',
    ]
    metrics = {u: defaultdict(float) for u in users}

    # Stream CSV ------------------------------------------------------
    usecols = ['user_id', 'activity_type', 'currency', 'amount']
    for chunk in pd.read_csv(args.txfile, chunksize=CHUNK_SIZE, usecols=usecols):
        sub = chunk[chunk['user_id'].isin(users)].copy()
        if sub.empty:
            continue
        sub['amount'] = pd.to_numeric(sub['amount'], errors='coerce').fillna(0)
        for _idx, row in sub.iterrows():
            update_metrics(row, metrics)

    # Add average balances -------------------------------------------
    balances = load_avg_balances(users)

    # Build output DataFrame -----------------------------------------
    rows = []
    for uid in users:
        row = {'user_id': uid, 'avg_balance': balances.get(uid, float('nan'))}
        row.update(metrics[uid])
        rows.append(row)

    out_df = pd.DataFrame(rows)

    if args.out == '-' or args.out.lower() == 'stdout':
        print(out_df.to_csv(index=False))
    else:
        out_df.to_csv(args.out, index=False)
        print(f"✓ Report written to {args.out} ({len(out_df)} rows)")


if __name__ == '__main__':
    main() 