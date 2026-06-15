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
//  Config 5 MNQ: TP 60 | SL 12,5 | BE +3,75->+2,5 | trail 1,75 | tol 20 ticks | maxDist 15pt.
//
//  GESTAO DE SAIDA — MODELO HIBRIDO:
//    - Stop inicial (12,5pt) = ordem no SERVIDOR (protege intrabar, sem OCO
//      pois nao usamos SetProfitTarget -> nao ha par OCO para conflitar).
//    - Quando breakeven aciona: atualiza stop servidor para nivel de lock (+2,5pt).
//      A partir dai, intrabar o servidor garante no minimo o lucro travado.
//    - Alvo (60pt), trailing (1,75pt) = SINTETICOS (fecha a mercado no bar close).
//    - Trailing nao atualiza o servidor (1,75pt e muito apertado; risco de
//      "stop abaixo do mercado" em barras rapidas). Servidor fica no breakeven.
//    - Stop sintetico existe como BACKUP do servidor (se ordem falhar).
//
//  Resultado: protecao real intrabar + sem erros de OCO em reentradas.
//  Calculate = OnBarClose. MNQ: $2/ponto; 5 contratos = $10/ponto.
//  Horarios (ET): entradas 9h30-16h00, flatten 16h55. Niveis = RTH do dia anterior.
//  SEGUNDA (15/06): usa o range do DOMINGO A NOITE (Globex 18h -> seg 9h30) como
//  nivel de rejeicao, em vez da linha de sexta. Toggle: SegUsaDomingo (default ON).
//  Backtest: +3 aprovacoes/ano (19->22), aprova mais rapido (15->13d), OOS 100%/100%.
// =============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
	public class BotAprovacao : Strategy
	{
		// ---------- Niveis do dia anterior (gatilho de entrada) ----------
		private double pdHigh = 0, pdLow = 0;
		private double curHigh = 0, curLow = 0;
		private string diaNiveis = "";

		// ---------- Range do domingo a noite (Globex) p/ usar na SEGUNDA ----------
		private double onHigh = 0, onLow = 0;   // high/low do overnight (dom 18h -> seg 9h30)
		private string onKey   = "";            // data da segunda a que esse range pertence

		// ---------- Gestao da posicao aberta ----------
		private double entryPrice = 0;
		private double stopPrice  = 0;    // stop sintetico: inicial -> trailing apos breakeven
		private double alvoPrice  = 0;    // alvo sintetico (substitui SetProfitTarget)
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
				MaxDistPontos		= 15.0;   // 15pt = sweet spot (otimizado 14/06): 100% taxa, PF 1.60, OOS 100%/100%

				StopDiarioDolar		= 750.0;
				MaxTradesDia		= 0;

				SessaoInicio		= 930;
				EntradaFim			= 1600;
				FlattenHora			= 1655;

				SegUsaDomingo		= true;   // segunda usa range do Globex (otimizado 15/06: +3 aprov/ano, aprova +rapido, OOS 100%)
				DomNoiteInicio		= 1800;   // abertura do Globex (ET)

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

			// ----- Range do domingo a noite (Globex): dom >= DomNoiteInicio  ate  seg < SessaoInicio -----
			// Acumula o high/low do overnight p/ servir de nivel de rejeicao na SEGUNDA.
			if (SegUsaDomingo)
			{
				DayOfWeek dow = Time[0].DayOfWeek;
				string chaveSeg = null;
				if (dow == DayOfWeek.Sunday && agora >= DomNoiteInicio)
					chaveSeg = Time[0].AddDays(1).ToString("yyyy-MM-dd");   // segunda seguinte
				else if (dow == DayOfWeek.Monday && agora < SessaoInicio)
					chaveSeg = hoje;
				if (chaveSeg != null)
				{
					if (chaveSeg != onKey) { onKey = chaveSeg; onHigh = High[0]; onLow = Low[0]; }
					else { onHigh = Math.Max(onHigh, High[0]); onLow = Math.Min(onLow, Low[0]); }
				}
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

		// Nivel de rejeicao ativo: na SEGUNDA usa o range do domingo a noite (Globex);
		// nos demais dias usa o RTH do dia anterior. Retorna false se nao ha nivel valido.
		private bool NivelAtivo(out double nHi, out double nLo, out bool usouDomingo)
		{
			usouDomingo = false;
			if (SegUsaDomingo && Time[0].DayOfWeek == DayOfWeek.Monday
				&& onKey == Time[0].ToString("yyyy-MM-dd") && onHigh > 0)
			{
				nHi = onHigh; nLo = onLow; usouDomingo = true;
				return true;
			}
			nHi = pdHigh; nLo = pdLow;
			return (nHi > 0 && nLo > 0);
		}

		private void EntradaNiveis(int agora)
		{
			if (agora < SessaoInicio || agora >= EntradaFim) return;

			double nHi, nLo; bool dom;
			if (!NivelAtivo(out nHi, out nLo, out dom)) return;
			string src = dom ? "(domingo)" : "";

			double tol = TolToqueTicks * TickSize;
			double h = High[0], l = Low[0], c = Close[0];

			// ----- tocou a zona da MAXIMA de referencia? (setup de SHORT) -----
			if (h >= nHi - tol)
			{
				if (c < nHi)
				{
					double distPontos = nHi - c;
					if (MaxDistPontos > 0 && distPontos > MaxDistPontos)
					{
						Print(string.Format("{0}  toque no Max {1:F2} {6} CHASE ignorado (close {2:F2}pt abaixo da linha, max permitido {3:F2}pt)",
							Time[0], nHi, distPontos, MaxDistPontos, h, c, src));
						return;
					}
					tradeSeq++;
					sinalAtivo = "NIV_S" + tradeSeq;
					// Stop no servidor (protege intrabar) — sem SetProfitTarget = sem OCO
					SetStopLoss(sinalAtivo, CalculationMode.Ticks, StopPontos / TickSize, false);
					EnterShort(Contratos, sinalAtivo);
					Print(string.Format("{0}  >>> SHORT @ {1:F2}  | tocou Max {2:F2} {6} (H={3:F2}, dist {4:F2}pt) e FECHOU ABAIXO (C={5:F2})",
						Time[0], c, nHi, h, distPontos, c, src));
				}
				else if (h <= nHi + tol * 2)  // silencia spam quando mercado opera longe acima da linha
				{
					Print(string.Format("{0}  toque no Max {1:F2} {4} SEM rejeicao (H={2:F2}, C={3:F2} >= linha) -> nao entrou",
						Time[0], nHi, h, c, src));
				}
				return;
			}

			// ----- tocou a zona da MINIMA de referencia? (setup de LONG) -----
			if (l <= nLo + tol)
			{
				if (c > nLo)
				{
					double distPontos = c - nLo;
					if (MaxDistPontos > 0 && distPontos > MaxDistPontos)
					{
						Print(string.Format("{0}  toque no Min {1:F2} {4} CHASE ignorado (close {2:F2}pt acima da linha, max permitido {3:F2}pt)",
							Time[0], nLo, distPontos, MaxDistPontos, src));
						return;
					}
					tradeSeq++;
					sinalAtivo = "NIV_L" + tradeSeq;
					// Stop no servidor (protege intrabar) — sem SetProfitTarget = sem OCO
					SetStopLoss(sinalAtivo, CalculationMode.Ticks, StopPontos / TickSize, false);
					EnterLong(Contratos, sinalAtivo);
					Print(string.Format("{0}  >>> LONG @ {1:F2}  | tocou Min {2:F2} {6} (L={3:F2}, dist {4:F2}pt) e FECHOU ACIMA (C={5:F2})",
						Time[0], c, nLo, l, distPontos, c, src));
				}
				else if (l >= nLo - tol * 2)  // silencia spam quando mercado opera longe abaixo da linha
				{
					Print(string.Format("{0}  toque no Min {1:F2} {4} SEM reacao (L={2:F2}, C={3:F2} <= linha) -> nao entrou",
						Time[0], nLo, l, c, src));
				}
			}
		}

		// ---------------- Gestao de stop/alvo/breakeven/trailing — 100% SINTETICO ----------------
		// Tudo gerenciado no codigo (igual ao backtest Python): fecha a mercado quando a barra
		// fecha alem do nivel. Sem SetStopLoss/SetProfitTarget -> sem OCO -> sem conflito em reentradas.
		private void GerenciaPosicao()
		{
			bool isLong = Position.MarketPosition == MarketPosition.Long;

			// 1a barra na posicao: registra entrada, inicializa stop e alvo sinteticos
			if (!gerenciando)
			{
				entryPrice = Position.AveragePrice;
				favPrice   = entryPrice;
				beFeito    = false;
				stopPrice  = isLong ? entryPrice - StopPontos : entryPrice + StopPontos;
				alvoPrice  = isLong ? entryPrice + AlvoPontos : entryPrice - AlvoPontos;
				gerenciando = true;
				return;
			}

			// Alvo sintetico
			if (isLong  && High[0] >= alvoPrice) { FechaPosicao("Alvo"); return; }
			if (!isLong && Low[0]  <= alvoPrice) { FechaPosicao("Alvo"); return; }

			// Stop sintetico (inicial antes do breakeven, trailing depois)
			if (isLong  && Low[0]  <= stopPrice) { FechaPosicao(beFeito ? "Trailing" : "StopInicial"); return; }
			if (!isLong && High[0] >= stopPrice) { FechaPosicao(beFeito ? "Trailing" : "StopInicial"); return; }

			// Atualiza o nivel de trailing (vale a partir da proxima barra)
			if (isLong)
			{
				favPrice = Math.Max(favPrice, High[0]);
				if (!beFeito && (favPrice - entryPrice) >= BreakevenTrigPontos)
				{
					beFeito = true;
					// Move stop servidor para nivel de breakeven — garante lucro minimo intrabar
					SetStopLoss(sinalAtivo, CalculationMode.Price, entryPrice + BreakevenLockPontos, false);
				}
				if (beFeito)
					stopPrice = Math.Max(stopPrice, Math.Max(entryPrice + BreakevenLockPontos, favPrice - TrailingPontos));
			}
			else
			{
				favPrice = Math.Min(favPrice, Low[0]);
				if (!beFeito && (entryPrice - favPrice) >= BreakevenTrigPontos)
				{
					beFeito = true;
					// Move stop servidor para nivel de breakeven — garante lucro minimo intrabar
					SetStopLoss(sinalAtivo, CalculationMode.Price, entryPrice - BreakevenLockPontos, false);
				}
				if (beFeito)
					stopPrice = Math.Min(stopPrice, Math.Min(entryPrice - BreakevenLockPontos, favPrice + TrailingPontos));
			}
		}

		// ---------------- Desenho das linhas de max/min do dia anterior ----------------
		private void DesenhaNiveis(string hoje)
		{
			if (!DesenharNiveis) return;

			double nHi, nLo; bool dom;
			NivelAtivo(out nHi, out nLo, out dom);
			string titulo = dom ? "Niveis DOMINGO a noite (Globex):" : "Niveis dia anterior:";

			Draw.TextFixed(this, "statusNiveis",
				titulo + "\n" +
				"  Max (short): " + (nHi > 0 ? nHi.ToString("F2") : "(aguardando 1o dia)") + "\n" +
				"  Min (long):  " + (nLo > 0 ? nLo.ToString("F2") : "(aguardando 1o dia)"),
				TextPosition.TopRight);

			if (nHi <= 0 || nLo <= 0) return;

			Draw.HorizontalLine(this, "PDH", nHi, Brushes.Red,       DashStyleHelper.Dash, 2);
			Draw.HorizontalLine(this, "PDL", nLo, Brushes.LimeGreen, DashStyleHelper.Dash, 2);
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
		[Range(0, 200)]
		[Display(Name="Max dist. entrada (pontos)", Description="Close deve estar a no max X pontos da linha (0=sem filtro, 15=recomendado). Filtra entradas chase.", Order=16, GroupName="2. Saida")]
		public double MaxDistPontos { get; set; }

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
		[Display(Name="Segunda usa range domingo-noite", Description="Na SEGUNDA usa o high/low do Globex (dom 18h -> seg 9h30) em vez da linha de sexta. Otimizado 15/06: +3 aprov/ano, aprova +rapido, OOS 100%.", Order=33, GroupName="4. Horarios")]
		public bool SegUsaDomingo { get; set; }

		[NinjaScriptProperty]
		[Range(0, 2359)]
		[Display(Name="Domingo noite inicio (HHmm ET)", Description="Inicio do range do domingo a noite (1800 = abertura do Globex)", Order=34, GroupName="4. Horarios")]
		public int DomNoiteInicio { get; set; }

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
