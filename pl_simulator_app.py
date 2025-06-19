#!/usr/bin/env python3
"""
📊 UGLYCASH – P&L Simulator App
--------------------------------
Aplicación Streamlit que permite modificar supuestos de fees/costos y tasa
mensual de crecimiento a partir de Jun-2025 para proyectar revenue, costos y
P&L.  Requiere que previamente se hayan generado los outputs con
``user_segmentation_analyzer.py`` (especialmente ``group_metrics_monthly.csv`` y
``active_users_monthly.csv``).
"""

import os
from typing import Dict

import pandas as pd
import streamlit as st
import plotly.express as px
from pandas.tseries.offsets import MonthEnd

from revenue_cost_calculator import RevenueCostCalculator
from tier_engine import assign_tiers, DEFAULT_THRESHOLDS, DEFAULT_REWARD_PARAMS

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def load_data(outputs_dir: str) -> Dict[str, pd.DataFrame]:
    """Carga DataFrames necesarios desde ``outputs_dir``."""
    group_metrics = pd.read_csv(os.path.join(outputs_dir, 'group_metrics_monthly.csv'))
    active_users = pd.read_csv(os.path.join(outputs_dir, 'active_users_monthly.csv'))
    user_segments = pd.read_csv(os.path.join(outputs_dir, 'user_segments_monthly.csv'))
    return {
        'group_metrics': group_metrics,
        'active_users': active_users,
        'user_segments': user_segments,
    }


def project_growth(df: pd.DataFrame, last_month: str, growth_rate: float, months: int) -> pd.DataFrame:
    """Genera proyección simple de crecimiento compuesto a partir de *last_month*.

    Parameters
    ----------
    df : DataFrame con filas correspondientes a *last_month*.
    last_month : str «YYYY-MM»
    growth_rate : crecimiento porcentual mensual (p.ej. 0.05 = 5 %).
    months : cantidad de meses futuros a proyectar.
    """
    proj_rows = []
    prev_rows = df[df['year_month'] == last_month].copy()

    for n in range(1, months + 1):
        factor = (1 + growth_rate) ** n
        new_rows = prev_rows.copy()
        new_period = (pd.Period(last_month) + n).strftime('%Y-%m')
        new_rows['year_month'] = new_period
        # Escalar métricas monetarias y users
        for col in new_rows.columns:
            if col not in ['year_month', 'segment', 'product']:
                new_rows[col] = new_rows[col] * factor
        proj_rows.append(new_rows)

    if proj_rows:
        proj_df = pd.concat(proj_rows, ignore_index=True)
        return pd.concat([df, proj_df], ignore_index=True)
    return df


# ---------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------

