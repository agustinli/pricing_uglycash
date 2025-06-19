#!/usr/bin/env python3
"""Streamlit dashboard para analizar revenue, costos y P&L.

Permite ajustar porcentajes/fees y la tasa de crecimiento mensual a partir de una fecha.
"""

import os
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime

from revenue_cost_calculator import RevenueCostCalculator

# ---------------------------------------------------------------------
# Carga datos ----------------------------------------------------------
# ---------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = './segmentation_outputs'

# Caching disabled for simplicity when code changes frequently
@st.cache_data
def load_data(output_dir: str):
    """Carga datos principales y opcionalmente rewards."""
    group_metrics_path = os.path.join(output_dir, 'group_metrics_monthly.csv')
    active_users_path = os.path.join(output_dir, 'active_users_monthly.csv')

    if not os.path.exists(group_metrics_path):
        st.error(f"No se encontró {group_metrics_path}. Ejecuta primero el análisis.")
        st.stop()

    group_metrics = pd.read_csv(group_metrics_path)
    active_users = pd.read_csv(active_users_path) if os.path.exists(active_users_path) else None

    rewards_path = os.path.join(output_dir, 'rewards_skeleton.csv')
    rewards_df = pd.read_csv(rewards_path) if os.path.exists(rewards_path) else None

    return group_metrics, active_users, rewards_df

# ---------------------------------------------------------------------
# Sidebar – parámetros -------------------------------------------------
# ---------------------------------------------------------------------

group_metrics, active_users, rewards_df = load_data(DEFAULT_OUTPUT_DIR)

st.sidebar.header('Parámetros de Revenue / Costos')
params = RevenueCostCalculator.get_default_params()

# Earn
st.sidebar.subheader('Earn')
params['earn_rev_pct'] = st.sidebar.number_input('Revenue % (earn)', value=params['earn_rev_pct'], step=0.0001, format="%0.4f")
params['earn_cost_pct'] = st.sidebar.number_input('Costo % (earn)', value=params['earn_cost_pct'], step=0.0001, format="%0.4f")

# Card
st.sidebar.subheader('Card')
params['card_rev_pct'] = st.sidebar.number_input('Revenue % tarjeta', value=params['card_rev_pct'], step=0.0001)
params['card_fx_pct'] = st.sidebar.number_input('% FX tarjeta', value=params['card_fx_pct'], step=0.0001)
params['card_cost_pct'] = st.sidebar.number_input('Costo % tarjeta', value=params['card_cost_pct'], step=0.0001)
params['card_per_tx_fee'] = st.sidebar.number_input('Fee fijo por tx', value=params['card_per_tx_fee'], step=0.01)

# Investment
st.sidebar.subheader('Investment')
params['invest_rev_pct'] = st.sidebar.number_input('Revenue % investment', value=params['invest_rev_pct'], step=0.0001)
params['invest_cost_pct'] = st.sidebar.number_input('Cost % investment', value=params['invest_cost_pct'], step=0.0001)

# Stables
st.sidebar.subheader('Stables')
params['stables_rev_per_tx'] = st.sidebar.number_input('Revenue por retiro', value=params['stables_rev_per_tx'], step=0.1)
params['stables_cost_per_tx'] = st.sidebar.number_input('Costo por retiro', value=params['stables_cost_per_tx'], step=0.1)

# Fiat
st.sidebar.subheader('Fiat on/off')
params['fiat_rev_per_tx'] = st.sidebar.number_input('Revenue fijo por tx', value=params['fiat_rev_per_tx'], step=0.1)
params['fiat_rev_withdraw_pct'] = st.sidebar.number_input('% sobre retiro fiat', value=params['fiat_rev_withdraw_pct'], step=0.0001)
params['fiat_cost_cash_dep'] = st.sidebar.number_input('Costo cash dep', value=params['fiat_cost_cash_dep'], step=0.01)
params['fiat_cost_cash_wdr'] = st.sidebar.number_input('Costo cash wdr', value=params['fiat_cost_cash_wdr'], step=0.01)
params['fiat_cost_fiat_dep'] = st.sidebar.number_input('Costo fiat dep', value=params['fiat_cost_fiat_dep'], step=0.01)
params['fiat_cost_fiat_wdr'] = st.sidebar.number_input('Costo fiat wdr', value=params['fiat_cost_fiat_wdr'], step=0.01)
params['fiat_cost_per_volume'] = st.sidebar.number_input('Costo por volumen', value=params['fiat_cost_per_volume'], step=0.0001)
params['rails_maintenance_per_user'] = st.sidebar.number_input('Mantenimiento rails por usuario', value=params['rails_maintenance_per_user'], step=0.1)

