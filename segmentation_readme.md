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

### Cortes de Gasto (Tarjeta + Investment)
- < 1 USD
- < 10 USD
- < 100 USD
- < 300 USD
- < 500 USD
- < 1,000 USD
- \> 1,000 USD

## 📈 Métricas Calculadas por Grupo

Para cada segmento mensual se calculan:

1. **usuarios_grupo**
2. **balance**
3. **tarjeta_tx_cantidad**
4. **tarjeta_valor_tx_promedio**
5. **tarjeta_promedio_usuario**
6. **investment_buy_tx_cantidad**
7. **investment_buy_valor_tx_promedio**
8. **investment_buy_promedio_usuario**
9. **investment_sell_tx_cantidad**
10. **investment_sell_valor_tx_promedio**
11. **investment_sell_promedio_usuario**
12. **crypto_deposit_tx_cantidad**
13. **crypto_deposit_valor_tx_promedio**
14. **crypto_deposit_promedio_usuario**
15. **crypto_withdraw_tx_cantidad**
16. **crypto_withdraw_valor_tx_promedio**
17. **crypto_withdraw_promedio_usuario**
18. **cash_deposit_tx_cantidad**
19. **cash_deposit_valor_tx_promedio**
20. **cash_deposit_promedio_usuario**
21. **cash_withdraw_tx_cantidad**
22. **cash_withdraw_valor_tx_promedio**
23. **cash_withdraw_promedio_usuario**
24. **fiat_deposit_tx_cantidad**
25. **fiat_deposit_valor_tx_promedio**
26. **fiat_deposit_promedio_usuario**
27. **fiat_withdraw_tx_cantidad**
28. **fiat_withdraw_valor_tx_promedio**
29. **fiat_withdraw_promedio_usuario**

## 🚀 Uso Rápido

### Instalación
```bash
pip install pandas numpy matplotlib seaborn
```

### Ejecución por CLI
```bash
python user_segmentation_analyzer.py \
    --transactions olympus_all_txs.csv \
    --rules Movimientos_por_tipo_y_side___completa_efecto.csv \
    --outdir ./segmentation_outputs
```

### Uso Interactivo
```python
from user_segmentation_analyzer import UserSegmentationAnalyzer

# Inicializar
analyzer = UserSegmentationAnalyzer(
    transactions_file='olympus_all_txs.csv',
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
   - Calcula las 29 métricas solicitadas por grupo
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
    (group_metrics['balance'] > 1000) |
    (group_metrics['tarjeta_valor_tx_promedio'] > 100)
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

1. **Gasto total (Tarjeta + Investment)**: incluye  
  `activity_type='card'` (side `hold_captured` / `debit`) **y**  
  `activity_type='crypto_investment'` (buy y sell).

2. **Balances**: Se calculan aplicando las reglas del CSV, solo para transacciones `status='settled'`

3. **Moneda**: Todos los análisis se realizan en eUSD

4. **Período**: Las métricas son mensuales (agregadas por mes calendario)

## 🚧 Próximos Pasos

1. **Modelado predictivo**: Usar segmentos para predecir churn
2. **Optimización automática**: Algoritmos para encontrar pricing óptimo
3. **Dashboard interactivo**: Visualización en tiempo real
4. **Análisis de cohortes**: Evolución de segmentos en el tiempo
5. **Machine Learning**: Clustering automático sin bins predefinidos