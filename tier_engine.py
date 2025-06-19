#!/usr/bin/env python3
"""Tier Engine
-------------
Asigna un nivel (Tier1-Tier4) a cada usuario-mes según criterios de gasto o balance
comparando con el mes previo y respetando la regla «máx. descenso 1 tier/mes».

También genera un DataFrame skeleton de *rewards* (de momento solo columna
`rewards_usd`=0) que luego se completará con el cálculo de beneficios.
"""

from __future__ import annotations

from typing import Dict, Tuple
import pandas as pd


DEFAULT_THRESHOLDS: Dict[str, int] = {
    # Card spending + investment (eUSD)
    'tier2_spend': 300,
    'tier3_spend': 500,
    'tier4_spend': 1000,
    # End-of-month balance (eUSD)
    'tier2_balance': 200,
    'tier3_balance': 500,
    'tier4_balance': 2000,
}

# Default reward assumptions (can be overridden). Percentages are monthly.
# Keys follow pattern '<tier>_cashback_pct' and '<tier>_yield_pct'.
# Cashback applies on total_card_spending; extra yield applies over balances up to 1k eUSD.
DEFAULT_REWARD_PARAMS: Dict[str, float] = {
    # Cashback on total spend
    'tier2_cashback_pct': 0.005,   # 0.5 %
    'tier3_cashback_pct': 0.01,    # 1 %
    'tier4_cashback_pct': 0.02,    # 2 %

    # Extra yield on balances ≤ 1k eUSD (monthly pct)
    'tier2_yield_pct': 0.0015,     # 0.15 %
    'tier3_yield_pct': 0.003,      # 0.3 %
    'tier4_yield_pct': 0.006,      # 0.6 %
}

TIER_ORDER = ['tier1', 'tier2', 'tier3', 'tier4']
TIER_RANK = {t: i for i, t in enumerate(TIER_ORDER, 1)}  # tier1->1 .. tier4->4


def _qualify_tier(row: pd.Series, thresholds: Dict[str, int]) -> str:
    """Return highest tier met by spend OR balance for the *current* row."""
    spend = row['total_card_spending']
    bal = row['end_balance']

    # evaluate from highest to lowest
    if spend >= thresholds['tier4_spend'] or bal >= thresholds['tier4_balance']:
        return 'tier4'
    if spend >= thresholds['tier3_spend'] or bal >= thresholds['tier3_balance']:
        return 'tier3'
    if spend >= thresholds['tier2_spend'] or bal >= thresholds['tier2_balance']:
        return 'tier2'
    return 'tier1'


def assign_tiers(
    user_segments: pd.DataFrame,
    thresholds: Dict[str, int] | None = None,
    reward_params: Dict[str, float] | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Asigna tier y devuelve:
        1. tiers_monthly: user_id, year_month, tier
        2. tier_counts   : year_month, tier, users
    Parámetros
    ----------
    user_segments : DataFrame con columnas ['user_id','year_month','total_card_spending','end_balance']
    thresholds    : dict con llaves tierX_spend / tierX_balance. Si None usa DEFAULT_THRESHOLDS.
    reward_params : dict con llaves tierX_cashback_pct / tierX_yield_pct. Si None usa DEFAULT_REWARD_PARAMS.
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS.copy()

    if reward_params is None:
        reward_params = DEFAULT_REWARD_PARAMS.copy()

    # asegurar ordering temporal
    user_segments = user_segments.sort_values(['user_id', 'year_month']).copy()
    user_segments['year_month'] = user_segments['year_month'].astype(str)

    results = []

    # procesar por usuario
    for user_id, grp in user_segments.groupby('user_id'):
        prev_tier = None  # se asignará en la primera iteración
        for _, row in grp.iterrows():
            qualified = _qualify_tier(row, thresholds)

            if prev_tier is None:
                # Primer mes: todos comienzan en tier4
                tier = 'tier4'
            else:
                # ranks: 1=base (tier1) ... 4=mejor (tier4)
                prev_rank = TIER_RANK[prev_tier]
                qual_rank = TIER_RANK[qualified]

                if qual_rank > prev_rank:
                    # mejora de tier (sube)
                    tier = qualified
                else:
                    # empeora: bajar máx 1 nivel por mes
                    diff = prev_rank - qual_rank
                    if diff > 1:
                        new_rank = prev_rank - 1  # baja solo 1 nivel
                        tier = TIER_ORDER[new_rank - 1]
                    else:
                        tier = qualified

            results.append({'user_id': user_id, 'year_month': row['year_month'], 'tier': tier})
            prev_tier = tier

    tiers_df = pd.DataFrame(results)

    # counts
    counts = tiers_df.groupby(['year_month', 'tier'])['user_id'].nunique().reset_index(name='users')

    # ------------------------------------------------------------------
    # Calcular rewards (cashback + extra yield) por usuario-mes
    # ------------------------------------------------------------------
    rewards_rows = []
    merged = tiers_df.merge(user_segments, on=['user_id', 'year_month'], how='left')
    for _, r in merged.iterrows():
        tier = r['tier']
        cb_key = f"{tier}_cashback_pct"
        yld_key = f"{tier}_yield_pct"
        cashback_pct = reward_params.get(cb_key, 0.0)
        yield_pct = reward_params.get(yld_key, 0.0)

        spend = r.get('total_card_spending', 0.0)
        bal = r.get('end_balance', 0.0)
        extra_yield_base = min(bal, 1000)

        rewards_usd = cashback_pct * spend + yield_pct * extra_yield_base
        rewards_rows.append({'user_id': r['user_id'], 'year_month': r['year_month'], 'rewards_usd': round(rewards_usd, 2)})

    rewards_df = pd.DataFrame(rewards_rows)

    return tiers_df, counts, rewards_df


if __name__ == "__main__":
    # quick smoke test
    data = {
        'user_id': [1, 1, 1, 2, 2],
        'year_month': ['2025-04', '2025-05', '2025-06', '2025-05', '2025-06'],
        'total_card_spending': [0, 1200, 400, 50, 600],
        'end_balance': [50, 100, 3000, 2500, 100],
    }
    us = pd.DataFrame(data)
    tiers, counts, rewards = assign_tiers(us)
    print(tiers)
    print(counts) 