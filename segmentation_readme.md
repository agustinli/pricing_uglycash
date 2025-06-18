# Sistema de Segmentación de Usuarios y Análisis de Pricing

Sistema completo para análisis de usuarios con reducción dimensional basado en balance y gastos mensuales con tarjeta.

## 🎯 Objetivo

Reducir la dimensionalidad del problema agrupando usuarios mensualmente según:
- **Balance en eUSD** al cierre de mes
- **Volumen de gastos con tarjeta** mensual

Para luego analizar el impacto en revenue y P&L de diferentes decisiones de pricing.

## 📊 Segmentación

### Cortes de Balance (eUSD)
- < 10 USD
- < 100 USD  
- < 500 USD
- < 1,000 USD
- < 3,000 USD
- < 10,000 USD
- \> 10,000 USD

### Cortes de Gastos con Tarjeta
- < 1 USD
- < 10 USD
- < 100 USD
- < 300 USD
- < 500 USD
- < 1,000 USD
- \> 1,000 USD

## 📈 Métricas Calculadas por Grupo

Para cada segmento mensual se calculan:

1. **cantidad_usuarios_grupo** - Usuarios en el segmento
2. **balance_promedio** - Balance promedio en eUSD
3. **cantidad_txs_tarjeta** - Total de transacciones de tarjeta
4. **valor_tx_promedio** - Ticket promedio de tarjeta
5. **monto_crypto_investment_promedio** - Inversión crypto promedio
6. **cantidad_tx_crypto_investment** - Transacciones de inversión
7. **cash_load_virtual_deposit_promedio** - Depósitos promedio
8. **cantidad_tx_cash_load_virtual_deposit** - Transacciones de depósito
9. **withdraw_crypto_promedio** - Retiros crypto promedio
10. **cantidad_tx_withdraw_crypto** - Transacciones de retiro
11. **deposit_crypto_promedio** - Depósitos crypto promedio
12. **cantidad_tx_deposit_crypto** - Transacciones de depósito crypto
13. **bank_transfer_promedio** - Transferencias bancarias promedio
14. **cantidad_tx_bank_transfer** - Transacciones bancarias

## 🚀 Uso Rápido

### Instalación
```bash
pip install pandas numpy matplotlib seaborn
```

### Ejecución por CLI
```bash
python user_segmentation_analyzer.py \
    --transactions sample_uglycash_subset.csv \
    --rules Movimientos_por_tipo_y_side___completa_efecto.csv \
    --outdir ./segmentation_outputs
```

### Uso Interactivo
```python
from user_segmentation_analyzer import UserSegmentationAnalyzer

# Inicializar
analyzer = UserSegmentationAnalyzer(
    transactions_file='sample_uglycash_subset.csv',
    rules_file='Movimientos_por_tipo_y_side___completa_efecto.csv'
)

# Ejecutar análisis
analyzer.run_analysis()

# Acceder a resultados
user_segments = analyzer.user_segments  # Segmentación por usuario-mes
group_metrics = analyzer.group_metrics  # Métricas por grupo

# Guardar resultados
analyzer.save_outputs('./outputs')
```

## 📁 Archivos del Sistema

### Componentes Principales

1. **`balance_rules_processor.py`**
   - Carga y aplica reglas de balance desde CSV
   - Identifica gastos con tarjeta (side = hold_captured o debit)
   - Calcula balances correctamente según reglas

2. **`monthly_user_segmentation.py`**
   - Calcula balances mensuales por usuario
   - Calcula gastos mensuales con tarjeta
   - Segmenta usuarios en grupos bidimensionales
   - Prepara métricas de transacciones

3. **`group_metrics_calculator.py`**
   - Calcula las 14 métricas solicitadas por grupo
   - Agrega datos mensualmente
   - Exporta resultados formateados

4. **`user_segmentation_analyzer.py`**
   - Sistema principal que orquesta todo
   - Genera visualizaciones
   - Exporta todos los resultados

5. **`pricing_scenario_analyzer.py`**
   - Analiza escenarios de pricing
   - Calcula revenue por segmento
   - Compara impacto de cambios
   - Sugiere pricing diferenciado

