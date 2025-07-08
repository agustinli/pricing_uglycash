#!/usr/bin/env python3
"""
Calculador de revenue y costos a partir de las métricas por grupo (group_metrics_monthly).

Producto / supuestos de fees y costos:
1. Earn: revenue 0.31 % anual sobre balance, costo 0.33 % anual.
2. Card: revenue 1.71 % sobre volumen + 1 % FX (50 % del volumen). Costos: 0.447 % + 1 % FX + 0.289 USD por transacción.
3. Investment: revenue 1 %, costo 0.22 % sobre volumen invertido.
4. Stables (retiro crypto): revenue 3 USD, costo 0.33 USD por retiro.
5. Fiat on/off (cash + fiat rails): revenue fijo 1 USD por tx + 0.25 % sobre volumen (solo en retiros fiat). Costos según rails + maintenance rails 1 USD por usuario.

CAC: 25 USD por usuario activo mensual (opcional, si se provee active_users_monthly).
"""

from typing import Optional, Dict
import pandas as pd
import numpy as np


# --- Default parameters (monthly rates unless noted) -----------------
DEFAULT_PARAMS: Dict[str, float] = {
    # Earn (monthly rates derived from default APY ~3.1%)
    'earn_rev_pct': 0.00307,  # derived from 3.75% APY
    'earn_cost_pct': 0.00327,  # derived from 4% APY

    # ---- Global Card Params (affect POS & ATM) ----
    'fx_fee_pct': 0.01,                 # fee % applied to FX volume (revenue side)
    'fx_volume_share': 0.50,            # share of volume with FX
    'cross_border_fee_pct': 0.005,      # fee % applied to cross-border volume (revenue side)
    'cross_border_volume_share': 0.20,  # share of volume that is cross-border

    # ISA (interchange settlement add-on)
    'isa_cost_pct': 0.01,   # % sobre volumen sujeto a ISA
    'isa_volume_pct': 0.50, # % del volumen de tarjeta expuesto a ISA

    # ---- Card POS specific ----
    'pos_rev_pct': 0.0171,
    'pos_processing_cost_pct': 0.00447,
    'pos_per_tx_fee': 0.289,

    # Investment
    'invest_rev_pct': 0.01,
    'invest_cost_pct': 0.0022,

    # Stables (variable fee)
    'stables_low_fee': 1.0,      # fee for withdrawals <= threshold
    'stables_high_fee': 2.0,     # fee for withdrawals > threshold
    'stables_threshold': 100.0,   # amount threshold in USD
    'stables_cost_per_tx': 0.85,  # cost remains fixed

    # Fiat on/off
    'fiat_rev_per_tx': 1.0,
    'fiat_rev_withdraw_pct': 0.0025,
    'fiat_cost_cash_dep': 0.73,
    'fiat_cost_cash_wdr': 0.90,
    'fiat_cost_fiat_dep': 0.50,
    'fiat_cost_fiat_wdr': 0.50,
    'fiat_cost_per_volume': 0.0001,
    'rails_maintenance_per_user': 1.0,

    # CAC
    'cac_per_user': 0.0,

    # Free-tx flags
    'free_first_fiat_dep': False,
    'free_first_crypto_wdr': False,

    # ATM specific
    'atm_fixed_rev': 1.0,
    'atm_var_rev_pct': 0.015,
    'atm_fixed_cost': 1.1,
    'atm_var_cost_pct': 0.0075,

    # Crypto deposit (no revenue, only cost)
    'crypto_deposit_cost_per_tx': 0.85,
}


# ---------------------------------------------------------------------------
# Revenue & Cost Calculator
# ---------------------------------------------------------------------------


