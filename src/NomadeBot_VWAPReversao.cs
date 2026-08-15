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
//  NomadeBot_VWAPReversao  —  Estrategia comparativa p/ Strategy Analyzer
// -----------------------------------------------------------------------------
//  Logica:
//    - VWAP diario (ancorado na abertura do pregao) + bandas de desvio padrao
//      ponderado por volume, calculadas na mao (nao depende do indicador
//      VWAP embutido do NT8 — funciona em qualquer versao).
//    - Preco toca banda de 2 desvios -> aguarda vela de rejeicao -> entra
//      na direcao do VWAP quando a vela SEGUINTE fecha naquela direcao.
//    - Filtro critico: DESLIGA completamente as entradas quando ADX > limiar
//      (mercado em tendencia forte — reversao a media nao funciona).
//    Stop = banda de 2.5 desvios. Alvo = VWAP (alvo primario).
//
//  SIMPLIFICACAO ASSUMIDA: o alvo secundario (banda oposta de 1 desvio)
//  descrito no pedido original NAO foi implementado como saida parcial —
//  o NT8 so aceita 1 SetProfitTarget por entrada nesse modelo simples.
//  O alvo usado e sempre o VWAP (alvo primario). Ver conversa para detalhe.
//
//  IMPORTANTE — FUSO DO GRAFICO: assume grafico configurado em ET.
//  Tools > Options > General > Time Zone = "(UTC-05:00) Eastern Time".
//
//  Uso: Strategy Analyzer, MNQ 5 min, Calculate = OnBarClose.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class NomadeBot_VWAPReversao : Strategy
	{
		// ---------- VWAP ancorado no dia (somas ponderadas por volume) ----------
		private string diaCorrente = "";
		private double somaPV  = 0;   // soma(typicalPrice * volume)
		private double somaPV2 = 0;   // soma(typicalPrice^2 * volume)
		private double somaVol = 0;

		private double vwap = 0, stdev = 0;
		private double bandaSup2 = 0, bandaInf2 = 0;   // gatilho de entrada (2 desvios)
		private double bandaSup1 = 0, bandaInf1 = 0;   // referencia (1 desvio)
		private double stopSup   = 0, stopInf   = 0;   // stop (N desvios, configuravel)

		// ---------- Maquina de estado do setup ----------
		// aguardandoConfirmShort/Long: true no bar seguinte a uma rejeicao na banda
		private bool aguardandoConfirmShort = false;
		private bool aguardandoConfirmLong  = false;
		private double vwapNoSinal = 0, stopNoSinal = 0;   // congela os niveis no momento da rejeicao

		// ---------- Indicador ADX (filtro de tendencia) ----------
		private ADX adx;

		// ---------- Risco / controle diario ----------
		private double pnlInicioDia  = 0;
		private bool   bloqueadoHoje = false;
		private int    tradeSeq = 0;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description					= @"Comparativo: reversao na banda de 2 desvios do VWAP, com filtro ADX. MNQ 5min.";
				Name						= "NomadeBot_VWAPReversao";
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

				DesvioEntradaBanda	= 2.0;    // banda que dispara o setup de reversao
				DesvioStopBanda		= 2.5;    // banda usada como stop
				DesvioRefBanda1		= 1.0;    // banda de referencia (1 desvio) — informativa

				ADXPeriodo			= 14;
				ADXDesativaAcima	= 30.0;   // desliga tudo acima disso (mercado em tendencia forte)

				HorarioInicio		= 930;
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
				adx = ADX(ADXPeriodo);
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBars[0] < BarsRequiredToTrade)
				return;

			int    agora = ToTime(Time[0]) / 100;   // assume grafico em ET
			string hoje  = Time[0].ToString("yyyy-MM-dd");

			// ---------- Virada de dia: zera o VWAP ancorado ----------
			if (hoje != diaCorrente)
			{
				diaCorrente   = hoje;
				bloqueadoHoje = false;
				pnlInicioDia  = RealizadoAcumulado();

				somaPV = somaPV2 = somaVol = 0;
				aguardandoConfirmShort = false;
				aguardandoConfirmLong  = false;
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

			// ---------- Atualiza VWAP + bandas (so dentro do pregao) ----------
			if (agora < HorarioInicio)
				return;

			double vol = Volume[0] > 0 ? Volume[0] : 1;   // guarda contra dado sem volume (ex.: replay)
			double tp  = (High[0] + Low[0] + Close[0]) / 3.0;

			somaPV  += tp * vol;
			somaPV2 += tp * tp * vol;
			somaVol += vol;

			if (somaVol <= 0)
				return;

			vwap = somaPV / somaVol;
			double variancia = (somaPV2 / somaVol) - (vwap * vwap);
			stdev = Math.Sqrt(Math.Max(variancia, 0));

			bandaSup2 = vwap + DesvioEntradaBanda * stdev;
			bandaInf2 = vwap - DesvioEntradaBanda * stdev;
			bandaSup1 = vwap + DesvioRefBanda1 * stdev;
			bandaInf1 = vwap - DesvioRefBanda1 * stdev;
			stopSup   = vwap + DesvioStopBanda * stdev;
			stopInf   = vwap - DesvioStopBanda * stdev;

			// ---------- Gestao de posicao aberta: nada a fazer (stop/alvo ja setados) ----------
			if (Position.MarketPosition != MarketPosition.Flat)
			{
				aguardandoConfirmShort = false;
				aguardandoConfirmLong  = false;
				return;
			}

			bool filtroADX  = ADXDesativaAcima <= 0 || adx[0] <= ADXDesativaAcima;
			bool podeEntrar = !bloqueadoHoje && filtroADX
				&& agora >= HorarioInicio && agora < EntradaFim
				&& (MaxTradesDia <= 0 || TradesHoje() < MaxTradesDia);

			// ---------- Confirmacao pendente de uma rejeicao anterior ----------
			if (aguardandoConfirmShort)
			{
				aguardandoConfirmShort = false;   // so vale para a barra imediatamente seguinte
				if (podeEntrar && Close[0] < Open[0] && Close[0] < Close[1])
				{
					string sinal = "VWAP_Short_" + (++tradeSeq);
					SetStopLoss(sinal, CalculationMode.Price, stopNoSinal, false);
					SetProfitTarget(sinal, CalculationMode.Price, vwapNoSinal);
					EnterShort(Contratos, sinal);
					Print(string.Format("{0}  ✅ SHORT (reversao VWAP) @ {1:F2} | SL {2:F2} | TP {3:F2}", Time[0], Close[0], stopNoSinal, vwapNoSinal));
					return;
				}
			}
			if (aguardandoConfirmLong)
			{
				aguardandoConfirmLong = false;
				if (podeEntrar && Close[0] > Open[0] && Close[0] > Close[1])
				{
					string sinal = "VWAP_Long_" + (++tradeSeq);
					SetStopLoss(sinal, CalculationMode.Price, stopNoSinal, false);
					SetProfitTarget(sinal, CalculationMode.Price, vwapNoSinal);
					EnterLong(Contratos, sinal);
					Print(string.Format("{0}  ✅ LONG (reversao VWAP) @ {1:F2} | SL {2:F2} | TP {3:F2}", Time[0], Close[0], stopNoSinal, vwapNoSinal));
					return;
				}
			}

			if (!podeEntrar)
				return;

			// ---------- Deteccao de rejeicao na banda de 2 desvios ----------
			// Toque + fechamento de volta pra dentro da banda = candle de rejeicao.
			bool rejeitouTopo  = High[0] >= bandaSup2 && Close[0] < bandaSup2;
			bool rejeitouFundo = Low[0]  <= bandaInf2 && Close[0] > bandaInf2;

			if (rejeitouTopo)
			{
				aguardandoConfirmShort = true;
				vwapNoSinal = vwap;
				stopNoSinal = stopSup;
				Print(string.Format("{0}  👀 Rejeicao no topo (banda +{1:F1}dp) @ {2:F2} — aguardando confirmacao.", Time[0], DesvioEntradaBanda, High[0]));
			}
			else if (rejeitouFundo)
			{
				aguardandoConfirmLong = true;
				vwapNoSinal = vwap;
				stopNoSinal = stopInf;
				Print(string.Format("{0}  👀 Rejeicao no fundo (banda -{1:F1}dp) @ {2:F2} — aguardando confirmacao.", Time[0], DesvioEntradaBanda, Low[0]));
			}
		}

		// ---------------- Utilitarios ----------------
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
		[Range(0.5, 5)]
		[Display(Name="Desvio de entrada (banda)", Description="Banda (em desvios padrao) que dispara o setup de reversao", Order=10, GroupName="2. VWAP")]
		public double DesvioEntradaBanda { get; set; }

		[NinjaScriptProperty]
		[Range(0.5, 6)]
		[Display(Name="Desvio do stop (banda)", Description="Banda usada como stop loss (deve ser > desvio de entrada)", Order=11, GroupName="2. VWAP")]
		public double DesvioStopBanda { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 3)]
		[Display(Name="Desvio referencia (banda)", Description="Banda de referencia/alvo secundario informativo (padrao 1 desvio)", Order=12, GroupName="2. VWAP")]
		public double DesvioRefBanda1 { get; set; }

		[NinjaScriptProperty]
		[Range(2, 50)]
		[Display(Name="ADX periodo", Order=20, GroupName="3. Filtro ADX")]
		public int ADXPeriodo { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(Name="ADX desativa acima de", Description="Zero entradas novas quando ADX > este valor (0 = desliga o filtro). Ideal operar so com ADX<25.", Order=21, GroupName="3. Filtro ADX")]
		public double ADXDesativaAcima { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Horario Inicio (HHmm ET)", Description="Inicio do calculo do VWAP ancorado e das entradas", Order=30, GroupName="4. Horarios")]
		public int HorarioInicio { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Entrada Fim (HHmm ET)", Order=31, GroupName="4. Horarios")]
		public int EntradaFim { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Flatten Hora (HHmm ET)", Order=32, GroupName="4. Horarios")]
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
