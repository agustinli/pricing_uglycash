#!/usr/bin/env python3
"""
Calculador de métricas por grupo de usuarios.
Calcula todas las métricas solicitadas para cada segmento mensual.
"""

import pandas as pd
import numpy as np
from typing import Dict, List


class GroupMetricsCalculator:
    """Calcula métricas agregadas por grupo de usuarios."""
    
    def __init__(self, df: pd.DataFrame, user_segments: pd.DataFrame):
        """
        Args:
            df: DataFrame con todas las transacciones procesadas
            user_segments: DataFrame con la segmentación de usuarios por mes
        """
        self.df = df
        self.user_segments = user_segments
        
    def calculate_group_metrics(self) -> pd.DataFrame:
        """
        Calcula todas las métricas solicitadas por grupo.
        
        Métricas:
        1) usuarios_grupo: cantidad de usuarios en el grupo
        2) balance: balance promedio por usuario
        3) tarjeta: cantidad de transacciones de tarjeta, valor promedio de transacciones de tarjeta, valor promedio de consumo por usuario
        4) investment_buy: cantidad de transacciones de compra, valor promedio de transacciones de compra, valor promedio de compra por usuario
        6) investment_sell: cantidad de transacciones de venta, valor promedio de transacciones de venta, valor promedio de venta por usuario
        9) crypto_deposit: cantidad de transacciones de depósito de crypto, valor promedio de transacciones de depósito de crypto, valor promedio de depósito de crypto por usuario
        10) crypto_withdraw: cantidad de transacciones de retiro de crypto, valor promedio de transacciones de retiro de crypto, valor promedio de retiro de crypto por usuario
        12) cash_deposit: cantidad de transacciones de depósito de cash, valor promedio de transacciones de depósito de cash, valor promedio de depósito de cash por usuario
        13) cash_withdraw: cantidad de transacciones de retiro de cash, valor promedio de transacciones de retiro de cash, valor promedio de retiro de cash por usuario
        14) fiat_deposit: cantidad de transacciones de depósito de virtual + bank_transfer + international_transfer, valor promedio de transacciones de depósito de virtual + bank_transfer + international_transfer, valor promedio de depósito de virtual + bank_transfer + international_transfer por usuario
        15) fiat_withdraw: cantidad de transacciones de retiro de virtual + bank_transfer + international_transfer, valor promedio de transacciones de retiro de virtual + bank_transfer + international_transfer, valor promedio de retiro de virtual + bank_transfer + international_transfer por usuario
        
        Returns:
            DataFrame con todas las métricas por grupo y mes
        """
        print("Calculando métricas por grupo...")
        
        # Preparar datos de transacciones con year_month
        eusd_df = self.df[
            (self.df['currency'] == 'eUSD') & 
            (self.df['status'] == 'settled')
        ].copy()
        eusd_df['year_month'] = eusd_df['created_at'].dt.to_period('M')
        
        # Merge con segmentos para asignar grupo a cada transacción
        eusd_df = eusd_df.merge(
            self.user_segments[['user_id', 'year_month', 'segment']],
            on=['user_id', 'year_month'],
            how='inner'
        )
        
        # Inicializar DataFrame de resultados
        group_metrics = []
        
        # Para cada grupo y mes
        for (year_month, segment), group_data in eusd_df.groupby(['year_month', 'segment']):
            
            # Usuarios únicos en el grupo
            unique_users = group_data['user_id'].nunique()
            
            # Métricas base del segmento
            segment_info = self.user_segments[
                (self.user_segments['year_month'] == year_month) & 
                (self.user_segments['segment'] == segment)
            ]
            
            metrics = {
                'year_month': str(year_month),
                'segment': segment,
                
                # 1) usuarios en el grupo
                'usuarios_grupo': unique_users,
                # 2) balance promedio
                'balance': segment_info['end_balance'].mean()
            }
            
            # 3-4) Métricas de tarjeta
            card_txs = group_data[
                (group_data['activity_type'] == 'card') &
                (group_data['side'].isin(['hold_captured', 'debit']))
            ]
            
            tarjeta_total = abs(card_txs['signed_amount'].sum())
            metrics.update({
                'tarjeta_tx_cantidad'       : len(card_txs),
                'tarjeta_valor_tx_promedio' : abs(card_txs['amount'].mean()) if len(card_txs) else 0,
                'tarjeta_promedio_usuario'  : tarjeta_total / unique_users if unique_users else 0,
            })
            
            # 5-6) Crypto investment
            crypto_inv = group_data[group_data['activity_type'] == 'crypto_investment']
            
            buy  = crypto_inv[crypto_inv['signed_amount'] < 0]
            sell = crypto_inv[crypto_inv['signed_amount'] > 0]
            
            metrics.update({
                # buy
                'investment_buy_tx_cantidad'       : len(buy),
                'investment_buy_valor_tx_promedio' : abs(buy['amount'].mean()) if len(buy) else 0,
                'investment_buy_promedio_usuario'  : abs(buy['signed_amount'].sum()) / unique_users if unique_users else 0,
                # sell
                'investment_sell_tx_cantidad'       : len(sell),
                'investment_sell_valor_tx_promedio' : abs(sell['amount'].mean()) if len(sell) else 0,
                'investment_sell_promedio_usuario'  : abs(sell['signed_amount'].sum()) / unique_users if unique_users else 0,
            })
            
            # 7-8) Crypto deposit
            dep = group_data[group_data['activity_type'] == 'incoming_crypto']
            wdr = group_data[group_data['activity_type'] == 'withdraw_crypto']
            
            metrics.update({
                'crypto_deposit_tx_cantidad'       : len(dep),
                'crypto_deposit_valor_tx_promedio' : abs(dep['amount'].mean()) if len(dep) else 0,
                'crypto_deposit_promedio_usuario'  :  dep['signed_amount'].sum() / unique_users if unique_users else 0,

                'crypto_withdraw_tx_cantidad'       : len(wdr),
                'crypto_withdraw_valor_tx_promedio' : abs(wdr['amount'].mean()) if len(wdr) else 0,
                'crypto_withdraw_promedio_usuario'  : abs(wdr['signed_amount'].sum()) / unique_users if unique_users else 0,
            })
            
            # 9-10) Cash deposit
            cash_dep = group_data[(group_data['activity_type'] == 'cash_load') & (group_data['signed_amount'] > 0)]
            cash_wdr = group_data[(group_data['activity_type'] == 'cash_load') & (group_data['signed_amount'] < 0)]
            
            metrics.update({
                'cash_deposit_tx_cantidad'       : len(cash_dep),
                'cash_deposit_valor_tx_promedio' : abs(cash_dep['amount'].mean()) if len(cash_dep) else 0,
                'cash_deposit_promedio_usuario'  :  cash_dep['signed_amount'].sum() / unique_users if unique_users else 0,

                'cash_withdraw_tx_cantidad'       : len(cash_wdr),
                'cash_withdraw_valor_tx_promedio' : abs(cash_wdr['amount'].mean()) if len(cash_wdr) else 0,
                'cash_withdraw_promedio_usuario'  : abs(cash_wdr['signed_amount'].sum()) / unique_users if unique_users else 0,
            })
            
            # 11-12) Virtual deposit
            fiat_mask = group_data['activity_type'].isin(
                ['virtual_deposit', 'bank_transfer', 'international_transfer'])
            fiat_dep = group_data[fiat_mask & (group_data['signed_amount'] > 0)]
            fiat_wdr = group_data[fiat_mask & (group_data['signed_amount'] < 0)]
            
            metrics.update({
                'fiat_deposit_tx_cantidad'       : len(fiat_dep),
                'fiat_deposit_valor_tx_promedio' : abs(fiat_dep['amount'].mean()) if len(fiat_dep) else 0,
                'fiat_deposit_promedio_usuario'  :  fiat_dep['signed_amount'].sum() / unique_users if unique_users else 0,

                'fiat_withdraw_tx_cantidad'       : len(fiat_wdr),
                'fiat_withdraw_valor_tx_promedio' : abs(fiat_wdr['amount'].mean()) if len(fiat_wdr) else 0,
                'fiat_withdraw_promedio_usuario'  : abs(fiat_wdr['signed_amount'].sum()) / unique_users if unique_users else 0,
            })
            
            # Agregar a la lista
            group_metrics.append(metrics)
            
        # Convertir a DataFrame
        result_df = pd.DataFrame(group_metrics)
        
        # Ordenar por fecha y segmento
        result_df = result_df.sort_values(['year_month', 'segment'])
        
        # Redondear valores monetarios
        money_columns = [col for col in result_df.columns if 'promedio' in col or 'valor' in col]
        result_df[money_columns] = result_df[money_columns].round(2)
        
        print(f"✓ Calculadas métricas para {len(result_df)} grupo-meses")
        
        return result_df
        
    def calculate_summary_statistics(self, group_metrics: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula estadísticas resumidas por segmento.
        
        Args:
            group_metrics: DataFrame con métricas por grupo
            
        Returns:
            DataFrame con estadísticas resumidas
        """
        # Extraer componentes del segmento
        group_metrics['balance_segment'] = group_metrics['segment'].str.extract(r'B:([^_]+)')
        group_metrics['spending_segment'] = group_metrics['segment'].str.extract(r'S:(.+)')
        
        # Estadísticas por balance_segment
        balance_summary = group_metrics.groupby('balance_segment').agg({
            'usuarios_grupo': 'sum',
            'balance': 'mean',
            'tarjeta_valor_tx_promedio': 'mean',
            'tarjeta_tx_cantidad': 'sum'
        }).round(2)
        
        # Estadísticas por spending_segment
        spending_summary = group_metrics.groupby('spending_segment').agg({
            'usuarios_grupo': 'sum',
            'tarjeta_valor_tx_promedio': 'mean',
            'tarjeta_tx_cantidad': 'sum',
            'investment_buy_promedio_usuario': 'mean'
        }).round(2)
        
        return balance_summary, spending_summary
        
    def export_metrics_to_csv(self, group_metrics: pd.DataFrame, output_path: str):
        """
        Exporta las métricas a CSV con formato legible.
        
        Args:
            group_metrics: DataFrame con métricas
            output_path: Ruta para guardar el archivo
        """
        # Reordenar columnas para mejor legibilidad
        column_order = [
            'year_month', 'segment', 'usuarios_grupo', 'balance',
            'tarjeta_tx_cantidad',       'tarjeta_valor_tx_promedio',       'tarjeta_promedio_usuario',
            'investment_buy_tx_cantidad','investment_buy_valor_tx_promedio','investment_buy_promedio_usuario',
            'investment_sell_tx_cantidad','investment_sell_valor_tx_promedio','investment_sell_promedio_usuario',
            'crypto_deposit_tx_cantidad','crypto_deposit_valor_tx_promedio','crypto_deposit_promedio_usuario',
            'crypto_withdraw_tx_cantidad','crypto_withdraw_valor_tx_promedio','crypto_withdraw_promedio_usuario',
            'cash_deposit_tx_cantidad',  'cash_deposit_valor_tx_promedio',  'cash_deposit_promedio_usuario',
            'cash_withdraw_tx_cantidad', 'cash_withdraw_valor_tx_promedio', 'cash_withdraw_promedio_usuario',
            'fiat_deposit_tx_cantidad',  'fiat_deposit_valor_tx_promedio',  'fiat_deposit_promedio_usuario',
            'fiat_withdraw_tx_cantidad', 'fiat_withdraw_valor_tx_promedio', 'fiat_withdraw_promedio_usuario',
        ]
        
        # Asegurar que todas las columnas existen
        available_columns = [col for col in column_order if col in group_metrics.columns]
        
        # Exportar
        group_metrics[available_columns].to_csv(output_path, index=False)
        print(f"✓ Métricas exportadas a {output_path}")