## 📊 Análisis de Pricing

### Definir Escenario de Fees
```python
from pricing_scenario_analyzer import PricingScenarioAnalyzer

# Inicializar con métricas de grupos
pricing = PricingScenarioAnalyzer(group_metrics)

# Definir estructura de fees
fees = {
    'card_fee_pct': 0.015,          # 1.5% sobre gastos
    'crypto_investment_fee_pct': 0.01,  # 1% sobre inversiones
    'withdraw_crypto_fee': 5.0,      # $5 por retiro
    'bank_transfer_fee_pct': 0.02,   # 2% sobre transferencias
    'monthly_maintenance_fee': 0     # Sin fee mensual
}

# Calcular revenue
revenue = pricing.calculate_revenue_by_segment(fees)
```

### Comparar Escenarios
```python
# Escenarios alternativos
scenarios = {
    'conservative': {...},
    'aggressive': {...},
    'subscription': {...}
}

# Comparar
comparison = pricing.compare_scenarios(fees, scenarios)
```

## 📈 Outputs Generados

### CSVs
- `group_metrics_monthly.csv` - Métricas completas por grupo y mes
- `user_segments_monthly.csv` - Segmentación de cada usuario por mes
- `segment_distribution.csv` - Distribución de usuarios por segmento
- `revenue_by_segment.csv` - Revenue estimado por segmento

### Visualizaciones
- `segment_heatmap.png` - Heatmap de usuarios por segmento y mes
- `segment_evolution.png` - Evolución temporal de segmentos principales
- `key_metrics_by_segment.png` - Métricas clave por segmento

## 🔍 Interpretación de Segmentos

Los segmentos se nombran como: `B:<balance>_S:<spending>`

Ejemplos:
- `B:<100_S:<10` = Balance menor a $100, gasto menor a $10
- `B:1k-3k_S:100-300` = Balance entre $1k-3k, gasto entre $100-300
- `B:>10k_S:>1k` = Balance mayor a $10k, gasto mayor a $1k

## 💡 Casos de Uso

### 1. Identificar Segmentos de Alto Valor
```python
high_value = group_metrics[
    (group_metrics['balance_promedio'] > 1000) |
    (group_metrics['valor_tx_promedio'] > 100)
]
```

### 2. Analizar Elasticidad de Precios
```python
elasticity = pricing.calculate_price_elasticity(
    segment='B:1k-3k_S:100-300',
    fee_changes=[-20, -10, 0, 10, 20]
)
```

### 3. Optimizar Pricing por Segmento
```python
key_segments = pricing.identify_key_segments(
    min_users=50,
    min_revenue_per_user=10
)
suggestions = pricing.suggest_differentiated_pricing(key_segments)
```

## 🛠️ Personalización

### Cambiar Cortes de Segmentación
Modificar en `monthly_user_segmentation.py`:
```python
BALANCE_BINS = [0, 10, 100, 500, ...]  # Nuevos cortes
CARD_SPEND_BINS = [0, 1, 10, 100, ...]  # Nuevos cortes
```

### Agregar Nuevas Métricas
En `group_metrics_calculator.py`, agregar en el loop de cálculo:
```python
# Nueva métrica
new_metric = group_data[...].sum()
metrics['nueva_metrica'] = new_metric / unique_users
```

## 📝 Notas Importantes

1. **Gastos con tarjeta**: Se identifican por `activity_type='card'` y `side IN ('hold_captured', 'debit')`

2. **Balances**: Se calculan aplicando las reglas del CSV, solo para transacciones `status='settled'`

3. **Moneda**: Todos los análisis se realizan en eUSD

4. **Período**: Las métricas son mensuales (agregadas por mes calendario)

## 🚧 Próximos Pasos

1. **Modelado predictivo**: Usar segmentos para predecir churn
2. **Optimización automática**: Algoritmos para encontrar pricing óptimo
3. **Dashboard interactivo**: Visualización en tiempo real
4. **Análisis de cohortes**: Evolución de segmentos en el tiempo
5. **Machine Learning**: Clustering automático sin bins predefinidos