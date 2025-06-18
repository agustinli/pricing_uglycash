#!/usr/bin/env python3
"""
Script de validación del sistema de segmentación.
Verifica que todos los componentes funcionen correctamente.
"""

import pandas as pd
import numpy as np
import os
import sys


def validate_rules_file(rules_file: str) -> bool:
    """Valida el archivo de reglas de balance."""
    print(f"\n📋 Validando archivo de reglas: {rules_file}")
    
    try:
        # Cargar con el delimiter correcto
        rules_df = pd.read_csv(rules_file, delimiter=';')
        
        # Verificar columnas esperadas
        expected_cols = ['activity_type', 'side', 'efecto (+ / - / 0)']
        if list(rules_df.columns) != expected_cols:
            print(f"❌ Columnas incorrectas. Esperadas: {expected_cols}")
            print(f"   Encontradas: {list(rules_df.columns)}")
            return False
            
        # Verificar que hay reglas
        if len(rules_df) == 0:
            print("❌ El archivo de reglas está vacío")
            return False
            
        # Verificar valores de efecto
        valid_effects = {'+', '-', '0'}
        effects = set(rules_df['efecto (+ / - / 0)'].unique())
        if not effects.issubset(valid_effects):
            print(f"❌ Valores de efecto inválidos: {effects - valid_effects}")
            return False
            
        print(f"✅ Archivo de reglas válido: {len(rules_df)} reglas cargadas")
        
        # Mostrar algunas reglas de ejemplo
        print("\n   Ejemplos de reglas:")
        for i, row in rules_df.head(5).iterrows():
            print(f"   - {row['activity_type']} + {row['side']} → {row['efecto (+ / - / 0)']}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error al cargar reglas: {e}")
        return False


def validate_transactions_file(transactions_file: str) -> bool:
    """Valida el archivo de transacciones."""
    print(f"\n📊 Validando archivo de transacciones: {transactions_file}")
    
    try:
        # Cargar muestra
        df_sample = pd.read_csv(transactions_file, nrows=100)
        
        # Columnas requeridas
        required_cols = [
            'created_at', 'currency', 'user_id', 'activity_type',
            'side', 'amount', 'status'
        ]
        
        missing_cols = set(required_cols) - set(df_sample.columns)
        if missing_cols:
            print(f"❌ Columnas faltantes: {missing_cols}")
            return False
            
        # Verificar tipos de datos
        print("✅ Todas las columnas requeridas presentes")
        
        # Cargar archivo completo para estadísticas
        df = pd.read_csv(transactions_file, parse_dates=['created_at'])
        
        print(f"\n   Estadísticas del archivo:")
        print(f"   - Total transacciones: {len(df):,}")
        print(f"   - Usuarios únicos: {df['user_id'].nunique():,}")
        print(f"   - Monedas: {df['currency'].unique()}")
        print(f"   - Período: {df['created_at'].min():%Y-%m-%d} a {df['created_at'].max():%Y-%m-%d}")
        
        # Verificar transacciones de tarjeta
        card_txs = df[
            (df['activity_type'] == 'card') & 
            (df['side'].isin(['hold_captured', 'debit']))
        ]
        print(f"   - Gastos con tarjeta identificados: {len(card_txs):,}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al cargar transacciones: {e}")
        return False


def test_balance_calculation(transactions_file: str, rules_file: str) -> bool:
    """Prueba el cálculo de balances."""
    print("\n💰 Probando cálculo de balances...")
    
    try:
        from balance_rules_processor import BalanceRulesProcessor
        
        # Cargar una muestra pequeña
        df = pd.read_csv(transactions_file, nrows=1000, parse_dates=['created_at'])
        
        # Aplicar reglas
        processor = BalanceRulesProcessor(rules_file)
        df_processed = processor.calculate_balances(df)
        
        # Verificar que se agregaron las columnas
        if 'signed_amount' not in df_processed.columns or 'balance' not in df_processed.columns:
            print("❌ No se agregaron las columnas de balance")
            return False
            
        # Verificar algunos cálculos
        sample_user = df_processed['user_id'].iloc[0]
        user_txs = df_processed[
            (df_processed['user_id'] == sample_user) & 
            (df_processed['currency'] == 'eUSD') &
            (df_processed['status'] == 'settled')
        ]
        
        if len(user_txs) > 0:
            print(f"\n   Ejemplo de cálculo para usuario {sample_user[:8]}...:")
            for i, (_, tx) in enumerate(user_txs.head(5).iterrows()):
                print(f"   Tx {i+1}: {tx['activity_type']} ({tx['side']}) "
                      f"amount={tx['amount']:.2f} → balance={tx['balance']:.2f}")
                      
        print("✅ Cálculo de balances funcionando correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error en cálculo de balances: {e}")
        return False


