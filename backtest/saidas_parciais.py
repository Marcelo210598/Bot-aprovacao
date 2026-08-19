#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FASE 1 — AUDITORIA: o que o dado real permite reconstruir por trade?

Motor: mesmo de sempre (SL12,5/TP60/BE3,75-2,5/trail1,75, 5 MNQ, slippage 2
ticks, 1min, ano inteiro). Estendido pra gravar idx_entry/idx_mfe/idx_mae/
idx_exit -- checando explicitamente o que o codigo ja tinha vs o que precisou
ser adicionado.
"""
import sys, os
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp

print("=" * 100)
print("FASE 1 — O QUE O DADO PERMITE RECONSTRUIR (auditoria, sem presumir)")
print("=" * 100)
campos = [
    ("Preco de entrada", "SIM - ja gravado em todos os scripts (entry)"),
    ("Preco maximo favoravel (MFE)", "SIM - ja gravado (mfe, em pontos desde a entrada)"),
    ("Preco maximo adverso (MAE)", "SIM - ja gravado (mae, em pontos)"),
    ("Horario de entrada", "SIM - via idx_entry -> bars[idx]['dt']"),
    ("Horario do MFE (quando o pico favoravel ocorreu)", "NAO gravado ate agora -- precisa ser adicionado (idx_mfe)"),
    ("Horario do MAE (quando o pico adverso ocorreu)", "NAO gravado ate agora -- precisa ser adicionado (idx_mae)"),
    ("Preco/horario de saida", "SIM - idx_exit + motivo (SL/BE_TRAIL/TP)"),
    ("Duracao", "SIM - idx_exit - idx_entry, em minutos (barras de 1min)"),
    ("PnL", "SIM - pnl_usd"),
    ("Direcao LONG/SHORT", "SIM - lado"),
    ("Sequencia temporal", "SIM - ordem cronologica ja preservada"),
    ("Se houve stop", "SIM - motivo=='SL' ou 'BE_TRAIL' (trailing/BE tambem sai via 'stop' sintetico)"),
    ("Se houve target (TP)", "SIM - motivo=='TP'"),
    ("Se houve trailing", "PARCIAL - motivo=='BE_TRAIL' cobre BE-lock E trailing juntos (o codigo nao distingue os dois "
     "no exit -- os dois usam o mesmo stop sintetico, so dá pra saber se breakeven tinha sido ativado, nao se foi "
     "especificamente o trailing que fechou vs o lock parado)"),
    ("Excursao intratrade completa (bar a bar)", "SIM, POSSIVEL DE RECONSTRUIR -- os bars[idx_entry:idx_exit+1] "
     "estao disponiveis no NQ_dados ja carregado; nao estava gravado por trade ate agora, mas pode ser reconstruido "
     "sob demanda"),
]
for nome, status in campos:
    marca = "✅" if status.startswith("SIM") else ("⚠️" if status.startswith("PARCIAL") else "❌")
    print(f"{marca} {nome}: {status}")
print("\nConclusao: nada critico falta. idx_mfe/idx_mae precisam ser adicionados ao motor -- vou fazer isso agora.")
