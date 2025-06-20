#!/usr/bin/env python3
"""
Procesador de reglas de balance basado en el archivo CSV de reglas.
Aplica las reglas correctas para calcular balances según activity_type y side.
"""

import pandas as pd
from typing import Dict, Tuple
import os


class BalanceRulesProcessor:
    """Carga y aplica las reglas de balance desde el CSV."""
    
    def __init__(self, rules_file: str):
        """
        Args:
            rules_file: Path al archivo CSV con las reglas de balance
        """
        self.rules_file = rules_file
        self.rules_dict = {}
        self._load_rules()
        
    def _load_rules(self):
        """Carga las reglas desde el CSV a un diccionario."""
        try:
            rules_df = pd.read_csv(self.rules_file, delimiter=';')
        except FileNotFoundError:
            # Intentar fallback a nombre por defecto dentro del proyecto
            fallback = 'Movimientos_por_tipo_y_side___completa_efecto.csv'
            if os.path.exists(fallback):
                print(f"Advertencia: {self.rules_file} no encontrado. Usando {fallback} como fallback.")
                rules_df = pd.read_csv(fallback, delimiter=';')
            else:
                raise
        
        # Crear diccionario de reglas (activity_type, side) -> efecto
        for _, row in rules_df.iterrows():
            key = (row['activity_type'], row['side'])
            effect = row['efecto (+ / - / 0)']
            self.rules_dict[key] = effect
            
        print(f"✓ Cargadas {len(self.rules_dict)} reglas de balance")
        
    def get_effect(self, activity_type: str, side: str) -> int:
        """
        Obtiene el efecto de una transacción en el balance.
        
        Args:
            activity_type: Tipo de actividad
            side: Lado de la transacción
            
        Returns:
            1 para suma (+), -1 para resta (-), 0 para sin efecto
        """
        key = (activity_type, side)
        effect = self.rules_dict.get(key, '0')
        
        if effect == '+':
            return 1
        elif effect == '-':
            return -1
        else:
            return 0
            
    def apply_rules_to_transaction(self, row: pd.Series) -> float:
        """
        Aplica las reglas a una transacción para calcular su efecto en el balance.
        
        Args:
            row: Fila del DataFrame con la transacción
            
        Returns:
            Monto con signo aplicado según las reglas
        """
        # Solo procesar transacciones settled
        if row['status'] != 'settled':
            return 0.0
            
        effect = self.get_effect(row['activity_type'], row['side'])
        
        # Aplicar el efecto al monto
        # IMPORTANTE: Verificar si los montos ya vienen con signo
        # Si ya vienen con signo (negativos para débitos), usar directamente
        # Si no, aplicar el efecto
        
        # Por ahora asumimos que necesitamos aplicar el efecto
        return abs(row['amount']) * effect
        
    def calculate_balances(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula balances acumulados aplicando las reglas.
        
        Args:
            df: DataFrame con transacciones
            
        Returns:
            DataFrame con columna 'signed_amount' y 'balance' agregadas
        """
        df = df.copy()
        df = df.sort_values(['user_id', 'currency', 'created_at'])
        
        # Aplicar reglas para obtener signed_amount
        df['signed_amount'] = df.apply(self.apply_rules_to_transaction, axis=1)
        
        # Calcular balance acumulado por usuario y moneda
        df['balance'] = df.groupby(['user_id', 'currency'])['signed_amount'].cumsum()
        
        return df
        
    def identify_card_spending(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identifica gastos con tarjeta según las reglas especificadas.
        
        Gastos con tarjeta: activity_type='card' y (side='hold_captured' o side='debit')
        
        Args:
            df: DataFrame con transacciones
            
        Returns:
            DataFrame filtrado con solo gastos de tarjeta
        """
        card_spending = df[
            (df['activity_type'] == 'card') & 
            (df['side'].isin(['hold_captured', 'debit'])) &
            (df['status'] == 'settled')
        ].copy()
        
        return card_spending
        
    def get_transaction_type_rules(self, activity_type: str) -> Dict[str, int]:
        """
        Obtiene todas las reglas para un tipo de actividad.
        
        Args:
            activity_type: Tipo de actividad
            
        Returns:
            Dict con side -> efecto para ese activity_type
        """
        rules = {}
        for (act_type, side), effect in self.rules_dict.items():
            if act_type == activity_type:
                effect_int = 1 if effect == '+' else (-1 if effect == '-' else 0)
                rules[side] = effect_int
        return rules
        
    def print_rules_summary(self):
        """Imprime un resumen de las reglas cargadas."""
        print("\n=== RESUMEN DE REGLAS DE BALANCE ===")
        
        # Agrupar por activity_type
        activity_types = {}
        for (act_type, side), effect in self.rules_dict.items():
            if act_type not in activity_types:
                activity_types[act_type] = []
            activity_types[act_type].append((side, effect))
            
        # Imprimir por tipo
        for act_type in sorted(activity_types.keys()):
            print(f"\n{act_type}:")
            for side, effect in sorted(activity_types[act_type]):
                print(f"  {side:15} → {effect}")
