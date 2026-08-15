#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
using System.Windows.Media;
using System.Globalization;
#endregion

// =============================================================================
//  NomadeBot_MomentumBreakout  —  Estrategia comparativa p/ Strategy Analyzer
// -----------------------------------------------------------------------------
//  Logica:
//    - Identifica consolidacao (ATR abaixo de um limiar) por N barras seguidas.
//    - Guarda a maxima/minima dessa zona comprimida.
//    - Quando o ATR volta a expandir (>= limiar) E o preco fecha rompendo a
//      maxima/minima da consolidacao: entra na direcao do rompimento.
//    Stop = dentro da zona (metade do ATR atual). Alvo = N x ATR atual.
//
//  ⚠️ O limiar de ATR (pontos) e um valor ABSOLUTO — depende do instrumento e
//  do timeframe. No MNQ 5min normalmente fica entre ~8 e ~20 pontos, mas
//  VARIA com o regime de volatilidade do mercado. Rode o Strategy Analyzer,
//  olhe o log (Print do ATR medio) e ajuste antes de tirar conclusao de
//  performance — o padrao abaixo e so um ponto de partida.
//
//  IMPORTANTE — FUSO DO GRAFICO: assume grafico configurado em ET.
//  Tools > Options > General > Time Zone = "(UTC-05:00) Eastern Time".
//
//  Uso: Strategy Analyzer, MNQ 5 min, Calculate = OnBarClose.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class NomadeBot_MomentumBreakout : Strategy
	{
		// ---------- Estado da consolidacao (janela deslizante) ----------
		private int    consolBarras = 0;
		private double consolHigh   = 0, consolLow = 0;

		// ---------- Indicador ATR ----------
		private ATR atr;

		// ---------- Risco / controle diario ----------
		private string diaCorrente   = "";
		private double pnlInicioDia  = 0;
		private bool   bloqueadoHoje = false;
		private int    tradeSeq = 0;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description					= @"Comparativo: rompimento de consolidacao com filtro de expansao do ATR. MNQ 5min.";
				Name						= "NomadeBot_MomentumBreakout";
				Calculate					= Calculate.OnBarClose;
				EntriesPerDirection			= 1;
				EntryHandling				= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy = false;
				IsFillLimitOnTouch			= false;
				MaximumBarsLookBack			= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution			= OrderFillResolution.Standard;
				Slippage					= 0;
				StartBehavior				= StartBehavior.AdoptAccountPosition;
				TimeInForce					= TimeInForce.Gtc;
				TraceOrders					= false;
				RealtimeErrorHandling		= RealtimeErrorHandling.IgnoreAllErrors;
				StopTargetHandling			= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade			= 30;
				IsInstantiatedOnEachOptimizationIteration = true;

				Contratos			= 1;

				ATRPeriodo				= 14;
				ATRLimiarConsolidacao	= 12.0;   // ponto de partida p/ MNQ 5min — AJUSTAR apos olhar o log
				BarrasConsolidacao		= 3;      // minimo de barras comprimidas p/ validar a zona

				AlvoATRMultiplo		= 2.0;    // alvo = 2x o ATR do rompimento
				StopATRMultiplo	= 0.5;    // stop = 0.5x o ATR (dentro da zona)

				HorarioInicio		= 930;
				MinutosSemOperar	= 5;      // nao opera nos primeiros N minutos apos HorarioInicio
				EntradaFim			= 1500;
				FlattenHora			= 1550;

				StopDiarioDolar		= -300.0;
				MaxTradesDia		= 3;
			}
			else if (State == State.Configure)
			{
			}
			else if (State == State.DataLoaded)
			{
				atr = ATR(ATRPeriodo);
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBars[0] < BarsRequiredToTrade)
				return;

			int    agora = ToTime(Time[0]) / 100;   // assume grafico em ET
			string hoje  = Time[0].ToString("yyyy-MM-dd");

			// ---------- Virada de dia ----------
			if (hoje != diaCorrente)
			{
				diaCorrente   = hoje;
				bloqueadoHoje = false;
				pnlInicioDia  = RealizadoAcumulado();

				consolBarras = 0;
				consolHigh = consolLow = 0;
			}

			// ---------- Flatten forcado ----------
			if (agora >= FlattenHora)
			{
				if (Position.MarketPosition == MarketPosition.Long)
					ExitLong("Flatten_EOD");
				else if (Position.MarketPosition == MarketPosition.Short)
					ExitShort("Flatten_EOD");
				return;
			}

			// ---------- Kill switch diario ----------
			double pnlDia = RealizadoAcumulado() - pnlInicioDia;
			if (!bloqueadoHoje && StopDiarioDolar < 0 && pnlDia <= StopDiarioDolar)
			{
				bloqueadoHoje = true;
				Print(string.Format("{0}  🛑 STOP DIARIO atingido (${1:F2}) — sem novas entradas hoje.", Time[0], pnlDia));
			}

			double atrAtual = atr[0];
			int inicioLiberado = SomaHHmm(HorarioInicio, MinutosSemOperar);

			bool janelaAberta = agora >= HorarioInicio && agora < EntradaFim;
			bool podeEntrar = !bloqueadoHoje && Position.MarketPosition == MarketPosition.Flat
				&& agora >= inicioLiberado && agora < EntradaFim
				&& (MaxTradesDia <= 0 || TradesHoje() < MaxTradesDia);

			// ---------- Checa rompimento ANTES de atualizar a janela de consolidacao ----------
			// (usa consolHigh/consolLow acumulados ATE a barra anterior — sem lookahead)
			if (janelaAberta && podeEntrar && consolBarras >= BarrasConsolidacao && atrAtual >= ATRLimiarConsolidacao)
			{
				if (Close[0] > consolHigh)
				{
					double stopPrice = Close[0] - StopATRMultiplo * atrAtual;
					double tgtPrice  = Close[0] + AlvoATRMultiplo * atrAtual;

					string sinal = "MOM_Long_" + (++tradeSeq);
					SetStopLoss(sinal, CalculationMode.Price, stopPrice, false);
					SetProfitTarget(sinal, CalculationMode.Price, tgtPrice);
					EnterLong(Contratos, sinal);

					Print(string.Format("{0}  ✅ LONG (breakout) @ {1:F2} | ATR {2:F2} | SL {3:F2} | TP {4:F2}", Time[0], Close[0], atrAtual, stopPrice, tgtPrice));

					consolBarras = 0; consolHigh = consolLow = 0;   // regime comprimido acabou
					return;
				}
				else if (Close[0] < consolLow)
				{
					double stopPrice = Close[0] + StopATRMultiplo * atrAtual;
					double tgtPrice  = Close[0] - AlvoATRMultiplo * atrAtual;

					string sinal = "MOM_Short_" + (++tradeSeq);
					SetStopLoss(sinal, CalculationMode.Price, stopPrice, false);
					SetProfitTarget(sinal, CalculationMode.Price, tgtPrice);
					EnterShort(Contratos, sinal);

					Print(string.Format("{0}  ✅ SHORT (breakout) @ {1:F2} | ATR {2:F2} | SL {3:F2} | TP {4:F2}", Time[0], Close[0], atrAtual, stopPrice, tgtPrice));

					consolBarras = 0; consolHigh = consolLow = 0;
					return;
				}
			}

			// ---------- Atualiza a janela de consolidacao p/ a proxima barra ----------
			if (atrAtual < ATRLimiarConsolidacao)
			{
				if (consolBarras == 0)
				{
					consolHigh = High[0];
					consolLow  = Low[0];
				}
				else
				{
					consolHigh = Math.Max(consolHigh, High[0]);
					consolLow  = Math.Min(consolLow,  Low[0]);
				}
				consolBarras++;
			}
			else
			{
				// ATR alto sem ter rompido a zona (ou nao havia zona formada ainda) -> reseta
				consolBarras = 0;
				consolHigh = consolLow = 0;
			}
		}

		// ---------------- Utilitarios ----------------
		private int SomaHHmm(int hhmm, int minutos)
		{
			int h = hhmm / 100, m = hhmm % 100;
			int totalMin = h * 60 + m + minutos;
			return (totalMin / 60) * 100 + (totalMin % 60);
		}

		private double RealizadoAcumulado()
		{
			try { return SystemPerformance?.AllTrades?.TradesPerformance?.Currency?.CumProfit ?? 0; }
			catch { return 0; }
		}

		private int TradesHoje()
		{
			int n = 0;
			try
			{
				string hoje = Time[0].ToString("yyyy-MM-dd");
				var trades = SystemPerformance?.AllTrades;
				if (trades != null)
				{
					for (int i = trades.Count - 1; i >= 0; i--)
					{
						var exit = trades[i]?.Exit;
						if (exit == null) continue;
						if (exit.Time.ToString("yyyy-MM-dd") == hoje) n++;
						else break;
					}
				}
			}
			catch { }
			if (Position.MarketPosition != MarketPosition.Flat) n++;
			return n;
		}

		#region Properties
		[NinjaScriptProperty]
		[Range(1, 50)]
		[Display(Name="Contratos", Description="Qtd de contratos MNQ", Order=1, GroupName="1. Geral")]
		public int Contratos { get; set; }

		[NinjaScriptProperty]
		[Range(2, 50)]
		[Display(Name="ATR periodo", Order=10, GroupName="2. Consolidacao (ATR)")]
		public int ATRPeriodo { get; set; }

		[NinjaScriptProperty]
		[Range(0.5, 100)]
		[Display(Name="Limiar consolidacao (pontos)", Description="ATR abaixo disso = mercado comprimido. Ajustar olhando o ATR medio real do periodo testado.", Order=11, GroupName="2. Consolidacao (ATR)")]
		public double ATRLimiarConsolidacao { get; set; }

		[NinjaScriptProperty]
		[Range(1, 50)]
		[Display(Name="Barras min. consolidacao", Description="Minimo de barras seguidas com ATR baixo p/ validar a zona", Order=12, GroupName="2. Consolidacao (ATR)")]
		public int BarrasConsolidacao { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 10)]
		[Display(Name="Alvo (x ATR)", Description="TP = N x ATR do rompimento", Order=20, GroupName="3. Saida")]
		public double AlvoATRMultiplo { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 5)]
		[Display(Name="Stop (x ATR)", Description="SL = N x ATR do rompimento (0.5 = metade do ATR)", Order=21, GroupName="3. Saida")]
		public double StopATRMultiplo { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Horario Inicio (HHmm ET)", Order=30, GroupName="4. Horarios")]
		public int HorarioInicio { get; set; }

		[NinjaScriptProperty]
		[Range(0, 60)]
		[Display(Name="Minutos sem operar apos abertura", Description="Ex.: 5 = nao entra entre 9h30-9h35", Order=31, GroupName="4. Horarios")]
		public int MinutosSemOperar { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Entrada Fim (HHmm ET)", Order=32, GroupName="4. Horarios")]
		public int EntradaFim { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Flatten Hora (HHmm ET)", Order=33, GroupName="4. Horarios")]
		public int FlattenHora { get; set; }

		[NinjaScriptProperty]
		[Range(-100000, 0)]
		[Display(Name="Stop diario ($)", Description="Bloqueia novas entradas ao perder esse valor no dia (0 = desliga)", Order=40, GroupName="5. Risco")]
		public double StopDiarioDolar { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(Name="Max trades/dia", Description="0 = sem limite", Order=41, GroupName="5. Risco")]
		public int MaxTradesDia { get; set; }
		#endregion
	}
}
