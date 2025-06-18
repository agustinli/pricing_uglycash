#!/usr/bin/env python3
"""
Analizador de escenarios de pricing basado en segmentación de usuarios.
Permite evaluar el impacto de diferentes estructuras de fees en el revenue.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class PricingScenarioAnalyzer:
    """Analiza escenarios de pricing sobre segmentos de usuarios."""
    
    def __init__(self, group_metrics: pd.DataFrame, transactions_df: pd.DataFrame = None):
        """
        Args:
            group_metrics: DataFrame con métricas por grupo
            transactions_df: DataFrame opcional con transacciones para análisis detallado
        """
        self.group_metrics = group_metrics
        self.transactions_df = transactions_df
        
    def calculate_revenue_by_segment(self, fee_structure: Dict[str, float]) -> pd.DataFrame:
        """
        Calcula el revenue estimado por segmento con una estructura de fees.
        
        Args:
            fee_structure: Dict con fees:
                - card_fee_pct: % sobre transacciones de tarjeta
                - crypto_investment_fee_pct: % sobre inversiones crypto
                - withdraw_crypto_fee: Fee fijo por retiro
                - bank_transfer_fee_pct: % sobre transferencias
                - monthly_maintenance_fee: Fee mensual por usuario
                
        Returns:
            DataFrame con revenue por segmento
        """
        revenue_data = []
        
        for _, row in self.group_metrics.iterrows():
            segment_revenue = {
                'year_month': row['year_month'],
                'segment': row['segment'],
                'users': row['cantidad_usuarios_grupo']
            }
            
            # Revenue de tarjetas
            card_volume = row['valor_tx_promedio'] * row['cantidad_txs_tarjeta']
            segment_revenue['card_revenue'] = card_volume * fee_structure.get('card_fee_pct', 0)
            
            # Revenue de crypto investment
            crypto_volume = row['monto_crypto_investment_promedio'] * row['cantidad_usuarios_grupo']
            segment_revenue['crypto_revenue'] = crypto_volume * fee_structure.get('crypto_investment_fee_pct', 0)
            
            # Revenue de retiros crypto
            withdraw_count = row['cantidad_tx_withdraw_crypto']
            segment_revenue['withdraw_revenue'] = withdraw_count * fee_structure.get('withdraw_crypto_fee', 0)
            
            # Revenue de transferencias bancarias (asumiendo fee sobre el monto)
            bank_volume = abs(row['bank_transfer_promedio']) * row['cantidad_usuarios_grupo']
            segment_revenue['bank_transfer_revenue'] = bank_volume * fee_structure.get('bank_transfer_fee_pct', 0)
            
            # Fee mensual de mantenimiento
            segment_revenue['maintenance_revenue'] = row['cantidad_usuarios_grupo'] * fee_structure.get('monthly_maintenance_fee', 0)
            
            # Revenue total
            segment_revenue['total_revenue'] = (
                segment_revenue['card_revenue'] +
                segment_revenue['crypto_revenue'] +
                segment_revenue['withdraw_revenue'] +
                segment_revenue['bank_transfer_revenue'] +
                segment_revenue['maintenance_revenue']
            )
            
            revenue_data.append(segment_revenue)
            
        return pd.DataFrame(revenue_data)
        
    def compare_scenarios(self, base_fees: Dict, scenarios: Dict[str, Dict]) -> pd.DataFrame:
        """
        Compara múltiples escenarios de pricing.
        
        Args:
            base_fees: Estructura de fees base
            scenarios: Dict con nombre_escenario -> estructura_fees
            
        Returns:
            DataFrame con comparación de escenarios
        """
        # Calcular revenue base
        base_revenue = self.calculate_revenue_by_segment(base_fees)
        total_base = base_revenue['total_revenue'].sum()
        
        comparison_data = [{
            'scenario': 'current',
            'total_revenue': total_base,
            'revenue_per_user': total_base / base_revenue['users'].sum(),
            'card_revenue': base_revenue['card_revenue'].sum(),
            'crypto_revenue': base_revenue['crypto_revenue'].sum(),
            'withdraw_revenue': base_revenue['withdraw_revenue'].sum(),
            'maintenance_revenue': base_revenue['maintenance_revenue'].sum()
        }]
        
        # Calcular para cada escenario
        for scenario_name, fee_structure in scenarios.items():
            scenario_revenue = self.calculate_revenue_by_segment(fee_structure)
            total_scenario = scenario_revenue['total_revenue'].sum()
            
            comparison_data.append({
                'scenario': scenario_name,
                'total_revenue': total_scenario,
                'revenue_per_user': total_scenario / scenario_revenue['users'].sum(),
                'card_revenue': scenario_revenue['card_revenue'].sum(),
                'crypto_revenue': scenario_revenue['crypto_revenue'].sum(),
                'withdraw_revenue': scenario_revenue['withdraw_revenue'].sum(),
                'maintenance_revenue': scenario_revenue['maintenance_revenue'].sum(),
                'revenue_change': total_scenario - total_base,
                'revenue_change_pct': ((total_scenario - total_base) / total_base * 100)
            })
            
        comparison_df = pd.DataFrame(comparison_data)
        
        # Ordenar por revenue total
        comparison_df = comparison_df.sort_values('total_revenue', ascending=False)
        
        return comparison_df
        
    def analyze_segment_impact(self, base_fees: Dict, new_fees: Dict) -> pd.DataFrame:
        """
        Analiza el impacto del cambio de pricing por segmento.
        
        Args:
            base_fees: Fees actuales
            new_fees: Nuevos fees propuestos
            
        Returns:
            DataFrame con impacto por segmento
        """
        # Calcular revenues
        base_revenue = self.calculate_revenue_by_segment(base_fees)
        new_revenue = self.calculate_revenue_by_segment(new_fees)
        
        # Agrupar por segmento (sumando todos los meses)
        base_by_segment = base_revenue.groupby('segment').agg({
            'users': 'sum',
            'total_revenue': 'sum'
        }).reset_index()
        
        new_by_segment = new_revenue.groupby('segment').agg({
            'total_revenue': 'sum'
        }).reset_index()
        
        # Merge y calcular cambios
        impact = base_by_segment.merge(
            new_by_segment,
            on='segment',
            suffixes=('_base', '_new')
        )
        
        impact['revenue_change'] = impact['total_revenue_new'] - impact['total_revenue_base']
        impact['revenue_change_pct'] = (impact['revenue_change'] / impact['total_revenue_base'] * 100).round(1)
        impact['revenue_per_user_base'] = impact['total_revenue_base'] / impact['users']
        impact['revenue_per_user_new'] = impact['total_revenue_new'] / impact['users']
        
        # Ordenar por cambio absoluto
        impact = impact.sort_values('revenue_change', ascending=False)
        
        return impact
        
    def identify_key_segments(self, min_users: int = 10, min_revenue_per_user: float = 5) -> pd.DataFrame:
        """
        Identifica segmentos clave basados en criterios.
        
        Args:
            min_users: Mínimo de usuarios para considerar
            min_revenue_per_user: Revenue mínimo por usuario
            
        Returns:
            DataFrame con segmentos clave
        """
        # Usar fees estándar para evaluación
        standard_fees = {
            'card_fee_pct': 0.015,
            'crypto_investment_fee_pct': 0.01,
            'withdraw_crypto_fee': 5.0,
            'bank_transfer_fee_pct': 0.02,
            'monthly_maintenance_fee': 0
        }
        
        revenue = self.calculate_revenue_by_segment(standard_fees)
        
        # Agrupar por segmento
        segment_summary = revenue.groupby('segment').agg({
            'users': 'sum',
            'total_revenue': 'sum',
            'card_revenue': 'sum',
            'crypto_revenue': 'sum'
        }).reset_index()
        
        # Agregar métricas promedio del grupo
        avg_metrics = self.group_metrics.groupby('segment').agg({
            'balance_promedio': 'mean',
            'valor_tx_promedio': 'mean',
            'cantidad_txs_tarjeta': 'sum'
        }).reset_index()
        
        segment_summary = segment_summary.merge(avg_metrics, on='segment')
        
        # Calcular revenue por usuario
        segment_summary['revenue_per_user'] = segment_summary['total_revenue'] / segment_summary['users']
        
        # Filtrar segmentos clave
        key_segments = segment_summary[
            (segment_summary['users'] >= min_users) &
            (segment_summary['revenue_per_user'] >= min_revenue_per_user)
        ]
        
        # Clasificar segmentos
        key_segments['segment_value'] = pd.cut(
            key_segments['revenue_per_user'],
            bins=[0, 10, 25, 50, float('inf')],
            labels=['low_value', 'medium_value', 'high_value', 'premium']
        )
        
        # Ordenar por revenue total
        key_segments = key_segments.sort_values('total_revenue', ascending=False)
        
        # Renombrar columnas para claridad
        key_segments = key_segments.rename(columns={
            'balance_promedio': 'avg_balance',
            'valor_tx_promedio': 'avg_card_ticket',
            'cantidad_txs_tarjeta': 'total_card_txs'
        })
        
        return key_segments
        
    def suggest_differentiated_pricing(self, key_segments: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """
        Sugiere pricing diferenciado basado en segmentos.
        
        Args:
            key_segments: DataFrame con segmentos clave
            
        Returns:
            Dict con sugerencias de pricing por tipo de segmento
        """
        suggestions = {}
        
        # Para cada tipo de valor de segmento
        for segment_value in ['low_value', 'medium_value', 'high_value', 'premium']:
            segments = key_segments[key_segments['segment_value'] == segment_value]
            
            if len(segments) == 0:
                continue
                
            # Analizar características promedio
            avg_balance = segments['avg_balance'].mean()
            avg_ticket = segments['avg_card_ticket'].mean()
            avg_revenue_per_user = segments['revenue_per_user'].mean()
            
            # Sugerir fees basados en el perfil
            if segment_value == 'premium':
                # Usuarios premium: fees bajos, posible fee mensual
                suggestions[segment_value] = {
                    'card_fee_pct': 0.005,  # 0.5%
                    'crypto_investment_fee_pct': 0.005,
                    'withdraw_crypto_fee': 0,
                    'bank_transfer_fee_pct': 0.01,
                    'monthly_maintenance_fee': 19.99
                }
            elif segment_value == 'high_value':
                # Alto valor: fees moderados
                suggestions[segment_value] = {
                    'card_fee_pct': 0.01,  # 1%
                    'crypto_investment_fee_pct': 0.008,
                    'withdraw_crypto_fee': 2.0,
                    'bank_transfer_fee_pct': 0.015,
                    'monthly_maintenance_fee': 4.99
                }
            elif segment_value == 'medium_value':
                # Valor medio: fees estándar
                suggestions[segment_value] = {
                    'card_fee_pct': 0.015,  # 1.5%
                    'crypto_investment_fee_pct': 0.01,
                    'withdraw_crypto_fee': 5.0,
                    'bank_transfer_fee_pct': 0.02,
                    'monthly_maintenance_fee': 0
                }
            else:  # low_value
                # Bajo valor: fees más altos, sin fee mensual
                suggestions[segment_value] = {
                    'card_fee_pct': 0.02,  # 2%
                    'crypto_investment_fee_pct': 0.015,
                    'withdraw_crypto_fee': 7.0,
                    'bank_transfer_fee_pct': 0.025,
                    'monthly_maintenance_fee': 0
                }
                
        return suggestions
        
    def calculate_price_elasticity(self, segment: str, fee_changes: List[float]) -> pd.DataFrame:
        """
        Estima la elasticidad precio para un segmento específico.
        
        Args:
            segment: Nombre del segmento
            fee_changes: Lista de cambios porcentuales en fees [-20, -10, 0, 10, 20]
            
        Returns:
            DataFrame con análisis de elasticidad
        """
        segment_data = self.group_metrics[self.group_metrics['segment'] == segment]
        
        if len(segment_data) == 0:
            return pd.DataFrame()
            
        # Fees base
        base_fees = {
            'card_fee_pct': 0.015,
            'crypto_investment_fee_pct': 0.01,
            'withdraw_crypto_fee': 5.0,
            'bank_transfer_fee_pct': 0.02,
            'monthly_maintenance_fee': 0
        }
        
        elasticity_data = []
        
        for change_pct in fee_changes:
            # Ajustar fees
            adjusted_fees = {}
            for fee_name, fee_value in base_fees.items():
                if 'pct' in fee_name:
                    adjusted_fees[fee_name] = fee_value * (1 + change_pct/100)
                elif fee_name == 'withdraw_crypto_fee':
                    adjusted_fees[fee_name] = fee_value * (1 + change_pct/100)
                else:
                    adjusted_fees[fee_name] = fee_value
                    
            # Calcular revenue
            revenue = self.calculate_revenue_by_segment(adjusted_fees)
            segment_revenue = revenue[revenue['segment'] == segment]['total_revenue'].sum()
            
            elasticity_data.append({
                'fee_change_pct': change_pct,
                'total_revenue': segment_revenue,
                'revenue_per_user': segment_revenue / segment_data['cantidad_usuarios_grupo'].sum()
            })
            
        elasticity_df = pd.DataFrame(elasticity_data)
        
        # Calcular cambio vs base
        base_revenue = elasticity_df[elasticity_df['fee_change_pct'] == 0]['total_revenue'].iloc[0]
        elasticity_df['revenue_change_pct'] = (
            (elasticity_df['total_revenue'] - base_revenue) / base_revenue * 100
        )
        
        return elasticity_df
