import pandas as pd
import pytest

from balance_rules_processor import BalanceRulesProcessor

# Ruta al archivo de reglas dentro del proyecto
RULES_FILE = 'Movimientos_por_tipo_y_side___completa_efecto.csv'

@pytest.fixture(scope="module")
def processor():
    """Instancia de BalanceRulesProcessor compartida para las pruebas."""
    return BalanceRulesProcessor(RULES_FILE)


def test_get_effect(processor):
    """Verifica que get_effect devuelva el valor correcto para distintos casos."""
    assert processor.get_effect('card', 'debit') == -1
    assert processor.get_effect('card', 'credit') == 1
    # Caso por defecto (rule not found)
    assert processor.get_effect('foo', 'bar') == 0


def test_apply_rules_to_transaction(processor):
    """Prueba apply_rules_to_transaction con ejemplos sencillos."""
    # Transacción de tarjeta (debit) asentada
    row1 = pd.Series({
        'status': 'settled',
        'activity_type': 'card',
        'side': 'debit',
        'amount': 100
    })
    assert processor.apply_rules_to_transaction(row1) == -100

    # Transacción de tarjeta (credit) asentada
    row2 = pd.Series({
        'status': 'settled',
        'activity_type': 'card',
        'side': 'credit',
        'amount': 50
    })
    assert processor.apply_rules_to_transaction(row2) == 50

    # Transacción pendiente no debería afectar el balance
    row3 = pd.Series({
        'status': 'pending',
        'activity_type': 'card',
        'side': 'debit',
        'amount': 80
    })
    assert processor.apply_rules_to_transaction(row3) == 0.0


def test_calculate_balances_and_identify_card_spending(processor):
    """Comprueba el cálculo de balances y la identificación de gastos de tarjeta."""
    data = [
        # Usuario A – gasto tarjeta debit
        {
            'user_id': 'A',
            'currency': 'eUSD',
            'created_at': '2024-01-01',
            'activity_type': 'card',
            'side': 'debit',
            'status': 'settled',
            'amount': 100
        },
        # Usuario A – devolución tarjeta credit
        {
            'user_id': 'A',
            'currency': 'eUSD',
            'created_at': '2024-01-02',
            'activity_type': 'card',
            'side': 'credit',
            'status': 'settled',
            'amount': 20
        },
        # Usuario B – transferencia bancaria credit
        {
            'user_id': 'B',
            'currency': 'eUSD',
            'created_at': '2024-01-03',
            'activity_type': 'bank_transfer',
            'side': 'credit',
            'status': 'settled',
            'amount': 200
        },
    ]

    df = pd.DataFrame(data)
    df['created_at'] = pd.to_datetime(df['created_at'])

    # Calcular balances
    processed = processor.calculate_balances(df)

    # Comprobaciones básicas
    assert processed.loc[0, 'signed_amount'] == -100  # primer registro
    assert processed.loc[1, 'signed_amount'] == 20    # segundo registro

    # Balance acumulado usuario A: -100 + 20 = -80
    balance_A_end = processed[processed['user_id'] == 'A']['balance'].iloc[-1]
    assert balance_A_end == -80

    # Identificación de gastos de tarjeta debería devolver solo el primer registro (debit)
    card_spending = processor.identify_card_spending(processed)
    assert len(card_spending) == 1
    assert card_spending.iloc[0]['side'] == 'debit' 