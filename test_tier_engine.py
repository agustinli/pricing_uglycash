import pandas as pd
from tier_engine import assign_tiers


def test_assign_tiers():
    data = {
        'user_id': [1, 1, 1, 2, 2],
        'year_month': ['2025-04', '2025-05', '2025-06', '2025-05', '2025-06'],
        'total_card_spending': [0, 1200, 400, 50, 600],
        'end_balance': [50, 100, 100, 2500, 100],
    }
    df = pd.DataFrame(data)
    tiers_df, counts_df, _ = assign_tiers(df)

    # user 1 expected tiers: start tier4, May tie r4 (spend>=1000), Jun maybe tier3 (down only 1) even though spend 400 qualifies tier2.
    assert tiers_df.loc[(tiers_df.user_id == 1) & (tiers_df.year_month == '2025-04'), 'tier'].item() == 'tier4'
    assert tiers_df.loc[(tiers_df.user_id == 1) & (tiers_df.year_month == '2025-05'), 'tier'].item() == 'tier4'
    assert tiers_df.loc[(tiers_df.user_id == 1) & (tiers_df.year_month == '2025-06'), 'tier'].item() == 'tier3'

    # counts sanity
    assert counts_df.loc[(counts_df.year_month == '2025-05') & (counts_df.tier == 'tier4'), 'users'].item() == 2 