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
#endregion

// =============================================================================
//  ApexApprovalSim  —  Backtest comparativo de estrategias p/ APROVAR conta Apex
// -----------------------------------------------------------------------------
//  Objetivo: medir, com dados reais do NQ, quantas avaliacoes Apex CADA estrategia
//  teria APROVADO vs REPROVADO no periodo. Roda no Strategy Analyzer do NT8.
//
//  Como usar:
//    1) Copie este .cs p/ Documents\NinjaTrader 8\bin\Custom\Strategies\
//    2) No NT8: Nova janela > Editor NinjaScript > F5 (compilar)
//    3) Strategy Analyzer > selecione "ApexApprovalSim" > NQ continuo > 12 meses
//    4) LIGUE "Tick Replay" (Strategy Analyzer > engrenagem) p/ DD intraday fiel
//    5) Rode 1x por Modo (ORB_VWAP / MeanReversion / Niveis) e compare o output
//
//  O resumo final (avaliacoes / aprovadas / reprovadas) sai na aba "Output"
//  (Nova janela > NinjaScript Output) ao terminar o backtest.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	// Modos de estrategia testados
	public enum ModoEstrategia
	{
		ORB_VWAP,        // Opening Range Breakout filtrado por VWAP de sessao
		MeanReversion,   // Reversao a media (extensao da VWAP)
		Niveis           // Rejeicao em niveis (high/low do dia anterior)
	}

	// Tamanho da conta Apex -> define meta de lucro e trailing drawdown
	public enum TamanhoConta
	{
		C25K,
		C50K,
		C100K,
		C150K,
		C250K,
		C300K
	}

	public class ApexApprovalSim : Strategy
	{
		// ---------- VWAP de sessao (calculo manual) ----------
		private double cumPV;     // soma de (preco tipico * volume)
		private double cumVol;    // soma de volume
		private double vwap;

		// ---------- ORB (opening range) ----------
		private double orbHigh;
		private double orbLow;
		private bool   orbPronto;       // janela ORB ja fechou
		private bool   tradeNoDiaFeito;  // ja entrou hoje (1 setup/dia p/ ORB)

		// ---------- Niveis do dia anterior ----------
		private double pdHigh = 0, pdLow = 0;   // prior-day high/low
		private double curHigh, curLow;          // acumula high/low do dia atual

		// ---------- Simulador de avaliacao Apex (maquina de estados) ----------
		private double metaLucro;        // ex: 3000 p/ conta 50K
		private double limiteDD;         // ex: 2500 p/ conta 50K
		private double realizadoNoInicio; // CumProfit no inicio da avaliacao atual
		private double picoEquity;        // maior equity atingido na avaliacao
		private double nivelDD;           // threshold do trailing DD (sobe com o pico)
		private HashSet<string> diasOperados = new HashSet<string>();
		private bool   avaliacaoAtiva;    // avaliacao em andamento

		private int avaliacoesTotais;
		private int aprovadas;
		private int reprovadas;
		private List<int> diasParaAprovar = new List<int>();
		private DateTime inicioAvaliacao;

		// ---------- Kill switch diario ----------
		private double pnlInicioDia;      // realizado no inicio do dia
		private string diaCorrente = "";
		private bool   bloqueadoHoje;     // estourou perda diaria -> nao opera mais hoje

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description					= @"Backtest comparativo de estrategias p/ aprovar conta Apex (ORB/MeanRev/Niveis) com simulador de avaliacao embutido.";
				Name						= "ApexApprovalSim";
				Calculate					= Calculate.OnBarClose;   // roda em barras de minuto; DD intraday estimado via High/Low (pior caso)
				EntriesPerDirection			= 1;
				EntryHandling				= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy = true;
				ExitOnSessionCloseSeconds	= 30;
				IsFillLimitOnTouch			= false;
				MaximumBarsLookBack			= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution			= OrderFillResolution.Standard;
				Slippage					= 0;
				StartBehavior				= StartBehavior.WaitUntilFlat;
				TimeInForce					= TimeInForce.Gtc;
				TraceOrders					= false;
				RealtimeErrorHandling		= RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling			= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade			= 20;
				IsInstantiatedOnEachOptimizationIteration = true;

				// ----- Parametros configuraveis -----
				Modo				= ModoEstrategia.ORB_VWAP;
				Conta				= TamanhoConta.C50K;
				Contratos			= 1;
				ModoIntradayDD		= true;   // true = trailing intraday (pior caso); false = EOD

				// Horarios (HHmm em ET — rode o grafico em horario US Eastern)
				SessaoInicio		= 930;
				ORBFim				= 935;
				EntradaFim			= 1015;
				FlattenHora			= 1555;

				// ORB
				ORBStopFatorRange	= 0.5;   // stop = meio do range (0.5 = half-back)
				ORBAlvoFatorRange	= 1.0;   // alvo = 1x a largura do range

				// Mean Reversion
				MRDistVWAPTicks		= 40;    // distancia da VWAP p/ entrar (em ticks)
				MRStopTicks			= 30;
				MRAlvoTicks			= 25;

				// Niveis
				NivStopTicks		= 24;
				NivAlvoTicks		= 30;

				// Kill switch diario (fracao do DD; 0.5 = para o dia ao perder 50% do DD)
				KillSwitchFracaoDD	= 0.5;

				// Comissao por contrato por lado (round-turn = 2x). Ajuste p/ sua corretora.
				ComissaoPorContrato	= 1.75;
			}
			else if (State == State.Configure)
			{
				// comissao/slippage aplicados no backtest p/ numero honesto
				Commission = ComissaoPorContrato;
				DefineMetaEDD();
			}
			else if (State == State.DataLoaded)
			{
				ResetAvaliacao(Time != null && CurrentBars[0] >= 0 ? Time[0] : DateTime.MinValue);
			}
			else if (State == State.Terminated)
			{
				ImprimeResumo();
			}
		}

		// Define meta de lucro e trailing DD conforme tamanho da conta (regras Apex 2026)
		private void DefineMetaEDD()
		{
			switch (Conta)
			{
				case TamanhoConta.C25K:  metaLucro = 1500;  limiteDD = 1500;  break;
				case TamanhoConta.C50K:  metaLucro = 3000;  limiteDD = 2500;  break;
				case TamanhoConta.C100K: metaLucro = 6000;  limiteDD = 3000;  break;
				case TamanhoConta.C150K: metaLucro = 9000;  limiteDD = 5000;  break;
				case TamanhoConta.C250K: metaLucro = 15000; limiteDD = 6500;  break;
				case TamanhoConta.C300K: metaLucro = 20000; limiteDD = 7500;  break;
			}
		}

		// Reinicia o estado de uma nova avaliacao
		private void ResetAvaliacao(DateTime quando)
		{
			realizadoNoInicio = SystemPerformance != null ? SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit : 0;
			picoEquity        = 0;
			nivelDD           = -limiteDD;   // threshold inicial (equity comeca em 0)
			diasOperados.Clear();
			avaliacaoAtiva    = true;
			inicioAvaliacao   = quando;
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBars[0] < BarsRequiredToTrade)
				return;

			int agora = ToTime(Time[0]) / 100;   // HHmm
			string hoje = Time[0].ToString("yyyy-MM-dd");

			// ----- Virada de dia -----
			if (hoje != diaCorrente)
			{
				diaCorrente = hoje;
				bloqueadoHoje = false;
				tradeNoDiaFeito = false;
				pnlInicioDia = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;

				// guarda high/low do dia anterior p/ modo Niveis
				if (curHigh > 0) { pdHigh = curHigh; pdLow = curLow; }
				curHigh = High[0]; curLow = Low[0];
			}
			else
			{
				curHigh = Math.Max(curHigh, High[0]);
				curLow  = Math.Min(curLow,  Low[0]);
			}

			// ----- VWAP de sessao -----
			if (Bars.IsFirstBarOfSession)
			{
				cumPV = 0; cumVol = 0;
				orbHigh = 0; orbLow = 0; orbPronto = false;
			}
			double tp = (High[0] + Low[0] + Close[0]) / 3.0;
			cumPV  += tp * Volume[0];
			cumVol += Volume[0];
			vwap = cumVol > 0 ? cumPV / cumVol : Close[0];

			// ----- Captura do ORB -----
			if (agora >= SessaoInicio && agora < ORBFim)
			{
				orbHigh = orbHigh == 0 ? High[0] : Math.Max(orbHigh, High[0]);
				orbLow  = orbLow  == 0 ? Low[0]  : Math.Min(orbLow,  Low[0]);
			}
			else if (agora >= ORBFim && !orbPronto && orbHigh > 0)
			{
				orbPronto = true;
			}

			// ----- Atualiza simulador Apex (a cada tick) -----
			AtualizaApexSim();

			// ----- Flatten no fim do dia -----
			if (agora >= FlattenHora)
			{
				if (Position.MarketPosition != MarketPosition.Flat)
					CerrarTudo("FlattenEOD");
				return;
			}

			// se avaliacao encerrou (aprovou/reprovou) nao opera ate proxima
			if (!avaliacaoAtiva) return;
			if (bloqueadoHoje)   return;

			// ----- Logica de entrada por modo -----
			if (Position.MarketPosition == MarketPosition.Flat)
			{
				switch (Modo)
				{
					case ModoEstrategia.ORB_VWAP:     EntradaORB(agora);          break;
					case ModoEstrategia.MeanReversion: EntradaMeanReversion(agora); break;
					case ModoEstrategia.Niveis:        EntradaNiveis(agora);        break;
				}
			}
		}

		// ---------------- Estrategia 1: ORB + VWAP ----------------
		private void EntradaORB(int agora)
		{
			if (!orbPronto || tradeNoDiaFeito) return;
			if (agora < ORBFim || agora >= EntradaFim) return;

			double range = orbHigh - orbLow;
			if (range <= 0) return;

			// rompe p/ cima e fecha acima da VWAP -> long
			if (Close[0] > orbHigh && Close[0] > vwap)
			{
				EnterLong(Contratos, "ORB_L");
				double stop = orbHigh - range * ORBStopFatorRange;
				SetStopLoss("ORB_L", CalculationMode.Price, stop, false);
				SetProfitTarget("ORB_L", CalculationMode.Price, orbHigh + range * ORBAlvoFatorRange);
				tradeNoDiaFeito = true;
			}
			// rompe p/ baixo e fecha abaixo da VWAP -> short
			else if (Close[0] < orbLow && Close[0] < vwap)
			{
				EnterShort(Contratos, "ORB_S");
				double stop = orbLow + range * ORBStopFatorRange;
				SetStopLoss("ORB_S", CalculationMode.Price, stop, false);
				SetProfitTarget("ORB_S", CalculationMode.Price, orbLow - range * ORBAlvoFatorRange);
				tradeNoDiaFeito = true;
			}
		}

		// ---------------- Estrategia 2: Mean Reversion (VWAP) ----------------
		private void EntradaMeanReversion(int agora)
		{
			if (agora < SessaoInicio || agora >= EntradaFim) return;

			double dist = MRDistVWAPTicks * TickSize;

			// preco muito ABAixo da VWAP -> compra (volta p/ media)
			if (Close[0] < vwap - dist)
			{
				EnterLong(Contratos, "MR_L");
				SetStopLoss("MR_L", CalculationMode.Ticks, MRStopTicks, false);
				SetProfitTarget("MR_L", CalculationMode.Ticks, MRAlvoTicks);
			}
			// preco muito ACIma da VWAP -> vende
			else if (Close[0] > vwap + dist)
			{
				EnterShort(Contratos, "MR_S");
				SetStopLoss("MR_S", CalculationMode.Ticks, MRStopTicks, false);
				SetProfitTarget("MR_S", CalculationMode.Ticks, MRAlvoTicks);
			}
		}

		// ---------------- Estrategia 3: Niveis (high/low dia anterior) ----------------
		private void EntradaNiveis(int agora)
		{
			if (agora < SessaoInicio || agora >= EntradaFim) return;
			if (pdHigh <= 0 || pdLow <= 0) return;

			double tol = 6 * TickSize;   // tolerancia de toque na zona

			// rejeicao no high do dia anterior -> short
			if (High[0] >= pdHigh - tol && Close[0] < pdHigh)
			{
				EnterShort(Contratos, "NIV_S");
				SetStopLoss("NIV_S", CalculationMode.Ticks, NivStopTicks, false);
				SetProfitTarget("NIV_S", CalculationMode.Ticks, NivAlvoTicks);
			}
			// rejeicao no low do dia anterior -> long
			else if (Low[0] <= pdLow + tol && Close[0] > pdLow)
			{
				EnterLong(Contratos, "NIV_L");
				SetStopLoss("NIV_L", CalculationMode.Ticks, NivStopTicks, false);
				SetProfitTarget("NIV_L", CalculationMode.Ticks, NivAlvoTicks);
			}
		}

		// ---------------- Simulador de avaliacao Apex ----------------
		private void AtualizaApexSim()
		{
			if (!avaliacaoAtiva) return;

			double realizadoTotal = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
			double pnlRealizado   = realizadoTotal - realizadoNoInicio;

			// Pior caso intraday usando High/Low da barra (sem precisar de tick):
			//  - equityFav  = extremo FAVORAVEL  -> sobe o pico do trailing (mais exigente)
			//  - equityAdv  = extremo ADVERSO    -> testa a quebra do DD (nao subestima reprovacao)
			double unrealFav = 0, unrealAdv = 0;
			if (Position.MarketPosition == MarketPosition.Long)
			{
				unrealFav = Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, High[0]);
				unrealAdv = Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, Low[0]);
			}
			else if (Position.MarketPosition == MarketPosition.Short)
			{
				unrealFav = Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, Low[0]);
				unrealAdv = Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, High[0]);
			}
			double equityFav = pnlRealizado + unrealFav;
			double equityAdv = pnlRealizado + unrealAdv;

			// trailing DD
			if (ModoIntradayDD)
			{
				// intraday: pico sobe com o melhor lucro NAO realizado da barra (pior caso, mais fiel)
				if (equityFav > picoEquity) picoEquity = equityFav;
			}
			else
			{
				// EOD: pico so sobe com o realizado
				if (pnlRealizado > picoEquity) picoEquity = pnlRealizado;
			}
			nivelDD = picoEquity - limiteDD;

			// equity usado p/ testar a quebra: pior caso intraday (ou so realizado no modo EOD)
			double equityCheck = ModoIntradayDD ? equityAdv : pnlRealizado;

			// conta dia operado (se tem posicao ou ja realizou trade hoje)
			if (Position.MarketPosition != MarketPosition.Flat)
				diasOperados.Add(Time[0].ToString("yyyy-MM-dd"));

			// kill switch diario (pior caso)
			double pnlDia = realizadoTotal - pnlInicioDia + unrealAdv;
			if (pnlDia <= -(limiteDD * KillSwitchFracaoDD))
			{
				bloqueadoHoje = true;
				if (Position.MarketPosition != MarketPosition.Flat)
					CerrarTudo("KillSwitch");
			}

			// ----- Checa REPROVACAO (estourou trailing DD) -----
			if (equityCheck <= nivelDD)
			{
				if (Position.MarketPosition != MarketPosition.Flat)
					CerrarTudo("DD_Estourado");
				avaliacoesTotais++;
				reprovadas++;
				avaliacaoAtiva = false;
				ResetAvaliacao(Time[0]);
				return;
			}

			// ----- Checa APROVACAO (meta + minimo 7 dias, so com realizado) -----
			if (pnlRealizado >= metaLucro && diasOperados.Count >= 7)
			{
				if (Position.MarketPosition != MarketPosition.Flat)
					CerrarTudo("MetaAtingida");
				avaliacoesTotais++;
				aprovadas++;
				diasParaAprovar.Add((int)(Time[0] - inicioAvaliacao).TotalDays);
				avaliacaoAtiva = false;
				ResetAvaliacao(Time[0]);
			}
		}

		private void CerrarTudo(string motivo)
		{
			if (Position.MarketPosition == MarketPosition.Long)  ExitLong();
			if (Position.MarketPosition == MarketPosition.Short) ExitShort();
		}

		private void ImprimeResumo()
		{
			double taxa = avaliacoesTotais > 0 ? 100.0 * aprovadas / avaliacoesTotais : 0;
			double mediaDias = diasParaAprovar.Count > 0 ? diasParaAprovar.Average() : 0;

			Print("==================================================================");
			Print("  RESUMO APEX APPROVAL SIM");
			Print("------------------------------------------------------------------");
			Print(string.Format("  Modo .................. {0}", Modo));
			Print(string.Format("  Conta ................. {0} (meta ${1:N0} / DD ${2:N0})", Conta, metaLucro, limiteDD));
			Print(string.Format("  Contratos ............. {0}", Contratos));
			Print(string.Format("  Trailing DD ........... {0}", ModoIntradayDD ? "INTRADAY (pior caso)" : "EOD"));
			Print("------------------------------------------------------------------");
			Print(string.Format("  Avaliacoes totais ..... {0}", avaliacoesTotais));
			Print(string.Format("  APROVADAS ............. {0}", aprovadas));
			Print(string.Format("  REPROVADAS ............ {0}", reprovadas));
			Print(string.Format("  Taxa de aprovacao ..... {0:N1}%", taxa));
			Print(string.Format("  Dias medios p/ aprovar  {0:N1}", mediaDias));
			Print("==================================================================");
		}

		#region Properties
		[NinjaScriptProperty]
		[Display(Name="Modo", Description="Estrategia testada", Order=1, GroupName="1. Estrategia")]
		public ModoEstrategia Modo { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Conta", Description="Tamanho da conta Apex (define meta e DD)", Order=2, GroupName="1. Estrategia")]
		public TamanhoConta Conta { get; set; }

		[NinjaScriptProperty]
		[Range(1, 20)]
		[Display(Name="Contratos", Order=3, GroupName="1. Estrategia")]
		public int Contratos { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Trailing DD Intraday", Description="true=intraday (fiel/pior caso) | false=EOD", Order=4, GroupName="1. Estrategia")]
		public bool ModoIntradayDD { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Sessao Inicio (HHmm ET)", Order=10, GroupName="2. Horarios")]
		public int SessaoInicio { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="ORB Fim (HHmm ET)", Order=11, GroupName="2. Horarios")]
		public int ORBFim { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Entrada Fim (HHmm ET)", Order=12, GroupName="2. Horarios")]
		public int EntradaFim { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Flatten Hora (HHmm ET)", Order=13, GroupName="2. Horarios")]
		public int FlattenHora { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 2.0)]
		[Display(Name="ORB Stop (fator range)", Order=20, GroupName="3. ORB")]
		public double ORBStopFatorRange { get; set; }

		[NinjaScriptProperty]
		[Range(0.5, 5.0)]
		[Display(Name="ORB Alvo (fator range)", Order=21, GroupName="3. ORB")]
		public double ORBAlvoFatorRange { get; set; }

		[NinjaScriptProperty]
		[Range(5, 200)]
		[Display(Name="MR Dist VWAP (ticks)", Order=30, GroupName="4. MeanReversion")]
		public int MRDistVWAPTicks { get; set; }

		[NinjaScriptProperty]
		[Range(5, 200)]
		[Display(Name="MR Stop (ticks)", Order=31, GroupName="4. MeanReversion")]
		public int MRStopTicks { get; set; }

		[NinjaScriptProperty]
		[Range(5, 200)]
		[Display(Name="MR Alvo (ticks)", Order=32, GroupName="4. MeanReversion")]
		public int MRAlvoTicks { get; set; }

		[NinjaScriptProperty]
		[Range(5, 200)]
		[Display(Name="Niveis Stop (ticks)", Order=40, GroupName="5. Niveis")]
		public int NivStopTicks { get; set; }

		[NinjaScriptProperty]
		[Range(5, 200)]
		[Display(Name="Niveis Alvo (ticks)", Order=41, GroupName="5. Niveis")]
		public int NivAlvoTicks { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 1.0)]
		[Display(Name="Kill Switch (fracao DD)", Order=50, GroupName="6. Risco")]
		public double KillSwitchFracaoDD { get; set; }

		[NinjaScriptProperty]
		[Range(0, 10)]
		[Display(Name="Comissao/contrato/lado ($)", Order=51, GroupName="6. Risco")]
		public double ComissaoPorContrato { get; set; }
		#endregion
	}
}
