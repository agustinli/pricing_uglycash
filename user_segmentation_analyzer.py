#!/usr/bin/env python3
"""
Sistema principal de análisis de segmentación de usuarios.
Orquesta el procesamiento de reglas, segmentación y cálculo de métricas.
"""

import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

from balance_rules_processor import BalanceRulesProcessor
from monthly_user_segmentation import MonthlyUserSegmentation
from group_metrics_calculator import GroupMetricsCalculator


class UserSegmentationAnalyzer:
    """Sistema principal de análisis de segmentación."""
    
    def __init__(self, transactions_file: str, rules_file: str):
        """
        Args:
            transactions_file: Path al CSV de transacciones
            rules_file: Path al CSV de reglas de balance
        """
        self.transactions_file = transactions_file
        self.rules_file = rules_file
        
        # Componentes del sistema
        self.rules_processor = None
        self.segmentation = None
        self.metrics_calculator = None
        
        # DataFrames principales
        self.df = None
        self.user_segments = None
        self.group_metrics = None
        
    def run_analysis(self):
        """Ejecuta el análisis completo."""
        print("\n=== ANÁLISIS DE SEGMENTACIÓN DE USUARIOS ===\n")
        
        # 1. Cargar y procesar transacciones
        print("1. Cargando transacciones y reglas...")
        self._load_and_process_data()
        
        # 2. Segmentar usuarios
        print("\n2. Segmentando usuarios mensualmente...")
        self._segment_users()
        
        # 3. Calcular métricas por grupo
        print("\n3. Calculando métricas por grupo...")
        self._calculate_group_metrics()
        
        # 4. Generar resumen
        print("\n4. Generando resumen...")
        self._print_summary()
        
    def _load_and_process_data(self):
        """Carga datos y aplica reglas de balance."""
        # Cargar transacciones
        self.df = pd.read_csv(self.transactions_file, parse_dates=['created_at'])
        print(f"✓ Cargadas {len(self.df):,} transacciones")
        
        # Inicializar procesador de reglas
        self.rules_processor = BalanceRulesProcessor(self.rules_file)
        
        # Aplicar reglas para calcular balances
        self.df = self.rules_processor.calculate_balances(self.df)
        print("✓ Balances calculados con reglas")
        
    def _segment_users(self):
        """Segmenta usuarios por balance y gastos."""
        # Inicializar segmentación
        self.segmentation = MonthlyUserSegmentation(self.df)
        
        # Calcular segmentos
        self.user_segments = self.segmentation.segment_users_monthly()
        
        # Agregar métricas de transacciones
        transaction_metrics = self.segmentation.prepare_transaction_metrics()
        
        # Merge con segmentos y llenar NaN solo en columnas numéricas
        merged = self.user_segments.merge(
            transaction_metrics,
            on=['user_id', 'year_month'],
            how='left'
        )

        # Rellenar NaN únicamente en columnas numéricas (evita problemas con columnas categóricas)
        numeric_cols = merged.select_dtypes(include=['number']).columns
        merged[numeric_cols] = merged[numeric_cols].fillna(0)
        self.user_segments = merged
        
    def _calculate_group_metrics(self):
        """Calcula métricas agregadas por grupo."""
        self.metrics_calculator = GroupMetricsCalculator(self.df, self.user_segments)
        self.group_metrics = self.metrics_calculator.calculate_group_metrics()
        
    def _print_summary(self):
        """Imprime resumen del análisis."""
        print("\n=== RESUMEN DEL ANÁLISIS ===")
        
        # Período analizado
        min_date = self.df['created_at'].min()
        max_date = self.df['created_at'].max()
        print(f"\nPeríodo: {min_date:%Y-%m-%d} a {max_date:%Y-%m-%d}")
        
        # Usuarios y transacciones
        print(f"Usuarios únicos: {self.df['user_id'].nunique():,}")
        print(f"Transacciones totales: {len(self.df):,}")
        
        # Segmentos
        print(f"\nSegmentos únicos: {self.group_metrics['segment'].nunique()}")
        print(f"Meses analizados: {self.group_metrics['year_month'].nunique()}")
        
        # Top segmentos por usuarios
        top_segments = self.group_metrics.groupby('segment')['usuarios_grupo'].sum().sort_values(ascending=False).head(10)
        print("\nTop 10 segmentos por cantidad de usuarios:")
        for segment, count in top_segments.items():
            print(f"  {segment}: {count:,} usuarios")
            
        # Usuarios activos por mes (balance > 0 o alguna transacción)
        active_users = self.user_segments[
            (self.user_segments['end_balance'] > 0) |
            (self.user_segments['card_tx_count'] > 0) |
            (self.user_segments['crypto_investment_amount'] > 0) |
            (self.user_segments['cash_virtual_deposit_amount'] > 0) |
            (self.user_segments['withdraw_crypto_amount'] > 0) |
            (self.user_segments['deposit_crypto_amount'] > 0) |
            (self.user_segments['bank_transfer_amount'] != 0)
        ]
        active_by_month = (
            active_users.groupby('year_month')['user_id']
            .nunique()
            .reset_index(name='active_users')
            .sort_values('year_month')
        )

        print("\nUsuarios con balance > 0 o actividad por mes:")
        for _, row in active_by_month.iterrows():
            print(f"  {row['year_month']}: {row['active_users']:,} usuarios")

        # Guardar para uso externo
        self.active_users_monthly = active_by_month
        
    def save_outputs(self, output_dir: str):
        """
        Guarda todos los resultados.
        
        Args:
            output_dir: Directorio de salida
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Métricas por grupo
        metrics_path = os.path.join(output_dir, 'group_metrics_monthly.csv')
        self.metrics_calculator.export_metrics_to_csv(self.group_metrics, metrics_path)
        
        # 2. Segmentos de usuarios
        segments_path = os.path.join(output_dir, 'user_segments_monthly.csv')
        self.user_segments.to_csv(segments_path, index=False)
        print(f"✓ Segmentos guardados en {segments_path}")
        
        # 3. Distribución de segmentos
        distribution = self.segmentation.get_segment_distribution()
        dist_path = os.path.join(output_dir, 'segment_distribution.csv')
        distribution.to_csv(dist_path, index=False)
        print(f"✓ Distribución guardada en {dist_path}")

        # 4. Usuarios activos
        if hasattr(self, 'active_users_monthly'):
            active_path = os.path.join(output_dir, 'active_users_monthly.csv')
            self.active_users_monthly.to_csv(active_path, index=False)
            print(f"✓ Usuarios activos guardados en {active_path}")
        
        # 5. Generar visualizaciones
        self._generate_visualizations(output_dir)
        
    def _generate_visualizations(self, output_dir: str):
        """Genera gráficos del análisis."""
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # 1. Heatmap de segmentos
        self._plot_segment_heatmap(output_dir)
        
        # 2. Evolución temporal de segmentos principales
        self._plot_segment_evolution(output_dir)
        
        # 3. Métricas clave por segmento
        self._plot_key_metrics(output_dir)
        
    def _plot_segment_heatmap(self, output_dir: str):
        """Genera heatmap de usuarios por segmento."""
        # Preparar datos para heatmap
        pivot_data = self.group_metrics.pivot_table(
            index='segment',
            columns='year_month',
            values='usuarios_grupo',
            fill_value=0
        )
        
        # Crear figura
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # Heatmap
        sns.heatmap(
            pivot_data,
            cmap='YlOrRd',
            annot=True,
            fmt='g',
            cbar_kws={'label': 'Cantidad de usuarios'},
            ax=ax
        )
        
        ax.set_title('Distribución de Usuarios por Segmento y Mes')
        ax.set_xlabel('Mes')
        ax.set_ylabel('Segmento (Balance_Gasto)')
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'segment_heatmap.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
    def _plot_segment_evolution(self, output_dir: str):
        """Grafica evolución de segmentos principales."""
        # Top 5 segmentos
        top_segments = self.group_metrics.groupby('segment')['usuarios_grupo'].sum().nlargest(5).index
        
        # Filtrar datos
        evolution_data = self.group_metrics[self.group_metrics['segment'].isin(top_segments)]
        
        # Crear gráfico
        fig, ax = plt.subplots(figsize=(12, 6))
        
        for segment in top_segments:
            segment_data = evolution_data[evolution_data['segment'] == segment]
            ax.plot(
                segment_data['year_month'],
                segment_data['usuarios_grupo'],
                marker='o',
                label=segment,
                linewidth=2
            )
            
        ax.set_xlabel('Mes')
        ax.set_ylabel('Cantidad de Usuarios')
        ax.set_title('Evolución de los Top 5 Segmentos')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'segment_evolution.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
    def _plot_key_metrics(self, output_dir: str):
        """Grafica métricas clave por segmento."""
        # Agregar datos por segmento
        segment_summary = self.group_metrics.groupby('segment').agg({
            'usuarios_grupo': 'sum',
            'balance': 'mean',
            'tarjeta_valor_tx_promedio': 'mean',
            'tarjeta_tx_cantidad': 'sum'
        }).reset_index()
        
        # Top 10 segmentos por usuarios
        top_segments = segment_summary.nlargest(10, 'usuarios_grupo')
        
        # Crear subplots
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. Balance promedio
        ax1 = axes[0, 0]
        ax1.bar(range(len(top_segments)), top_segments['balance'], color='steelblue')
        ax1.set_xticks(range(len(top_segments)))
        ax1.set_xticklabels(top_segments['segment'], rotation=45, ha='right')
        ax1.set_ylabel('Balance Promedio (eUSD)')
        ax1.set_title('Balance Promedio por Segmento')
        
        # 2. Valor transacción promedio
        ax2 = axes[0, 1]
        ax2.bar(range(len(top_segments)), top_segments['tarjeta_valor_tx_promedio'], color='coral')
        ax2.set_xticks(range(len(top_segments)))
        ax2.set_xticklabels(top_segments['segment'], rotation=45, ha='right')
        ax2.set_ylabel('Valor Tx Promedio (eUSD)')
        ax2.set_title('Ticket Promedio de Tarjeta')
        
        # 3. Scatter: Balance vs Gasto
        ax3 = axes[1, 0]
        scatter = ax3.scatter(
            segment_summary['balance'],
            segment_summary['tarjeta_valor_tx_promedio'],
            s=segment_summary['usuarios_grupo'],
            alpha=0.6,
            c=segment_summary['usuarios_grupo'],
            cmap='viridis'
        )
        ax3.set_xlabel('Balance Promedio')
        ax3.set_ylabel('Valor Tx Promedio')
        ax3.set_title('Relación Balance vs Gasto (tamaño = usuarios)')
        plt.colorbar(scatter, ax=ax3, label='Usuarios')
        
        # 4. Usuarios por segmento
        ax4 = axes[1, 1]
        ax4.barh(range(len(top_segments)), top_segments['usuarios_grupo'], color='lightgreen')
        ax4.set_yticks(range(len(top_segments)))
        ax4.set_yticklabels(top_segments['segment'])
        ax4.set_xlabel('Cantidad de Usuarios')
        ax4.set_title('Usuarios por Segmento')
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'key_metrics_by_segment.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        print("✓ Visualizaciones generadas")


def main():
    """Función principal para CLI."""
    parser = argparse.ArgumentParser(
        description='Análisis de segmentación de usuarios con reducción dimensional'
    )
    parser.add_argument(
        '--transactions',
        required=True,
        help='Path al archivo CSV de transacciones'
    )
    parser.add_argument(
        '--rules',
        required=True,
        help='Path al archivo CSV de reglas de balance'
    )
    parser.add_argument(
        '--outdir',
        default='./segmentation_outputs',
        help='Directorio de salida (default: ./segmentation_outputs)'
    )
    
    args = parser.parse_args()
    
    # Ejecutar análisis
    analyzer = UserSegmentationAnalyzer(args.transactions, args.rules)
    analyzer.run_analysis()
    analyzer.save_outputs(args.outdir)
    
    print(f"\n✓ Análisis completado. Resultados en: {args.outdir}/")


if __name__ == '__main__':
    main()
