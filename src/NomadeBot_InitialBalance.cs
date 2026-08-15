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
//  NomadeBot_InitialBalance  —  Estrategia comparativa p/ Strategy Analyzer
// -----------------------------------------------------------------------------
//  Logica (estilo MaxAlgo "IB + retracao"):
//    1) Captura a maxima/minima da PRIMEIRA HORA (Initial Balance, IB).
//    2) Aguarda o preco ROMPER o IB (fechamento acima/abaixo).
//    3) Aguarda RETRACAO de volta ao topo/fundo do IB (zona de reteste).
//    4) Entra na direcao do rompimento original quando uma vela de
//       confirmacao fecha de volta naquela direcao.
//    Stop = alem do lado oposto do IB (com buffer configuravel).
//    Alvo = extensao configuravel do tamanho do IB, medida a partir da borda.
//
//  IMPORTANTE — FUSO DO GRAFICO: esta estrategia assume que o grafico esta
//  configurado em horario EASTERN (ET) — igual ao mercado dos EUA.
//  Tools > Options > General > Time Zone = "(UTC-05:00) Eastern Time".
//  Se o grafico estiver em outro fuso, os horarios abaixo vao bater errado.
//
//  Uso: Strategy Analyzer, MNQ 5 min, Calculate = OnBarClose.
//  Nao carrega posicao overnight (compativel com Apex): flatten forcado.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class NomadeBot_InitialBalance : Strategy
	{
		// ---------- Initial Balance do dia ----------
		private string diaCorrente = "";
		private double ibHigh = 0, ibLow = 0;
		private bool   ibFechado = false;      // true depois que a janela de IB terminou

		// ---------- Maquina de estado do setup ----------
		// fase: 0 = ainda formando IB | 1 = IB pronto, aguardando rompimento
		//       2 = rompeu p/ CIMA, aguardando reteste no topo do IB
		//       3 = rompeu p/ BAIXO, aguardando reteste no fundo do IB
		private int  fase = 0;
		private bool retestou = false;

		// ---------- Risco / controle diario ----------
		private double pnlInicioDia  = 0;
		private bool   bloqueadoHoje = false;

		// ---------- Sequencia de sinal (nomes unicos por trade) ----------
		private int tradeSeq = 0;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description					= @"Comparativo: Initial Balance (1a hora) + retracao ao IB + confirmacao. MNQ 5min.";
				Name						= "NomadeBot_InitialBalance";
				Calculate					= Calculate.OnBarClose;
				EntriesPerDirection			= 1;
				EntryHandling				= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy = false;   // flatten manual (FlattenHora) abaixo
				IsFillLimitOnTouch			= false;
				MaximumBarsLookBack			= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution			= OrderFillResolution.Standard;
				Slippage					= 0;
				StartBehavior				= StartBehavior.AdoptAccountPosition;
				TimeInForce					= TimeInForce.Gtc;
				TraceOrders					= false;
				RealtimeErrorHandling		= RealtimeErrorHandling.IgnoreAllErrors;
				StopTargetHandling			= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade			= 20;
				IsInstantiatedOnEachOptimizationIteration = true;

				Contratos			= 1;

				HorarioInicio		= 930;    // inicio do IB (abertura do pregao, ET)
				IBFimHora			= 1030;   // fim da janela de captura do IB (1a hora)
				EntradaFim			= 1500;   // nao abre trade novo depois disso
				FlattenHora			= 1550;   // fecha tudo

				ToleranciaRetestPontos	= 3.0;    // quao perto da borda do IB conta como "retestou"
				AlvoExtensaoIB			= 1.0;    // alvo = 1x o tamanho do IB, medido da borda rompida
				StopBufferPontos		= 1.0;    // stop = borda oposta do IB - buffer

				StopDiarioDolar		= -300.0; // 0 = desliga o kill switch
				MaxTradesDia		= 3;      // 0 = sem limite
			}
			else if (State == State.Configure)
			{
			}
			else if (State == State.DataLoaded)
			{
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBars[0] < BarsRequiredToTrade)
				return;

			// Assume grafico em ET (ver aviso no cabecalho do arquivo).
			int    agora = ToTime(Time[0]) / 100;   // HHmm
			string hoje  = Time[0].ToString("yyyy-MM-dd");

			// ---------- Virada de dia: zera tudo ----------
			if (hoje != diaCorrente)
			{
				diaCorrente   = hoje;
				bloqueadoHoje = false;
				pnlInicioDia  = RealizadoAcumulado();

				ibHigh    = 0;
				ibLow     = 0;
				ibFechado = false;
				fase      = 0;
				retestou  = false;
			}

			// ---------- Flatten forcado (prioridade maxima) ----------
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

			// ---------- 1) Captura do Initial Balance (1a hora) ----------
			if (agora >= HorarioInicio && agora < IBFimHora)
			{
				ibHigh = (ibHigh == 0) ? High[0] : Math.Max(ibHigh, High[0]);
				ibLow  = (ibLow  == 0) ? Low[0]  : Math.Min(ibLow,  Low[0]);
				return;   // ainda formando o IB, nao ha o que operar
			}

			if (agora >= IBFimHora && !ibFechado && ibHigh > 0)
			{
				ibFechado = true;
				fase      = 1;
				Print(string.Format("{0}  📊 IB fechado: {1:F2} - {2:F2} (range {3:F2}pt)", Time[0], ibLow, ibHigh, ibHigh - ibLow));
			}

			if (!ibFechado)
				return;   // IB nunca se formou direito (ex.: gráfico comecou no meio do dia)

			// ---------- Gestao de posicao aberta: nada a fazer aqui (stop/alvo ja setados) ----------
			if (Position.MarketPosition != MarketPosition.Flat)
				return;

			bool podeEntrar = !bloqueadoHoje
				&& agora >= IBFimHora && agora < EntradaFim
				&& (MaxTradesDia <= 0 || TradesHoje() < MaxTradesDia);

			// ---------- 2) Deteccao do rompimento ----------
			if (fase == 1)
			{
				if (Close[0] > ibHigh)
				{
					fase = 2;
					retestou = false;
					Print(string.Format("{0}  🔼 Rompimento de ALTA do IB @ {1:F2} — aguardando retracao.", Time[0], Close[0]));
				}
				else if (Close[0] < ibLow)
				{
					fase = 3;
					retestou = false;
					Print(string.Format("{0}  🔽 Rompimento de BAIXA do IB @ {1:F2} — aguardando retracao.", Time[0], Close[0]));
				}
				return;
			}

			// ---------- 3) e 4) Retracao + confirmacao — LONG ----------
			if (fase == 2)
			{
				// invalida o setup se o preco devolver todo o IB
				if (Close[0] < ibLow)
				{
					fase = 1;
					retestou = false;
					return;
				}

				if (!retestou && Low[0] <= ibHigh + ToleranciaRetestPontos)
					retestou = true;

				if (retestou && podeEntrar && Close[0] > Open[0] && Close[0] > ibHigh)
				{
					double ibRange   = ibHigh - ibLow;
					double stopPrice = ibLow - StopBufferPontos;
					double tgtPrice  = ibHigh + AlvoExtensaoIB * ibRange;

					string sinal = "IB_Long_" + (++tradeSeq);
					SetStopLoss(sinal, CalculationMode.Price, stopPrice, false);
					SetProfitTarget(sinal, CalculationMode.Price, tgtPrice);
					EnterLong(Contratos, sinal);

					Print(string.Format("{0}  ✅ LONG @ {1:F2} | SL {2:F2} | TP {3:F2}", Time[0], Close[0], stopPrice, tgtPrice));

					fase = 1;   // rearma p/ um possivel novo setup no mesmo dia (ate o limite de trades)
					retestou = false;
				}
				return;
			}

			// ---------- 3) e 4) Retracao + confirmacao — SHORT ----------
			if (fase == 3)
			{
				if (Close[0] > ibHigh)
				{
					fase = 1;
					retestou = false;
					return;
				}

				if (!retestou && High[0] >= ibLow - ToleranciaRetestPontos)
					retestou = true;

				if (retestou && podeEntrar && Close[0] < Open[0] && Close[0] < ibLow)
				{
					double ibRange   = ibHigh - ibLow;
					double stopPrice = ibHigh + StopBufferPontos;
					double tgtPrice  = ibLow - AlvoExtensaoIB * ibRange;

					string sinal = "IB_Short_" + (++tradeSeq);
					SetStopLoss(sinal, CalculationMode.Price, stopPrice, false);
					SetProfitTarget(sinal, CalculationMode.Price, tgtPrice);
					EnterShort(Contratos, sinal);

					Print(string.Format("{0}  ✅ SHORT @ {1:F2} | SL {2:F2} | TP {3:F2}", Time[0], Close[0], stopPrice, tgtPrice));

					fase = 1;
					retestou = false;
				}
				return;
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
		[Range(0, 2359)]
		[Display(Name="Horario Inicio (HHmm ET)", Description="Inicio da captura do Initial Balance (abertura do pregao)", Order=10, GroupName="2. Horarios")]
		public int HorarioInicio { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="IB Fim (HHmm ET)", Description="Fim da janela do Initial Balance (1a hora = 60min apos o inicio)", Order=11, GroupName="2. Horarios")]
		public int IBFimHora { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Entrada Fim (HHmm ET)", Description="Nao abre trade novo depois deste horario", Order=12, GroupName="2. Horarios")]
		public int EntradaFim { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Flatten Hora (HHmm ET)", Description="Fecha qualquer posicao aberta neste horario", Order=13, GroupName="2. Horarios")]
		public int FlattenHora { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(Name="Tolerancia reteste (pontos)", Description="Distancia da borda do IB que ainda conta como retracao valida", Order=20, GroupName="3. Setup")]
		public double ToleranciaRetestPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 10)]
		[Display(Name="Alvo (x tamanho do IB)", Description="Alvo = borda rompida + N x range do IB (TP)", Order=21, GroupName="3. Setup")]
		public double AlvoExtensaoIB { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(Name="Buffer do stop (pontos)", Description="Stop = borda oposta do IB, com este buffer extra (SL)", Order=22, GroupName="3. Setup")]
		public double StopBufferPontos { get; set; }

		[NinjaScriptProperty]
		[Range(-100000, 0)]
		[Display(Name="Stop diario ($)", Description="Bloqueia novas entradas ao perder esse valor no dia (0 = desliga)", Order=30, GroupName="4. Risco")]
		public double StopDiarioDolar { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(Name="Max trades/dia", Description="0 = sem limite", Order=31, GroupName="4. Risco")]
		public int MaxTradesDia { get; set; }
		#endregion
	}
}
