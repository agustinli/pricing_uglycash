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

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def load_data(outputs_dir: str) -> Dict[str, pd.DataFrame]:
    """Carga DataFrames necesarios desde ``outputs_dir``."""
    group_metrics = pd.read_csv(os.path.join(outputs_dir, 'group_metrics_monthly.csv'))
    active_users = pd.read_csv(os.path.join(outputs_dir, 'active_users_monthly.csv'))
    return {'group_metrics': group_metrics, 'active_users': active_users}


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
    st.set_page_config(layout='wide', page_title='🏦 UGLYCASH – P&L Simulator')
    st.title('🏦 UGLYCASH – P&L Simulator')

    # 1. Directorio de outputs ------------------------------------------------
    outputs_dir = st.sidebar.text_input('📂 Carpeta de outputs', value='segmentation_outputs')
    if not os.path.isdir(outputs_dir):
        st.error(f'No se encontró el directorio {outputs_dir}. Genera los outputs primero.')
        st.stop()

    data = load_data(outputs_dir)

    # 2. Parámetros -----------------------------------------------------------
    st.sidebar.header('⚙️ Parámetros de fees / costos')
    default_params = RevenueCostCalculator.get_default_params()
    params: Dict[str, float] = {}

    # Crear sliders dinámicamente
    for key, default in default_params.items():
        if key == 'cac_per_user':
            # cac slider aparte al final
            continue
        if 'pct' in key or 'fx' in key:
            params[key] = st.sidebar.slider(key, min_value=0.0, max_value=default * 3, value=default, step=0.0001, format='%.4f')
        else:
            params[key] = st.sidebar.slider(key, min_value=0.0, max_value=default * 3 if default else 10.0, value=default, step=0.01)

    params['cac_per_user'] = st.sidebar.slider('cac_per_user', min_value=0.0, max_value=default_params['cac_per_user'] * 3, value=default_params['cac_per_user'], step=1.0)

    st.sidebar.header('📈 Supuesto de crecimiento')
    growth_rate = st.sidebar.slider('Tasa mensual de crecimiento post Jun-2025 (%)', 0.0, 20.0, 5.0, 0.5) / 100.0
    proj_months = st.sidebar.slider('Meses a proyectar', 0, 36, 30, 1)

    # 3. Cálculo -------------------------------------------------------------
    rc_calc = RevenueCostCalculator(data['group_metrics'], data['active_users'], params=params)
    product_df = rc_calc.calculate_product_level()

    # Proyección futura -------------------------------------------------------
    if proj_months > 0 and growth_rate > 0:
        last_month = product_df['year_month'].max()
        product_df = project_growth(product_df, last_month, growth_rate, proj_months)

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

    # 4. Visualizaciones ------------------------------------------------------
    st.header('Revenue por producto')
    rev_pivot = product_df.pivot_table(index='year_month', columns='product', values='revenue', aggfunc='sum').fillna(0)
    fig_rev = px.bar(rev_pivot, x=rev_pivot.index, y=rev_pivot.columns, title='Revenue (stacked)', labels={'value': 'USD', 'year_month': 'Mes'})
    st.plotly_chart(fig_rev, use_container_width=True)

    st.header('Costos por producto')
    cost_pivot = product_df.pivot_table(index='year_month', columns='product', values='cost', aggfunc='sum').fillna(0)
    fig_cost = px.bar(cost_pivot, x=cost_pivot.index, y=cost_pivot.columns, title='Costos (stacked)', labels={'value': 'USD', 'year_month': 'Mes'})
    st.plotly_chart(fig_cost, use_container_width=True)

    st.header('P&L')
    fig_pl = px.line(pl_df, x='year_month', y='pl', title='Profit & Loss', labels={'pl': 'USD', 'year_month': 'Mes'})
    st.plotly_chart(fig_pl, use_container_width=True)

    # Tabla resumen ----------------------------------------------------------
    st.subheader('Resumen P&L')
    st.dataframe(pl_df, height=400)


if __name__ == '__main__':
    main() 