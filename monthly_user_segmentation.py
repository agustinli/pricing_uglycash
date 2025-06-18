#!/usr/bin/env python3
"""
Sistema de segmentación mensual de usuarios por balance y gastos con tarjeta.
Agrupa usuarios según criterios específicos y calcula métricas.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime


class MonthlyUserSegmentation:
    """Segmenta usuarios mensualmente por balance y gastos."""
    
    # Cortes de balance en eUSD
    BALANCE_BINS = [0, 10, 100, 500, 1000, 3000, 10000, float('inf')]
    BALANCE_LABELS = ['<10', '<100', '<500', '<1k', '<3k', '<10k', '>10k']
    
    # Cortes de gastos mensuales con tarjeta
    CARD_SPEND_BINS = [0, 1, 10, 100, 300, 500, 1000, float('inf')]
    CARD_SPEND_LABELS = ['<1', '<10', '<100', '<300', '<500', '<1k', '>1k']
    
    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: DataFrame con transacciones procesadas (incluye balance y signed_amount)
        """
        self.df = df
        self.monthly_balances = None
        self.monthly_card_spending = None
        self.user_segments = None
        
    def calculate_monthly_balances(self) -> pd.DataFrame:
        """
        Calcula el balance de cada usuario al final de cada mes.
        
        Returns:
            DataFrame con user_id, year_month, currency, end_balance
        """
        print("Calculando balances mensuales...")
        
        # Filtrar solo eUSD y transacciones settled
        eusd_df = self.df[
            (self.df['currency'] == 'eUSD') & 
            (self.df['status'] == 'settled')
        ].copy()
        
        # Agregar columna year_month
        eusd_df['year_month'] = eusd_df['created_at'].dt.to_period('M')
        
        # Para cada usuario y mes, obtener el último balance
        monthly_balances = []
        
        for (user_id, year_month), group in eusd_df.groupby(['user_id', 'year_month']):
            # Última transacción del mes
            last_tx = group.sort_values('created_at').iloc[-1]
            
            monthly_balances.append({
                'user_id': user_id,
                'year_month': year_month,
                'end_balance': last_tx['balance']
            })
            
        self.monthly_balances = pd.DataFrame(monthly_balances)
        print(f"✓ Calculados balances para {len(self.monthly_balances)} usuario-meses")
        
        # ===== NUEVO: asegurar cobertura completa usuario-mes =====
        # Crear grid con todos los usuarios y todos los meses del período analizado
        unique_users = eusd_df['user_id'].unique()
        all_months = pd.period_range(eusd_df['year_month'].min(), eusd_df['year_month'].max(), freq='M')

        full_index = pd.MultiIndex.from_product(
            [unique_users, all_months], names=['user_id', 'year_month']
        ).to_frame(index=False)

        # Combinar con los balances ya calculados
        full_balances = full_index.merge(
            self.monthly_balances,
            on=['user_id', 'year_month'],
            how='left'
        ).sort_values(['user_id', 'year_month'])

        # Propagar último balance conocido hacia adelante; si ningún balance previo, usar 0
        full_balances['end_balance'] = (
            full_balances.groupby('user_id')['end_balance']
            .ffill()
            .fillna(0)
        )

        # Reemplazar el atributo con la versión completa
        self.monthly_balances = full_balances
        print(f"✓ Balance mensual expandido a {len(self.monthly_balances)} usuario-meses (grid completo)")

        return self.monthly_balances
        
    def calculate_monthly_card_spending(self) -> pd.DataFrame:
        """
        Calcula el gasto mensual con tarjeta de cada usuario.
        
        Returns:
            DataFrame con user_id, year_month, total_card_spending
        """
        print("Calculando gastos mensuales con tarjeta...")
        
        # Filtrar gastos de tarjeta (hold_captured o debit)
        card_spending = self.df[
            (self.df['activity_type'] == 'card') &
            (self.df['side'].isin(['hold_captured', 'debit'])) &
            (self.df['status'] == 'settled') &
            (self.df['currency'] == 'eUSD')
        ].copy()
        
        # Agregar year_month
        card_spending['year_month'] = card_spending['created_at'].dt.to_period('M')
        
        # Agrupar por usuario y mes
        monthly_card_spending = card_spending.groupby(['user_id', 'year_month']).agg({
            'amount': lambda x: abs(x.sum()),  # Suma absoluta de gastos
            'created_at': 'count'  # Contar transacciones
        }).reset_index()
        
        monthly_card_spending.columns = ['user_id', 'year_month', 'total_card_spending', 'card_tx_count']
        
        self.monthly_card_spending = monthly_card_spending
        print(f"✓ Calculados gastos para {len(self.monthly_card_spending)} usuario-meses")
        
        return self.monthly_card_spending
        
    def segment_users_monthly(self) -> pd.DataFrame:
        """
        Segmenta usuarios por mes según balance y gastos.
        
        Returns:
            DataFrame con segmentación completa
        """
        print("Segmentando usuarios por balance y gastos...")
        
        # Asegurar que tenemos los datos calculados
        if self.monthly_balances is None:
            self.calculate_monthly_balances()
        if self.monthly_card_spending is None:
            self.calculate_monthly_card_spending()
            
        # Merge balances y gastos
        user_segments = self.monthly_balances.merge(
            self.monthly_card_spending,
            on=['user_id', 'year_month'],
            how='left'
        )
        
        # Llenar NaN en gastos con 0 (usuarios sin gastos ese mes)
        user_segments['total_card_spending'] = user_segments['total_card_spending'].fillna(0)
        user_segments['card_tx_count'] = user_segments['card_tx_count'].fillna(0)
        
        # Asignar bins de balance
        user_segments['balance_group'] = pd.cut(
            user_segments['end_balance'],
            bins=self.BALANCE_BINS,
            labels=self.BALANCE_LABELS,
            include_lowest=True
        )
        
        # Asignar bins de gastos
        user_segments['spending_group'] = pd.cut(
            user_segments['total_card_spending'],
            bins=self.CARD_SPEND_BINS,
            labels=self.CARD_SPEND_LABELS,
            include_lowest=True
        )
        
        # Crear grupo combinado
        user_segments['segment'] = (
            'B:' + user_segments['balance_group'].astype(str) + 
            '_S:' + user_segments['spending_group'].astype(str)
        )
        
        self.user_segments = user_segments
        print(f"✓ Segmentados {len(user_segments)} usuario-meses en {user_segments['segment'].nunique()} segmentos")
        
        return user_segments
        
    def prepare_transaction_metrics(self) -> pd.DataFrame:
        """
        Prepara métricas adicionales de transacciones por usuario-mes.
        
        Returns:
            DataFrame con métricas de transacciones por tipo
        """
        print("Preparando métricas de transacciones...")
        
        # Filtrar solo eUSD settled
        eusd_df = self.df[
            (self.df['currency'] == 'eUSD') & 
            (self.df['status'] == 'settled')
        ].copy()
        
        eusd_df['year_month'] = eusd_df['created_at'].dt.to_period('M')
        
        # Definir los tipos de transacciones a analizar
        metrics_config = {
            'crypto_investment': ['crypto_investment'],
            'cash_virtual_deposit': ['cash_load', 'virtual_deposit'],
            'withdraw_crypto': ['withdraw_crypto'],
            'deposit_crypto': ['incoming_crypto'],  # incoming_crypto es el depósito
            'bank_transfer': ['bank_transfer']
        }
        
        # Calcular métricas para cada tipo
        all_metrics = []
        
        for metric_name, activity_types in metrics_config.items():
            # Filtrar transacciones del tipo
            type_txs = eusd_df[eusd_df['activity_type'].isin(activity_types)]
            
            # Agrupar por usuario-mes
            monthly_metrics = type_txs.groupby(['user_id', 'year_month']).agg({
                'signed_amount': ['sum', 'count']
            }).reset_index()
            
            monthly_metrics.columns = ['user_id', 'year_month', f'{metric_name}_amount', f'{metric_name}_count']
            
            # Para métricas que son gastos (negativos), convertir a positivo
            if metric_name in ['crypto_investment', 'withdraw_crypto']:
                monthly_metrics[f'{metric_name}_amount'] = monthly_metrics[f'{metric_name}_amount'].abs()
            
            all_metrics.append(monthly_metrics)
            
        # ───── NUEVO BLOQUE  ──────────────────────────────
        # Definición auxiliar
        def _build(df, name):
            if df.empty:
                return pd.DataFrame(columns=[
                    'user_id', 'year_month',
                    f'{name}_amount', f'{name}_count'
                ])
            tmp = (df
                   .groupby(['user_id', 'year_month'])
                   .agg(signed_amount=('signed_amount', 'sum'),
                        tx_count=('signed_amount', 'count'))
                   .reset_index())
            tmp.columns = ['user_id', 'year_month',
                           f'{name}_amount', f'{name}_count']
            return tmp

        fiat_types = ['bank_transfer', 'virtual_deposit',
                      'international_transfer']

        # 1) Fiat deposit (+)
        all_metrics.append(
            _build(eusd_df[
                (eusd_df['activity_type'].isin(fiat_types)) &
                (eusd_df['signed_amount'] > 0)
            ], 'fiat_deposit')
        )

        # 2) Fiat withdrawal (–)
        tmp_with = eusd_df[
            (eusd_df['activity_type'].isin(fiat_types)) &
            (eusd_df['signed_amount'] < 0)
        ].copy()
        tmp_with.loc[:, 'signed_amount'] = tmp_with['signed_amount'].abs()
        all_metrics.append(_build(tmp_with, 'fiat_withdrawal'))

        # 3) Cash-load deposit (+)
        all_metrics.append(
            _build(eusd_df[
                (eusd_df['activity_type'] == 'cash_load') &
                (eusd_df['signed_amount'] > 0)
            ], 'cash_load_deposit')
        )

        # 4) Cash-load withdrawal (–)
        tmp_clw = eusd_df[
            (eusd_df['activity_type'] == 'cash_load') &
            (eusd_df['signed_amount'] < 0)
        ].copy()
        tmp_clw.loc[:, 'signed_amount'] = tmp_clw['signed_amount'].abs()
        all_metrics.append(_build(tmp_clw, 'cash_load_withdrawal'))
        # ──────────────────────────────────────────────────

        # Merge todas las métricas
        transaction_metrics = all_metrics[0]
        for m in all_metrics[1:]:
            transaction_metrics = transaction_metrics.merge(
                m, on=['user_id', 'year_month'], how='outer'
            )
            
        # Llenar NaN con 0
        transaction_metrics = transaction_metrics.fillna(0)
        
        print(f"✓ Calculadas métricas para {len(transaction_metrics)} usuario-meses")
        
        return transaction_metrics
        
    def get_segment_distribution(self) -> pd.DataFrame:
        """
        Obtiene la distribución de usuarios por segmento y mes.
        
        Returns:
            DataFrame con conteo de usuarios por segmento
        """
        if self.user_segments is None:
            self.segment_users_monthly()
            
        distribution = self.user_segments.groupby(['year_month', 'segment']).size().reset_index(name='user_count')
        
        # Agregar porcentaje
        total_by_month = distribution.groupby('year_month')['user_count'].transform('sum')
        distribution['percentage'] = (distribution['user_count'] / total_by_month * 100).round(2)
        
        return distribution.sort_values(['year_month', 'user_count'], ascending=[True, False])