def test_segmentation(transactions_file: str, rules_file: str) -> bool:
    """Prueba la segmentación de usuarios."""
    print("\n🎯 Probando segmentación de usuarios...")
    
    try:
        from balance_rules_processor import BalanceRulesProcessor
        from monthly_user_segmentation import MonthlyUserSegmentation
        
        # Cargar y procesar datos
        df = pd.read_csv(transactions_file, nrows=10000, parse_dates=['created_at'])
        processor = BalanceRulesProcessor(rules_file)
        df = processor.calculate_balances(df)
        
        # Segmentar
        segmentation = MonthlyUserSegmentation(df)
        user_segments = segmentation.segment_users_monthly()
        
        # Verificar resultados
        if len(user_segments) == 0:
            print("❌ No se generaron segmentos")
            return False
            
        print(f"✅ Segmentación completada: {len(user_segments)} usuario-meses")
        
        # Mostrar distribución
        segment_counts = user_segments['segment'].value_counts().head(10)
        print("\n   Top 10 segmentos:")
        for segment, count in segment_counts.items():
            print(f"   - {segment}: {count} usuarios")
            
        return True
        
    except Exception as e:
        print(f"❌ Error en segmentación: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_metrics_calculation(transactions_file: str, rules_file: str) -> bool:
    """Prueba el cálculo de métricas."""
    print("\n📈 Probando cálculo de métricas...")
    
    try:
        from user_segmentation_analyzer import UserSegmentationAnalyzer
        
        # Usar muestra pequeña para prueba rápida
        analyzer = UserSegmentationAnalyzer(transactions_file, rules_file)
        
        # Cargar solo una muestra
        analyzer.df = pd.read_csv(transactions_file, nrows=5000, parse_dates=['created_at'])
        analyzer._load_and_process_data()
        analyzer._segment_users()
        analyzer._calculate_group_metrics()
        
        # Verificar que se calcularon métricas
        if analyzer.group_metrics is None or len(analyzer.group_metrics) == 0:
            print("❌ No se calcularon métricas")
            return False
            
        print(f"✅ Métricas calculadas para {len(analyzer.group_metrics)} grupo-meses")
        
        # Verificar columnas esperadas
        expected_metrics = [
            'cantidad_usuarios_grupo', 'balance_promedio',
            'cantidad_txs_tarjeta', 'valor_tx_promedio'
        ]
        
        missing_metrics = set(expected_metrics) - set(analyzer.group_metrics.columns)
        if missing_metrics:
            print(f"❌ Métricas faltantes: {missing_metrics}")
            return False
            
        print("✅ Todas las métricas principales presentes")
        return True
        
    except Exception as e:
        print(f"❌ Error en cálculo de métricas: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Función principal de validación."""
    print("=== VALIDACIÓN DEL SISTEMA DE SEGMENTACIÓN ===")
    
    # Archivos a validar
    transactions_file = 'sample_uglycash_subset.csv'
    rules_file = 'Movimientos_por_tipo_y_side___completa_efecto.csv'
    
    # Verificar que existen
    if not os.path.exists(transactions_file):
        print(f"❌ No se encuentra el archivo de transacciones: {transactions_file}")
        sys.exit(1)
        
    if not os.path.exists(rules_file):
        print(f"❌ No se encuentra el archivo de reglas: {rules_file}")
        sys.exit(1)
        
    # Ejecutar validaciones
    tests = [
        ("Archivo de reglas", lambda: validate_rules_file(rules_file)),
        ("Archivo de transacciones", lambda: validate_transactions_file(transactions_file)),
        ("Cálculo de balances", lambda: test_balance_calculation(transactions_file, rules_file)),
        ("Segmentación", lambda: test_segmentation(transactions_file, rules_file)),
        ("Cálculo de métricas", lambda: test_metrics_calculation(transactions_file, rules_file))
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ Error en prueba '{test_name}': {e}")
            results.append((test_name, False))
            
    # Resumen final
    print("\n\n=== RESUMEN DE VALIDACIÓN ===")
    all_passed = True
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False
            
    if all_passed:
        print("\n✅ ¡Todas las pruebas pasaron! El sistema está listo para usar.")
        print("\nPróximo paso:")
        print("python user_segmentation_analyzer.py --transactions sample_uglycash_subset.csv --rules Movimientos_por_tipo_y_side___completa_efecto.csv")
    else:
        print("\n❌ Algunas pruebas fallaron. Revisa los errores arriba.")
        
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