class RevenueCostCalculator:
    """Calcula revenue, costos y P&L mensual de la compañía.

    Ahora admite un DataFrame opcional ``rewards_monthly`` con las columnas
    ``year_month`` y ``rewards_usd`` que se incorpora como costo adicional
    (negativo en P&L).
    """

    def __init__(self,
                 group_metrics: pd.DataFrame,
                 active_users_monthly: Optional[pd.DataFrame] = None,
                 rewards_monthly: Optional[pd.DataFrame] = None,
                 params: Optional[Dict[str, float]] = None) -> None:
        """Inicializa el calculador.

        Args
        ----
        group_metrics : DataFrame resultante de ``GroupMetricsCalculator``.
        active_users_monthly : DataFrame con columnas ``year_month`` y ``active_users``
            para incorporar CAC. Si ``None`` no se considera CAC.
        rewards_monthly : DataFrame con columnas ``year_month`` y ``rewards_usd``
            para incorporar rewards. Si ``None`` no se considera rewards.
        params : Optional dictionary of custom parameters.
        """
        self.group_metrics = group_metrics.copy()
        self.active_users_monthly = active_users_monthly
        self.rewards_monthly = rewards_monthly

        self.params = DEFAULT_PARAMS.copy()
        if params:
            self.params.update(params)

    # ------------------------------------------------------------------
    # 1) Revenue & Cost por producto-segmento-mes
    # ------------------------------------------------------------------
    def calculate_product_level(self) -> pd.DataFrame:
        """Devuelve un DataFrame con revenue y costo por producto.

        Columns: year_month, segment, product, revenue, cost
        """
        df = self.group_metrics.copy()

        # Volúmenes totales por grupo -----------------------------------
        df['balance_total'] = df['usuarios_grupo'] * df['balance']

        df['card_volume'] = (
            df['tarjeta_tx_cantidad'] * df['tarjeta_valor_tx_promedio']
        )
        df['investment_volume'] = (
            df['investment_buy_tx_cantidad'] * df['investment_buy_valor_tx_promedio'] +
            df['investment_sell_tx_cantidad'] * df['investment_sell_valor_tx_promedio']
        )
        df['cash_deposit_volume'] = (
            df['cash_deposit_tx_cantidad'] * df['cash_deposit_valor_tx_promedio']
        )
        df['cash_withdraw_volume'] = (
            df['cash_withdraw_tx_cantidad'] * df['cash_withdraw_valor_tx_promedio']
        )
        df['fiat_deposit_volume'] = (
            df['fiat_deposit_tx_cantidad'] * df['fiat_deposit_valor_tx_promedio']
        )
        df['fiat_withdraw_volume'] = (
            df['fiat_withdraw_tx_cantidad'] * df['fiat_withdraw_valor_tx_promedio']
        )

        # Split POS and ATM volumes from group_metrics
        df['pos_volume'] = df.get('pos_tx_cantidad', 0) * df.get('pos_valor_tx_promedio', 0)
        df['atm_volume'] = df.get('atm_tx_cantidad', 0) * df.get('atm_valor_tx_promedio', 0)

        # --- Global volume slices --------------------------------------
        isa_volume_pos  = self.params['isa_volume_pct']            * df['pos_volume']
        isa_volume_atm  = self.params['isa_volume_pct']            * df['atm_volume']

        fx_pos_vol      = self.params['fx_volume_share']           * df['pos_volume']
        fx_atm_vol      = self.params['fx_volume_share']           * df['atm_volume']

        cb_pos_vol      = self.params['cross_border_volume_share'] * df['pos_volume']
        cb_atm_vol      = self.params['cross_border_volume_share'] * df['atm_volume']

        # 1. Earn --------------------------------------------------------
        df['earn_revenue'] = self.params['earn_rev_pct'] * df['balance_total']
        df['earn_cost'] = self.params['earn_cost_pct'] * df['balance_total']

        # 2. Card --------------------------------------------------------
        # ---------------- POS ----------------------------------------
        df['card_pos_revenue'] = (
            self.params['pos_rev_pct']          * df['pos_volume'] +
            self.params['fx_fee_pct']           * fx_pos_vol +
            self.params['cross_border_fee_pct'] * cb_pos_vol
        )

        df['card_pos_cost'] = (
            self.params['pos_processing_cost_pct'] * df['pos_volume'] +
            self.params['pos_per_tx_fee']          * df.get('pos_tx_cantidad', 0) +
            self.params['isa_cost_pct']            * isa_volume_pos
        )

        # ---------------- ATM ----------------------------------------
        df['card_atm_revenue'] = (
            self.params['atm_fixed_rev'] * df.get('atm_tx_cantidad', 0) +
            self.params['atm_var_rev_pct'] * df['atm_volume'] +
            self.params['fx_fee_pct']           * fx_atm_vol +
            self.params['cross_border_fee_pct'] * cb_atm_vol
        )

        df['card_atm_cost'] = (
            self.params['atm_fixed_cost'] * df.get('atm_tx_cantidad', 0) +
            self.params['atm_var_cost_pct'] * df['atm_volume'] +
            self.params['isa_cost_pct']     * isa_volume_atm
        )

        # For backward compatibility keep combined card metrics
        df['card_volume'] = df['pos_volume'] + df['atm_volume']
        isa_volume = isa_volume_pos + isa_volume_atm
        fx_volume = fx_pos_vol + fx_atm_vol
        df['card_revenue'] = df['card_pos_revenue'] + df['card_atm_revenue']
        df['card_cost'] = df['card_pos_cost'] + df['card_atm_cost']

        # 3. Investment --------------------------------------------------
        df['investment_revenue'] = self.params['invest_rev_pct'] * df['investment_volume']
        df['investment_cost'] = self.params['invest_cost_pct'] * df['investment_volume']

        # 4. Stables (crypto withdrawal) -----------------------------------
        free_wdr = self.params.get('free_first_crypto_wdr', False)
        if free_wdr:
            if 'users_with_crypto_wdr' in df.columns:
                free_wdr_count = df['users_with_crypto_wdr']
            else:
                # Fallback: estimar usuarios con retiro = min(tx_cantidad, usuarios_grupo)
                free_wdr_count = df[['crypto_withdraw_tx_cantidad', 'usuarios_grupo']].min(axis=1)
        else:
            free_wdr_count = 0

        low_fee = self.params['stables_low_fee']
        high_fee = self.params['stables_high_fee']

        if {'stables_small_tx', 'stables_large_tx'}.issubset(df.columns):
            small = df['stables_small_tx']
            large = df['stables_large_tx']

            # Distribuir la exención de primera transacción sobre small primero
            free_small = np.minimum(free_wdr_count, small)
            free_large = free_wdr_count - free_small
            free_large = np.minimum(free_large, large)

            df['stables_revenue'] = (
                low_fee  * (small - free_small) +
                high_fee * (large - free_large)
            )

            total_tx = small + large
        else:
            # Fallback a aproximación promedio (caso legacy)
            fee_per_tx = np.where(df['crypto_withdraw_valor_tx_promedio'] <= 100, low_fee, high_fee)
            df['stables_revenue'] = fee_per_tx * (df['crypto_withdraw_tx_cantidad'] - free_wdr_count)
            total_tx = df['crypto_withdraw_tx_cantidad']

        # Costos (uno por transacción, gratis la primera si flag activo)
        df['stables_cost'] = (
            self.params['stables_cost_per_tx'] * (total_tx - free_wdr_count)
        )

        # 5. Fiat on/off -------------------------------------------------
        # ---------------- Free first fiat deposit --------------------
        free_dep = self.params.get('free_first_fiat_dep', False)
        if free_dep:
            if 'users_with_fiat_dep' in df.columns:
                free_dep_count = df['users_with_fiat_dep']
            else:
                free_dep_count = df[['fiat_deposit_tx_cantidad', 'usuarios_grupo']].min(axis=1)
        else:
            free_dep_count = 0

        df['fiat_revenue'] = (
            self.params['fiat_rev_per_tx'] * df['cash_deposit_tx_cantidad'] +
            self.params['fiat_rev_per_tx'] * df['cash_withdraw_tx_cantidad'] +
            self.params['fiat_rev_per_tx'] * df['fiat_deposit_tx_cantidad'] +
            self.params['fiat_rev_per_tx'] * df['fiat_withdraw_tx_cantidad'] +
            self.params['fiat_rev_withdraw_pct'] * df['fiat_withdraw_volume']
        ) - free_dep_count * self.params['fiat_rev_per_tx']

        df['fiat_cost'] = (
            self.params['fiat_cost_cash_dep'] * df['cash_deposit_tx_cantidad'] +
            self.params['fiat_cost_cash_wdr'] * df['cash_withdraw_tx_cantidad'] +
            self.params['fiat_cost_fiat_dep'] * df['fiat_deposit_tx_cantidad'] +
            self.params['fiat_cost_fiat_wdr'] * df['fiat_withdraw_tx_cantidad'] +
            self.params['fiat_cost_per_volume'] * df['fiat_deposit_volume'] +
            self.params['fiat_cost_per_volume'] * df['fiat_withdraw_volume'] +
            self.params['rails_maintenance_per_user'] * df['usuarios_grupo']
        ) - free_dep_count * self.params['fiat_cost_fiat_dep']

        # 6. Crypto deposit (cost only) ----------------------------------
        if 'crypto_deposit_tx_cantidad' in df.columns:
            df['crypto_deposit_revenue'] = 0.0
            df['crypto_deposit_cost'] = (
                self.params['crypto_deposit_cost_per_tx'] * df['crypto_deposit_tx_cantidad']
            )
        else:
            df['crypto_deposit_revenue'] = 0.0
            df['crypto_deposit_cost'] = 0.0

        # Transformar a formato largo -----------------------------------
        product_dfs = []
        for prod in ['earn', 'card_pos', 'card_atm', 'investment', 'stables', 'crypto_deposit', 'fiat']:
            if prod == 'card_pos':
                revenue_col = 'card_pos_revenue'
                cost_col = 'card_pos_cost'
            elif prod == 'card_atm':
                revenue_col = 'card_atm_revenue'
                cost_col = 'card_atm_cost'
            elif prod == 'card':
                # deprecated combined
                revenue_col = 'card_revenue'
                cost_col = 'card_cost'
            else:
                revenue_col = f'{prod}_revenue'
                cost_col = f'{prod}_cost'

            if revenue_col in df.columns:
                product_dfs.append(
                    df[['year_month', 'segment', revenue_col, cost_col]]
                      .rename(columns={revenue_col: 'revenue', cost_col: 'cost'})
                      .assign(product=prod)
                )

        product_df = pd.concat(product_dfs, ignore_index=True)
        product_df = product_df[['year_month', 'segment', 'product', 'revenue', 'cost']]
        product_df[['revenue', 'cost']] = product_df[['revenue', 'cost']].round(2)

        # Incorporar rewards como producto separado ---------------------
        if self.rewards_monthly is not None:
            rew = self.rewards_monthly.copy()
            rew['year_month'] = rew['year_month'].astype(str)
            rew_prod = (rew.groupby('year_month')['rewards_usd']
                           .sum()
                           .reset_index()
                           .assign(segment='all', product='rewards')
                           .rename(columns={'rewards_usd': 'cost'}))
            rew_prod['revenue'] = 0.0
            product_df = pd.concat([product_df, rew_prod[['year_month','segment','product','revenue','cost']]], ignore_index=True)

        return product_df

    # ------------------------------------------------------------------
    # 2) P&L consolidado mensual
    # ------------------------------------------------------------------
    def calculate_monthly_pl(self) -> pd.DataFrame:
        """Devuelve P&L consolidado mensual con CAC opcional."""
        product_df = self.calculate_product_level()

        pl = (product_df.groupby('year_month')[['revenue', 'cost']]
                      .sum()
                      .reset_index())

        # Incorporar CAC si se provee active_users_monthly ---------------
        if self.active_users_monthly is not None:
            # Alinear tipos de columna year_month (puede venir como Period)
            au = self.active_users_monthly.copy()
            au['year_month'] = au['year_month'].astype(str)
            pl = pl.merge(au, on='year_month', how='left')
            # CAC solo para nuevos usuarios activos (mes a mes)
            pl = pl.sort_values('year_month').reset_index(drop=True)
            pl['new_active_users'] = pl['active_users'].diff().fillna(pl['active_users'])
            pl['new_active_users'] = pl['new_active_users'].clip(lower=0)
            pl['cac_cost'] = pl['new_active_users'] * self.params['cac_per_user']
        else:
            pl['cac_cost'] = 0
            pl['active_users'] = 0

        # Incorporar rewards si se provee --------------------------------
        if self.rewards_monthly is not None:
            rew = self.rewards_monthly.copy()
            rew['year_month'] = rew['year_month'].astype(str)
            pl = pl.merge(rew[['year_month', 'rewards_usd']], on='year_month', how='left')
            pl['rewards_usd'] = pl['rewards_usd'].fillna(0)
        else:
            pl['rewards_usd'] = 0

        pl['total_cost'] = pl['cost'] + pl['cac_cost'] + pl['rewards_usd']
        pl['pl'] = pl['revenue'] - pl['total_cost']
        pl['arr'] = pl['pl'] * 12  # Annual run-rate (simple extrapolation)
        pl['arc'] = pl.apply(lambda r: r['pl'] / r['active_users'] if r['active_users'] else 0, axis=1)

        # Rentabilidad (% pl / arr) -------------------------------------
        pl['pl_arr'] = pl.apply(lambda r: r['pl'] / r['arr'] if r['arr'] else 0, axis=1)

        cols = ['year_month', 'revenue', 'cost', 'cac_cost', 'rewards_usd', 'total_cost', 'pl', 'arr', 'arc', 'pl_arr']
        return pl[cols].round(2)

    # ------------------------------------------------------------------
    # 3) Helpers de exportación
    # ------------------------------------------------------------------
    @staticmethod
    def export_product_metrics(product_df: pd.DataFrame, path: str) -> None:
        """Exporta métricas por producto a CSV."""
        product_df.to_csv(path, index=False)

    @staticmethod
    def export_pl_monthly(pl_df: pd.DataFrame, path: str) -> None:
        """Exporta P&L mensual a CSV."""
        pl_df.to_csv(path, index=False)

    # ------------------------------------------------------------------
    # 4) Static helpers
    # ------------------------------------------------------------------
    @staticmethod
    def get_default_params() -> Dict[str, float]:
        """Return a copy of DEFAULT_PARAMS."""
        return DEFAULT_PARAMS.copy() 