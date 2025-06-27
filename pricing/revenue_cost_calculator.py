#!/usr/bin/env python3
"""
Calculador de revenue y costos a partir de group_metrics_monthly.

Formulación de productos:
1. Earn: 0.31 %  vs  0.33 % sobre balance total.
2. Card: 1.71 % sobre volumen + 1 % FX (50 % del vol.).
            Costos: 0.447 % + 1 % FX + 0.289 USD por tx.
3. Investment: 1 % revenue / 0.22 % costo sobre volumen.
4. Stables: 3 USD revenue / 0.33 USD costo por retiro.
5. Fiat on/off: ver comentarios en código.

CAC: 25 USD por usuario activo mensual.
"""

from typing import Optional
import pandas as pd


class RevenueCostCalculator:
    def __init__(self,
                 group_metrics: pd.DataFrame,
                 active_users: Optional[pd.DataFrame] = None) -> None:
        """
        Args
        ----
        group_metrics : DataFrame con métricas por grupo y mes (output de
                        GroupMetricsCalculator).
        active_users  : DataFrame con columnas year_month, active_users.
                        Necesario para incorporar CAC.
        """
        self.group_metrics = group_metrics.copy()
        self.active_users = active_users

    # ------------------------------------------------------------------ #
    # 1) Revenue & Cost por producto-segmento-mes
    # ------------------------------------------------------------------ #
    def calculate_product_level(self) -> pd.DataFrame:
        df = self.group_metrics.copy()

        # Totales por grupo
        df['balance_total'] = df['usuarios_grupo'] * df['balance']
        df['card_volume'] = df['tarjeta_tx_cantidad'] * df['tarjeta_valor_tx_promedio']
        df['investment_volume'] = (
            df['investment_buy_tx_cantidad'] * df['investment_buy_valor_tx_promedio'] +
            df['investment_sell_tx_cantidad'] * df['investment_sell_valor_tx_promedio']
        )
        df['cash_load_volume'] = df['cash_deposit_tx_cantidad'] * df['cash_deposit_valor_tx_promedio']
        df['cash_withdraw_volume'] = df['cash_withdraw_tx_cantidad'] * df['cash_withdraw_valor_tx_promedio']
        df['fiat_deposit_volume'] = df['fiat_deposit_tx_cantidad'] * df['fiat_deposit_valor_tx_promedio']
        df['fiat_withdraw_volume'] = df['fiat_withdraw_tx_cantidad'] * df['fiat_withdraw_valor_tx_promedio']

        # 1. Earn
        df['earn_revenue'] = 0.0031 * df['balance_total']
        df['earn_cost'] = 0.0033 * df['balance_total']

        # 2. Card
        fx_volume = 0.5 * df['card_volume']
        df['card_revenue'] = 0.0171 * df['card_volume'] + 0.01 * fx_volume
        df['card_cost'] = 0.00447 * df['card_volume'] + 0.01 * fx_volume + 0.289 * df['tarjeta_tx_cantidad']

        # 3. Investments
        df['investment_revenue'] = 0.01 * df['investment_volume']
        df['investment_cost'] = 0.0022 * df['investment_volume']

        # 4. Stables  (retiros crypto)
        df['stables_revenue'] = 3 * df['crypto_withdraw_tx_cantidad']
        df['stables_cost'] = 0.33 * df['crypto_withdraw_tx_cantidad']

        # 5. Fiat on/off
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
            1 * df['usuarios_grupo']        # mantenimiento rails
        )

        # Convertir a formato largo
        product_frames = []
        for prod in ['earn', 'card', 'investment', 'stables', 'fiat']:
            product_frames.append(
                df[['year_month', 'segment',
                    f'{prod}_revenue', f'{prod}_cost']]
                  .rename(columns={f'{prod}_revenue': 'revenue',
                                   f'{prod}_cost': 'cost'})
                  .assign(product=prod)
            )
        product_df = pd.concat(product_frames)
        product_df = product_df[['year_month', 'segment',
                                 'product', 'revenue', 'cost']]
        product_df[['revenue', 'cost']] = product_df[['revenue', 'cost']].round(2)
        return product_df.reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # 2) P&L consolidado mensual
    # ------------------------------------------------------------------ #
    def calculate_monthly_pl(self) -> pd.DataFrame:
        prod_df = self.calculate_product_level()

        pl = (prod_df.groupby('year_month')[['revenue', 'cost']]
                     .sum()
                     .reset_index())

        # CAC (si se suministró active_users_monthly)
        if self.active_users is not None:
            pl = pl.merge(self.active_users, on='year_month', how='left')
            pl['cac_cost'] = pl['active_users'] * 25
        else:
            pl['cac_cost'] = 0
            pl['active_users'] = 0

        pl['total_cost'] = pl['cost'] + pl['cac_cost']
        pl['pl'] = pl['revenue'] - pl['total_cost']
        pl['arr'] = pl['pl'] * 12
        pl['arc'] = (pl['pl'] / pl['active_users']).round(2).fillna(0)
        pl['pl_arr'] = (pl['pl'] / pl['arr']).round(4).fillna(0)

        cols = ['year_month', 'revenue', 'cost', 'cac_cost',
                'total_cost', 'pl', 'arr', 'arc', 'pl_arr']
        return pl[cols].round(2)

    # Export helpers ---------------------------------------------------- #
    @staticmethod
    def export_product_metrics(product_df: pd.DataFrame, path: str) -> None:
        product_df.to_csv(path, index=False)

    @staticmethod
    def export_pl_monthly(pl_df: pd.DataFrame, path: str) -> None:
        pl_df.to_csv(path, index=False) 