# CAC
st.sidebar.subheader('CAC')
params['cac_per_user'] = st.sidebar.number_input('CAC por nuevo usuario', value=params['cac_per_user'], step=1.0)

# Crecimiento ----------------------------------------------------------

st.sidebar.header('Proyección de Crecimiento')
growth_start = st.sidebar.date_input('Inicio proyección', datetime(2025, 6, 1))
growth_rate = st.sidebar.number_input('Crecimiento mensual %', value=5.0, step=0.5)
projection_months = st.sidebar.slider('Meses a proyectar', min_value=0, max_value=36, value=24)

# ---------------------------------------------------------------------
# Cálculo --------------------------------------------------------------
# ---------------------------------------------------------------------

def project_growth(pl_df: pd.DataFrame, start_date: datetime, growth_pct: float, months: int):
    """Proyecta revenue+cost growth_pct mensualmente por *months* a partir de start_date."""
    if months == 0:
        return pl_df

    last_history = pl_df[pl_df['year_month'] >= start_date.strftime('%Y-%m')]
    if last_history.empty:
        base_row = pl_df.iloc[-1].copy()
    else:
        base_row = last_history.iloc[-1].copy()

    new_rows = []
    current = base_row.copy()
    for i in range(1, months + 1):
        current = current.copy()
        new_date = (pd.Period(current['year_month']) + 1).strftime('%Y-%m')
        current['year_month'] = new_date
        current[['revenue', 'cost', 'total_cost', 'pl', 'arr']] *= (1 + growth_pct / 100)
        # active users growth as proxy
        current['active_users'] = current['active_users'] * (1 + growth_pct / 100)
        new_rows.append(current)
    return pd.concat([pl_df, pd.DataFrame(new_rows)], ignore_index=True)

# ------------ Actualizar llamada RevenueCostCalculator ---------------
calc = RevenueCostCalculator(
    group_metrics,
    active_users_monthly=active_users,
    rewards_monthly=rewards_df,
    params=params
)
product_df = calc.calculate_product_level()
pl_df = calc.calculate_monthly_pl()

# Proyección crecimiento
pl_df_proj = project_growth(pl_df, growth_start, growth_rate, projection_months)

# ---------------------------------------------------------------------
# Visualizaciones ------------------------------------------------------
# ---------------------------------------------------------------------

st.title('UGLYCASH – Revenue, Costs & P&L Dashboard')

# Revenue stacked bar --------------------------------------------------
rev_monthly = (product_df.groupby(['year_month', 'product'])['revenue']
                            .sum()
                            .reset_index())
fig_rev = px.bar(rev_monthly, x='year_month', y='revenue', color='product',
                 title='Revenue por Producto')
st.plotly_chart(fig_rev, use_container_width=True)

# Cost stacked bar -----------------------------------------------------
cost_monthly = (product_df.groupby(['year_month', 'product'])['cost']
                             .sum()
                             .reset_index())
fig_cost = px.bar(cost_monthly, x='year_month', y='cost', color='product',
                  title='Costos por Producto')
st.plotly_chart(fig_cost, use_container_width=True)

# P&L line -------------------------------------------------------------
fig_pl = px.line(pl_df_proj, x='year_month', y=['revenue', 'total_cost', 'pl'],
                 title='P&L Mensual (con proyección)')
fig_pl.update_layout(yaxis_title='USD')
st.plotly_chart(fig_pl, use_container_width=True)

# Tabla resumen --------------------------------------------------------
st.subheader('P&L Detallado')
st.dataframe(pl_df_proj.set_index('year_month').round(2))

st.caption('Ajusta los parámetros en la barra lateral para ver impacto inmediato.') 