def main():
    st.set_page_config(layout='wide', page_title='UGLYCASH – P&L Simulator')
    st.title('UGLYCASH – P&L Simulator')

    # 1. Directorio de outputs ------------------------------------------------
    outputs_dir = st.sidebar.text_input('Output folder', value='segmentation_outputs')
    if not os.path.isdir(outputs_dir):
        st.error(f'Directory {outputs_dir} not found. Run the analysis first.')
        st.stop()

    data = load_data(outputs_dir)

    # 2. Parámetros -----------------------------------------------------------
    st.sidebar.header('⚙️ Model parameters')
    default_params = RevenueCostCalculator.get_default_params()
    params: Dict[str, float] = {}

    # --- Product parameter groups ------------------------------------
    product_groups = {
        'Earn': {
            'color': '#FF8C00',
            'fields': {
                'earn_rev_pct': ('Revenue APY (%)', 'apy'),
                'earn_cost_pct': ('Cost APY (%)', 'apy'),
            }
        },
        'Card': {
            'color': '#1f77b4',
            'fields': {
                'card_rev_pct': ('Revenue % of volume', 'pct'),
                'card_fx_pct': ('FX share % of volume', 'pct'),
                'card_cost_pct': ('Processing cost % of volume', 'pct'),
                'card_per_tx_fee': ('Fixed fee per tx (USD)', 'usd'),
            }
        },
        'Investment': {
            'color': '#FFD700',
            'fields': {
                'invest_rev_pct': ('Revenue % of volume', 'pct'),
                'invest_cost_pct': ('Cost % of volume', 'pct'),
            }
        },
        'Stables': {
            'color': '#d62728',
            'fields': {
                'stables_rev_per_tx': ('Revenue per withdrawal (USD)', 'usd'),
                'stables_cost_per_tx': ('Cost per withdrawal (USD)', 'usd'),
            }
        },
        'Fiat': {
            'color': '#2ca02c',
            'fields': {
                'fiat_rev_per_tx': ('Revenue per tx (USD)', 'usd'),
                'fiat_rev_withdraw_pct': ('Revenue % of fiat withdrawal volume', 'pct'),
                'fiat_cost_cash_dep': ('Cash deposit cost (USD)', 'usd'),
                'fiat_cost_cash_wdr': ('Cash withdraw cost (USD)', 'usd'),
                'fiat_cost_fiat_dep': ('Fiat deposit cost (USD)', 'usd'),
                'fiat_cost_fiat_wdr': ('Fiat withdraw cost (USD)', 'usd'),
                'fiat_cost_per_volume': ('Cost per volume (USD)', 'usd'),
                'rails_maintenance_per_user': ('Rails maintenance per user (USD)', 'usd'),
            },
        },
        'RSR': {
            'color': '#9467bd',
            'fields': {}
        },
        'Rewards': {
            'color': '#8c564b',
            'fields': {}
        }
    }

    for product, cfg in product_groups.items():
        with st.sidebar.expander(f"{product} parameters", expanded=False):
            for key, (label, kind) in cfg['fields'].items():
                default = default_params[key]
                if kind == 'apy':
                    default_apy = (1 + default) ** 12 - 1
                    apy_val = st.number_input(label, value=round(default_apy * 100, 4), step=0.01, format="%0.2f")
                    params[key] = (1 + apy_val / 100) ** (1/12) - 1
                elif kind == 'pct':
                    val_pct = st.number_input(label, value=round(default * 100, 4), step=0.01, format="%0.2f")
                    params[key] = val_pct / 100
                else:
                    params[key] = st.number_input(label, value=default, step=0.01)

    # CAC separately ---------------------------------------------------
    with st.sidebar.expander('Customer Acquisition Cost (CAC)'):
        params['cac_per_user'] = st.number_input('CAC per new active user (USD)', value=default_params['cac_per_user'], step=1.0)

    # Tier parameters --------------------------------------------------
    st.sidebar.header('Tier system')

    # Thresholds
    thresholds = DEFAULT_THRESHOLDS.copy()
    with st.sidebar.expander('Tier thresholds', expanded=False):
        thresholds['tier2_spend'] = st.number_input('Tier2 min spend (eUSD)', value=thresholds['tier2_spend'], step=10)
        thresholds['tier3_spend'] = st.number_input('Tier3 min spend', value=thresholds['tier3_spend'], step=10)
        thresholds['tier4_spend'] = st.number_input('Tier4 min spend', value=thresholds['tier4_spend'], step=10)
        thresholds['tier2_balance'] = st.number_input('Tier2 min balance', value=thresholds['tier2_balance'], step=10)
        thresholds['tier3_balance'] = st.number_input('Tier3 min balance', value=thresholds['tier3_balance'], step=10)
        thresholds['tier4_balance'] = st.number_input('Tier4 min balance', value=thresholds['tier4_balance'], step=10)

    # Rewards params
    reward_params = DEFAULT_REWARD_PARAMS.copy()
    with st.sidebar.expander('Tier rewards (%)', expanded=False):
        for tier in ['tier2', 'tier3', 'tier4']:
            reward_params[f'{tier}_cashback_pct'] = st.number_input(f'{tier} cashback % of spend', value=reward_params[f'{tier}_cashback_pct'] * 100, step=0.1, format='%0.2f') / 100.0
            reward_params[f'{tier}_yield_pct'] = st.number_input(f'{tier} extra yield % (<=1k balance)', value=reward_params[f'{tier}_yield_pct'] * 100, step=0.1, format='%0.2f') / 100.0

    # Growth assumptions ----------------------------------------------
    st.sidebar.header('Growth projection')
    growth_rate = st.sidebar.slider('Monthly growth rate after Jun-2025 (%)', 0.0, 20.0, 16.0, 0.5) / 100.0
    proj_months = st.sidebar.slider('Months to project', 0, 36, 30, 1)

    # Extra param: RSR price -----------------------------------------
    st.sidebar.header('RSR token')
    rsr_price = st.sidebar.number_input('RSR price (USD)', value=0.006345, step=0.0001, format='%f')

    # 3. Cálculo -------------------------------------------------------------
    # Recalcular tiers y rewards según parámetros seleccionados
    tiers_df, tier_counts_df, rewards_df_input = assign_tiers(
        data['user_segments'], thresholds=thresholds, reward_params=reward_params
    )

    rc_calc = RevenueCostCalculator(
        data['group_metrics'],
        active_users_monthly=data['active_users'],
        rewards_monthly=rewards_df_input,
        params=params
    )

    # ----- 3.a REAL DATA up to May-2025 ---------------------------------
    cutoff_month = '2025-05'
    product_df_real = rc_calc.calculate_product_level()
    product_df_real = product_df_real[product_df_real['year_month'] <= cutoff_month]

    # ----- 3.b PROJECTION afterwards ----------------------------------
    product_df = product_df_real.copy()

    # 3.a Add RSR emissions -------------------------------------------
    rsr_path = os.path.join(outputs_dir, 'rsr_emissions.csv')
    if os.path.exists(rsr_path):
        rsr_df = pd.read_csv(rsr_path)  # expect columns year_month, rsr_amount (last column)
        if rsr_df.shape[1] >= 2:
            rsr_df.columns = ['year_month', 'rsr_units']
            rsr_df['revenue'] = rsr_df['rsr_units'] * rsr_price
            rsr_df['cost'] = 0.0
            rsr_df['product'] = 'rsr'
            rsr_df['segment'] = 'all'
            product_df = pd.concat([product_df, rsr_df[['year_month','segment','product','revenue','cost']]], ignore_index=True)

    # Proyección futura -------------------------------------------------------
    if proj_months > 0 and growth_rate > 0:
        last_month = cutoff_month
        product_df = project_growth(product_df, last_month, growth_rate, proj_months)

    # Mantener datos desde 2025-01 en adelante
    product_df = product_df[product_df['year_month'] >= '2025-01']

    # Recalcular activo usuarios proyectado ----------------------------------
    active_df = data['active_users'].copy()
    if proj_months > 0 and growth_rate > 0:
        last_active = active_df.iloc[-1].copy()
        last_period = pd.Period(last_active['year_month'])
        proj_rows = []
        for n in range(1, proj_months + 1):
            factor = (1 + growth_rate) ** n
            new_row = last_active.copy()
            new_row['year_month'] = (last_period + n).strftime('%Y-%m')
            new_row['active_users'] = round(last_active['active_users'] * factor)
            proj_rows.append(new_row)
        active_df = pd.concat([active_df, pd.DataFrame(proj_rows)], ignore_index=True)

    active_df = active_df[active_df['year_month'] >= '2025-01']

    # Allow filtering products ---------------------------------------
    all_products = sorted(product_df['product'].unique())
    selected_products = st.sidebar.multiselect('Products to include', all_products, default=all_products)
    product_df = product_df[product_df['product'].isin(selected_products)]

    # Recalcular P&L agregando revenue & cost
    pl_df = (product_df.groupby('year_month')[['revenue', 'cost']]
                       .sum()
                       .reset_index())

    # Fuse active users & CAC
    pl_df = pl_df.merge(active_df, on='year_month', how='left')
    pl_df = pl_df.sort_values('year_month').reset_index(drop=True)
    pl_df['new_active_users'] = pl_df['active_users'].diff().fillna(pl_df['active_users']).clip(lower=0)
    pl_df['cac_cost'] = pl_df['new_active_users'] * params['cac_per_user']
    pl_df['total_cost'] = pl_df['cost'] + pl_df['cac_cost']
    pl_df['pl'] = pl_df['revenue'] - pl_df['total_cost']
    pl_df['arr'] = pl_df['pl'] * 12
    pl_df['arc'] = pl_df.apply(lambda r: r['pl'] / r['active_users'] if r['active_users'] else 0, axis=1)
    pl_df['pl_arr'] = pl_df.apply(lambda r: r['pl'] / r['arr'] if r['arr'] else 0, axis=1)

    # Remove unused cols and rename ----------------------------------
    pl_df.rename(columns={'pl':'Monthly P&L','arr':'Annualized P&L'}, inplace=True)
    pl_df = pl_df[['year_month','revenue','cost','cac_cost','total_cost','Monthly P&L','Annualized P&L']]

    # Color mapping for products --------------------------------------
    color_map = {p.lower(): cfg['color'] for p, cfg in product_groups.items()}

    # 4. Visualizaciones ------------------------------------------------------
    st.header('Revenue by product')
    rev_pivot = product_df.pivot_table(index='year_month', columns='product', values='revenue', aggfunc='sum').fillna(0)
    fig_rev = px.bar(rev_pivot, x=rev_pivot.index, y=rev_pivot.columns, title='Revenue (stacked)', labels={'value': 'USD', 'year_month': 'Month'}, color_discrete_map=color_map)
    st.plotly_chart(fig_rev, use_container_width=True)

    st.header('Costs by product')
    cost_pivot = product_df.pivot_table(index='year_month', columns='product', values='cost', aggfunc='sum').fillna(0)
    fig_cost = px.bar(cost_pivot, x=cost_pivot.index, y=cost_pivot.columns, title='Costs (stacked)', labels={'value': 'USD', 'year_month': 'Month'}, color_discrete_map=color_map)
    st.plotly_chart(fig_cost, use_container_width=True)

    st.header('Profit & Loss')
    long_pl = pl_df.melt(id_vars='year_month', value_vars=['revenue','total_cost','Monthly P&L'], var_name='metric', value_name='USD')
    fig_pl = px.bar(long_pl, x='year_month', y='USD', color='metric', barmode='group', title='Profit & Loss', labels={'year_month':'Month'})
    st.plotly_chart(fig_pl, use_container_width=True)

    # Tabla resumen ----------------------------------------------------------
    st.subheader('P&L summary')
    st.dataframe(pl_df, height=400)

    # -----------------------------------------------------------------
    # 3.a  Project tier counts beyond historical months ----------------
    # -----------------------------------------------------------------
    if proj_months > 0 and growth_rate > 0:
        last_real_month = tier_counts_df['year_month'].max()
        base_counts = tier_counts_df[tier_counts_df['year_month'] == last_real_month].copy()
        base_counts = base_counts[base_counts['tier'] != 'tier1']

        proj_rows = []
        for n in range(1, proj_months + 1):
            factor = (1 + growth_rate) ** n
            target_period = (pd.Period(last_real_month) + n).strftime('%Y-%m')
            scaled = base_counts.copy()
            scaled['year_month'] = target_period
            scaled['users'] = (scaled['users'] * factor).round().astype(int)
            proj_rows.append(scaled)

        if proj_rows:
            tier_counts_df = pd.concat([tier_counts_df, *proj_rows], ignore_index=True)

    # --------------------------------------------------------------
    # Tier chart (now including projected counts) ------------------
    tier_chart_expander = st.expander('Users by tier evolution', expanded=False)
    with tier_chart_expander:
        last_month_proj = product_df['year_month'].max()
        counts_filtered = tier_counts_df[
            (tier_counts_df['year_month'] >= '2025-01') &
            (tier_counts_df['tier'] != 'tier1') &
            (tier_counts_df['year_month'] <= last_month_proj)
        ]

        counts_pivot = counts_filtered.pivot(index='year_month', columns='tier', values='users').fillna(0)
        all_periods = pd.period_range('2025-01', last_month_proj, freq='M').strftime('%Y-%m')
        counts_pivot = counts_pivot.reindex(all_periods, fill_value=0)

        fig_tier = px.area(counts_pivot, x=counts_pivot.index, y=counts_pivot.columns,
                           title='Users by Tier', labels={'value': 'Users', 'year_month': 'Month'})
        st.plotly_chart(fig_tier, use_container_width=True)

    # --- 4.a Product contribution pies (latest month) --------------------
    latest_month = product_df['year_month'].max()
    rev_latest = (product_df[product_df['year_month'] == latest_month]
                    .groupby('product')['revenue'].sum())
    cost_latest = (product_df[product_df['year_month'] == latest_month]
                     .groupby('product')['cost'].sum())

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f'Revenue share – {latest_month}')
        fig_pie_rev = px.pie(values=rev_latest.values, names=rev_latest.index,
                             title='Share of Revenue', color=rev_latest.index,
                             color_discrete_map=color_map)
        fig_pie_rev.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie_rev, use_container_width=True)

    with col2:
        st.subheader(f'Cost share – {latest_month}')
        fig_pie_cost = px.pie(values=cost_latest.values, names=cost_latest.index,
                              title='Share of Cost', color=cost_latest.index,
                              color_discrete_map=color_map)
        fig_pie_cost.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie_cost, use_container_width=True)

    # --- 4.b Stacked bars & others ----------------------------------------


if __name__ == '__main__':
    main() 