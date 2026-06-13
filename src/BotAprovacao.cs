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
#endregion

// =============================================================================
//  BotAprovacao  —  Bot de APROVACAO de conta Apex (config "94 em 15 dias")
// -----------------------------------------------------------------------------
//  Estrategia: reversao na maxima/minima do dia anterior ("Niveis 94").
//  Config 5 MNQ: TP 60 | SL 12,5 | BE +3,75->+2,5 | trail 1,75 | tol 20 ticks.
//
//  GESTAO DE SAIDA (importante):
//    - Stop inicial (12,5pt) e Alvo (60pt) = ordens FIXAS no servidor (validas,
//      protegem intrabar).
//    - Breakeven + trailing = gerenciados NO CODIGO (igual ao backtest): quando
//      a barra atinge o nivel do trailing, fecha a posicao a mercado. NAO move
//      ordens no servidor -> evita os erros "alterar ordem"/"stop abaixo do
//      mercado"/"OCO reutilizado" que o trailing apertado (1,75pt) causava.
//    - Cada trade usa um nome de sinal UNICO (evita colisao de OCO em reentradas).
//
//  Calculate = OnBarClose (igual ao backtest). FORWARD TEST no Sim101/Replay
//  antes da conta real. MNQ: $2/ponto; 5 contratos = $10/ponto.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class BotAprovacao : Strategy
	{
		// ---------- Niveis do dia anterior (gatilho de entrada) ----------
		private double pdHigh = 0, pdLow = 0;
		private double curHigh = 0, curLow = 0;
		private string diaNiveis = "";

		// ---------- Gestao da posicao aberta ----------
		private double entryPrice = 0;
		private double stopPrice  = 0;    // nivel do trailing (sintetico; sobe/desce no codigo)
		private double favPrice   = 0;
		private bool   beFeito    = false;
		private bool   gerenciando = false;
		private string sinalAtivo = "";
		private int    tradeSeq   = 0;    // contador p/ nome de sinal unico por trade

		// ---------- Kill switch / controle diario ----------
		private string diaCorrente = "";
		private double pnlInicioDia = 0;
		private bool   bloqueadoHoje = false;

		// ---------- Controle de meta (opcional) ----------
		private HashSet<string> diasOperados = new HashSet<string>();
		private bool aprovado = false;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description					= @"Bot de aprovacao Apex (Niveis 94): reversao na max/min do dia anterior. 5 MNQ, tol 20 ticks. Trailing gerenciado no codigo.";
				Name						= "BotAprovacao";
				Calculate					= Calculate.OnBarClose;
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
				RealtimeErrorHandling		= RealtimeErrorHandling.IgnoreAllErrors;  // rede de seguranca: erro de ordem nao desabilita a estrategia
				StopTargetHandling			= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade			= 20;
				IsInstantiatedOnEachOptimizationIteration = true;

				Contratos			= 5;

				AlvoPontos			= 60.0;
				StopPontos			= 12.5;
				BreakevenTrigPontos	= 3.75;
				BreakevenLockPontos	= 2.5;
				TrailingPontos		= 1.75;
				TolToqueTicks		= 20;     // 20 ticks = 5pt (otimizado 13/06)

				StopDiarioDolar		= 750.0;
				MaxTradesDia		= 0;

				SessaoInicio		= 930;
				EntradaFim			= 1500;
				FlattenHora			= 1555;

				PararAoAprovar		= true;
				MetaLucroDolar		= 1500.0;
				MinDiasOperados		= 7;

				DesenharNiveis		= true;
			}
			else if (State == State.Configure)
			{
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBars[0] < BarsRequiredToTrade)
				return;

			int agora = ToTime(Time[0]) / 100;
			string hoje = Time[0].ToString("yyyy-MM-dd");

			if (hoje != diaCorrente)
			{
				diaCorrente   = hoje;
				bloqueadoHoje = false;
				pnlInicioDia  = RealizadoAcumulado();
			}

			bool emSessao = agora >= SessaoInicio && agora < 1600;
			if (hoje != diaNiveis)
			{
				if (curHigh > 0) { pdHigh = curHigh; pdLow = curLow; }
				diaNiveis = hoje;
				curHigh = emSessao ? High[0] : 0;
				curLow  = emSessao ? Low[0]  : 0;
			}
			else if (emSessao)
			{
				curHigh = curHigh == 0 ? High[0] : Math.Max(curHigh, High[0]);
				curLow  = curLow  == 0 ? Low[0]  : Math.Min(curLow,  Low[0]);
			}

			DesenhaNiveis(hoje);

			// ---------------- Gestao da posicao aberta ----------------
			if (Position.MarketPosition != MarketPosition.Flat)
			{
				diasOperados.Add(hoje);
				GerenciaPosicao();
				if (Position.MarketPosition == MarketPosition.Flat) return;   // saiu pelo trailing nesta barra
			}
			else if (gerenciando)
			{
				gerenciando = false;
				sinalAtivo  = "";
			}

			// ---------------- Kill switch diario ----------------
			double pnlDia = RealizadoAcumulado() - pnlInicioDia + UnrealizadoPiorCaso();
			if (StopDiarioDolar > 0 && pnlDia <= -StopDiarioDolar)
			{
				bloqueadoHoje = true;
				if (Position.MarketPosition != MarketPosition.Flat)
					FechaPosicao("StopDiario");
			}

			// ---------------- Meta de aprovacao ----------------
			if (PararAoAprovar && !aprovado)
			{
				if (RealizadoAcumulado() >= MetaLucroDolar && diasOperados.Count >= MinDiasOperados)
				{
					aprovado = true;
					if (Position.MarketPosition != MarketPosition.Flat)
						FechaPosicao("MetaAtingida");
					Print(string.Format("[BotAprovacao] META ATINGIDA em {0} | realizado ${1:N2} | {2} dias operados — PARANDO de operar.",
						hoje, RealizadoAcumulado(), diasOperados.Count));
				}
			}

			// ---------------- Flatten no fim do dia ----------------
			if (agora >= FlattenHora)
			{
				if (Position.MarketPosition != MarketPosition.Flat)
					FechaPosicao("FlattenEOD");
				return;
			}

			// ---------------- Entrada ----------------
			if (aprovado || bloqueadoHoje) return;
			if (Position.MarketPosition != MarketPosition.Flat) return;
			if (MaxTradesDia > 0 && TradesHoje() >= MaxTradesDia) return;

			EntradaNiveis(agora);
		}

		private void EntradaNiveis(int agora)
		{
			if (agora < SessaoInicio || agora >= EntradaFim) return;
			if (pdHigh <= 0 || pdLow <= 0) return;

			double tol = TolToqueTicks * TickSize;
			double h = High[0], l = Low[0], c = Close[0];

			// ----- tocou a zona da MAXIMA do dia anterior? (setup de SHORT) -----
			if (h >= pdHigh - tol)
			{
				if (c < pdHigh)
				{
					tradeSeq++;
					sinalAtivo = "NIV_S" + tradeSeq;   // nome unico por trade (evita colisao de OCO)
					// stop e alvo definidos ANTES da entrada (em ticks): o NT8 cria as ordens
					// atreladas ao fill, no preco correto, protegendo intrabar desde o 1o tick
					SetStopLoss(sinalAtivo, CalculationMode.Ticks, StopPontos / TickSize, false);
					SetProfitTarget(sinalAtivo, CalculationMode.Ticks, AlvoPontos / TickSize);
					EnterShort(Contratos, sinalAtivo);
					Print(string.Format("{0}  >>> SHORT @ {1:F2}  | tocou Max {2:F2} (H={3:F2}) e FECHOU ABAIXO (C={4:F2})",
						Time[0], c, pdHigh, h, c));
				}
				else
				{
					Print(string.Format("{0}  toque no Max {1:F2} SEM rejeicao (H={2:F2}, C={3:F2} >= linha) -> nao entrou",
						Time[0], pdHigh, h, c));
				}
				return;
			}

			// ----- tocou a zona da MINIMA do dia anterior? (setup de LONG) -----
			if (l <= pdLow + tol)
			{
				if (c > pdLow)
				{
					tradeSeq++;
					sinalAtivo = "NIV_L" + tradeSeq;
					SetStopLoss(sinalAtivo, CalculationMode.Ticks, StopPontos / TickSize, false);
					SetProfitTarget(sinalAtivo, CalculationMode.Ticks, AlvoPontos / TickSize);
					EnterLong(Contratos, sinalAtivo);
					Print(string.Format("{0}  >>> LONG @ {1:F2}  | tocou Min {2:F2} (L={3:F2}) e FECHOU ACIMA (C={4:F2})",
						Time[0], c, pdLow, l, c));
				}
				else
				{
					Print(string.Format("{0}  toque no Min {1:F2} SEM reacao (L={2:F2}, C={3:F2} <= linha) -> nao entrou",
						Time[0], pdLow, l, c));
				}
			}
		}

		// ---------------- Gestao de stop/alvo/breakeven/trailing ----------------
		// Stop inicial + alvo = ordens fixas no servidor. Breakeven/trailing = sintetico
		// (fecha a mercado quando a barra atinge o nivel), igual a logica do backtest.
		private void GerenciaPosicao()
		{
			bool isLong = Position.MarketPosition == MarketPosition.Long;

			// 1a barra na posicao: registra entrada e inicializa o trailing
			// (stop inicial e alvo ja foram criados NA ENTRADA, em ticks atrelados ao fill)
			if (!gerenciando)
			{
				entryPrice = Position.AveragePrice;
				favPrice   = entryPrice;
				beFeito    = false;
				stopPrice  = isLong ? entryPrice - StopPontos : entryPrice + StopPontos;
				gerenciando = true;
				// stop inicial e alvo ja foram criados NA ENTRADA (em ticks, atrelados ao fill)
				return;
			}

			// 2. Trailing SINTETICO: checa se a barra ATUAL atingiu o nivel de trailing
			//    definido na barra anterior (so apos o breakeven). Fecha a mercado.
			if (beFeito)
			{
				if (isLong  && Low[0]  <= stopPrice) { FechaPosicao("Trailing"); return; }
				if (!isLong && High[0] >= stopPrice) { FechaPosicao("Trailing"); return; }
			}

			// 3. Atualiza o favoravel e recalcula o nivel de trailing (vale a partir da proxima barra)
			if (isLong)
			{
				favPrice = Math.Max(favPrice, High[0]);
				if (!beFeito && (favPrice - entryPrice) >= BreakevenTrigPontos)
					beFeito = true;
				if (beFeito)
					stopPrice = Math.Max(stopPrice, Math.Max(entryPrice + BreakevenLockPontos, favPrice - TrailingPontos));
			}
			else
			{
				favPrice = Math.Min(favPrice, Low[0]);
				if (!beFeito && (entryPrice - favPrice) >= BreakevenTrigPontos)
					beFeito = true;
				if (beFeito)
					stopPrice = Math.Min(stopPrice, Math.Min(entryPrice - BreakevenLockPontos, favPrice + TrailingPontos));
			}
		}

		// ---------------- Desenho das linhas de max/min do dia anterior ----------------
		private void DesenhaNiveis(string hoje)
		{
			if (!DesenharNiveis) return;

			Draw.TextFixed(this, "statusNiveis",
				"Niveis dia anterior:\n" +
				"  Max (short): " + (pdHigh > 0 ? pdHigh.ToString("F2") : "(aguardando 1o dia)") + "\n" +
				"  Min (long):  " + (pdLow  > 0 ? pdLow.ToString("F2")  : "(aguardando 1o dia)"),
				TextPosition.TopRight);

			if (pdHigh <= 0 || pdLow <= 0) return;

			Draw.HorizontalLine(this, "PDH", pdHigh, Brushes.Red,       DashStyleHelper.Dash, 2);
			Draw.HorizontalLine(this, "PDL", pdLow,  Brushes.LimeGreen, DashStyleHelper.Dash, 2);
		}

		private void FechaPosicao(string motivo)
		{
			if (Position.MarketPosition == MarketPosition.Long)  ExitLong("X_" + motivo, sinalAtivo);
			else if (Position.MarketPosition == MarketPosition.Short) ExitShort("X_" + motivo, sinalAtivo);
		}

		private double RealizadoAcumulado()
		{
			return SystemPerformance != null
				? SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit
				: 0;
		}

		private double UnrealizadoPiorCaso()
		{
			if (Position.MarketPosition == MarketPosition.Long)
				return Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, Low[0]);
			if (Position.MarketPosition == MarketPosition.Short)
				return Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, High[0]);
			return 0;
		}

		private int TradesHoje()
		{
			int n = 0;
			string hoje = Time[0].ToString("yyyy-MM-dd");
			var trades = SystemPerformance.AllTrades;
			for (int i = trades.Count - 1; i >= 0; i--)
			{
				if (trades[i].Exit.Time.ToString("yyyy-MM-dd") == hoje) n++;
				else break;
			}
			if (Position.MarketPosition != MarketPosition.Flat) n++;
			return n;
		}

		#region Properties
		[NinjaScriptProperty]
		[Range(1, 50)]
		[Display(Name="Contratos", Description="Qtd de contratos (5 = config MNQ vencedora)", Order=1, GroupName="1. Geral")]
		public int Contratos { get; set; }

		[NinjaScriptProperty]
		[Range(1, 500)]
		[Display(Name="Alvo (pontos)", Description="Take profit em pontos (60 = config vencedora)", Order=10, GroupName="2. Saida")]
		public double AlvoPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0.25, 100)]
		[Display(Name="Stop (pontos)", Description="Stop loss em pontos (12,5 = $125/trade com 5 MNQ)", Order=11, GroupName="2. Saida")]
		public double StopPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0.25, 50)]
		[Display(Name="Breakeven gatilho (pontos)", Description="Ganho que aciona o breakeven", Order=12, GroupName="2. Saida")]
		public double BreakevenTrigPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 50)]
		[Display(Name="Breakeven trava (pontos)", Description="Lucro travado ao acionar o breakeven", Order=13, GroupName="2. Saida")]
		public double BreakevenLockPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0.25, 50)]
		[Display(Name="Trailing (pontos)", Description="Distancia do trailing a partir do breakeven", Order=14, GroupName="2. Saida")]
		public double TrailingPontos { get; set; }

		[NinjaScriptProperty]
		[Range(0, 50)]
		[Display(Name="Tolerancia toque (ticks)", Description="Distancia max da linha p/ contar como toque (20 ticks=5pt, otimizado)", Order=15, GroupName="2. Saida")]
		public int TolToqueTicks { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100000)]
		[Display(Name="Stop diario ($)", Description="Para de operar no dia ao perder esse valor (0 = desliga)", Order=20, GroupName="3. Risco")]
		public double StopDiarioDolar { get; set; }

		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(Name="Max trades/dia", Description="0 = sem limite (config principal); 12 = variante amarrada", Order=21, GroupName="3. Risco")]
		public int MaxTradesDia { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Sessao Inicio (HHmm ET)", Order=30, GroupName="4. Horarios")]
		public int SessaoInicio { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Entrada Fim (HHmm ET)", Order=31, GroupName="4. Horarios")]
		public int EntradaFim { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Flatten Hora (HHmm ET)", Order=32, GroupName="4. Horarios")]
		public int FlattenHora { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Parar ao aprovar", Description="Para de operar ao bater a meta + min dias", Order=40, GroupName="5. Meta")]
		public bool PararAoAprovar { get; set; }

		[NinjaScriptProperty]
		[Range(0, 1000000)]
		[Display(Name="Meta lucro ($)", Description="Meta de aprovacao da conta (25K = $1.500)", Order=41, GroupName="5. Meta")]
		public double MetaLucroDolar { get; set; }

		[NinjaScriptProperty]
		[Range(0, 60)]
		[Display(Name="Min dias operados", Description="Minimo de dias p/ aprovar (Apex = 7)", Order=42, GroupName="5. Meta")]
		public int MinDiasOperados { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Desenhar niveis", Description="Mostra as linhas de max/min do dia anterior no grafico", Order=50, GroupName="6. Visual")]
		public bool DesenharNiveis { get; set; }
		#endregion
	}
}
