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

from typing import Optional
import pandas as pd


class RevenueCostCalculator:
    """Calcula revenue, costos y P&L mensual de la compañía."""

    def __init__(self,
                 group_metrics: pd.DataFrame,
                 active_users_monthly: Optional[pd.DataFrame] = None) -> None:
        """Inicializa el calculador.

        Args
        ----
        group_metrics : DataFrame resultante de ``GroupMetricsCalculator``.
        active_users_monthly : DataFrame con columnas ``year_month`` y ``active_users``
            para incorporar CAC. Si ``None`` no se considera CAC.
        """
        self.group_metrics = group_metrics.copy()
        self.active_users_monthly = active_users_monthly

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

        # 1. Earn --------------------------------------------------------
        df['earn_revenue'] = 0.0031 * df['balance_total']
        df['earn_cost'] = 0.0033 * df['balance_total']

        # 2. Card --------------------------------------------------------
        fx_volume = 0.5 * df['card_volume']  # asumimos 50 % lleva FX
        df['card_revenue'] = 0.0171 * df['card_volume'] + 0.01 * fx_volume
        df['card_cost'] = (
            0.00447 * df['card_volume'] +
            0.01 * fx_volume +
            0.289 * df['tarjeta_tx_cantidad']
        )

        # 3. Investment --------------------------------------------------
        df['investment_revenue'] = 0.01 * df['investment_volume']
        df['investment_cost'] = 0.0022 * df['investment_volume']

        # 4. Stables (retiros crypto) -----------------------------------
        df['stables_revenue'] = 3 * df['crypto_withdraw_tx_cantidad']
        df['stables_cost'] = 0.33 * df['crypto_withdraw_tx_cantidad']

        # 5. Fiat on/off -------------------------------------------------
        df['fiat_revenue'] = (
            1 * df['cash_deposit_tx_cantidad'] +
            1 * df['cash_withdraw_tx_cantidad'] +
            1 * df['fiat_deposit_tx_cantidad'] +
            1 * df['fiat_withdraw_tx_cantidad'] +
            0.0025 * df['fiat_withdraw_volume']
        )
        df['fiat_cost'] = (
            0.73 * df['cash_deposit_tx_cantidad'] +
            0.90 * df['cash_withdraw_tx_cantidad'] +
            0.50 * df['fiat_deposit_tx_cantidad'] +
            0.50 * df['fiat_withdraw_tx_cantidad'] +
            0.0001 * df['fiat_deposit_volume'] +
            0.0001 * df['fiat_withdraw_volume'] +
            1 * df['usuarios_grupo']  # mantenimiento rails
        )

        # Transformar a formato largo -----------------------------------
        product_dfs = []
        for prod in ['earn', 'card', 'investment', 'stables', 'fiat']:
            product_dfs.append(
                df[['year_month', 'segment', f'{prod}_revenue', f'{prod}_cost']]
                  .rename(columns={f'{prod}_revenue': 'revenue', f'{prod}_cost': 'cost'})
                  .assign(product=prod)
            )

        product_df = pd.concat(product_dfs, ignore_index=True)
        product_df = product_df[['year_month', 'segment', 'product', 'revenue', 'cost']]
        product_df[['revenue', 'cost']] = product_df[['revenue', 'cost']].round(2)
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
            pl['cac_cost'] = pl['new_active_users'] * 25
        else:
            pl['cac_cost'] = 0
            pl['active_users'] = 0

        pl['total_cost'] = pl['cost'] + pl['cac_cost']
        pl['pl'] = pl['revenue'] - pl['total_cost']
        pl['arr'] = pl['pl'] * 12  # Annual run-rate (simple extrapolation)
        pl['arc'] = pl.apply(lambda r: r['pl'] / r['active_users'] if r['active_users'] else 0, axis=1)

        # Rentabilidad (% pl / arr) -------------------------------------
        pl['pl_arr'] = pl.apply(lambda r: r['pl'] / r['arr'] if r['arr'] else 0, axis=1)

        cols = ['year_month', 'revenue', 'cost', 'cac_cost', 'total_cost', 'pl', 'arr', 'arc', 'pl_arr']
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