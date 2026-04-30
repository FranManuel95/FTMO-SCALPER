//+------------------------------------------------------------------+
//|                                              FTMO_Pullback.mq5  |
//|                            EMA20 pullback signal viewer (MT5)   |
//|                                                                  |
//| Visualiza la familia de estrategias Trend Pullback del bot.     |
//| Reglas idénticas a src/signals/pullback/trend_pullback.py.       |
//|                                                                  |
//| LONG:                                                            |
//|   - close > EMA50 AND EMA20 > EMA50    (estructura alcista)     |
//|   - close prev < EMA20 prev AND close > EMA20  (rebote sobre EMA20)
//|   - ADX > AdxMin                                                 |
//|   - RSI < RsiOverbought                                          |
//|   - H4 trend bullish (EMA50_H4 > EMA200_H4) si UseH4Filter      |
//|   - Hora broker dentro de sesión                                 |
//|                                                                  |
//| SL = entry - 1.5×ATR ; TP = entry + 2.5 × (entry - SL)          |
//+------------------------------------------------------------------+
#property copyright "FTMO-Scalper"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots   4

#property indicator_label1  "Long"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLimeGreen
#property indicator_width1  2
#property indicator_style1  STYLE_SOLID

#property indicator_label2  "Short"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrCrimson
#property indicator_width2  2
#property indicator_style2  STYLE_SOLID

#property indicator_label3  "EMA20"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrDodgerBlue
#property indicator_width3  1

#property indicator_label4  "EMA50"
#property indicator_type4   DRAW_LINE
#property indicator_color4  clrOrange
#property indicator_width4  1

//─── Inputs ───
input group "Filtros de señal"
input int    EmaFast        = 20;
input int    EmaSlow        = 50;
input int    AdxPeriod      = 14;
input double AdxMin         = 25.0;     // 25 XAUUSD/GBPUSD/AUDUSD, 20 USDJPY
input int    RsiPeriod      = 14;
input double RsiOverbought  = 60.0;
input double RsiOversold    = 40.0;
input bool   LongOnly       = false;    // true para AUDUSD

input group "Niveles"
input double AtrSlMult      = 1.5;
input double RrTarget       = 2.5;

input group "Filtro H4"
input bool   UseH4Filter    = true;
input int    H4EmaFast      = 50;
input int    H4EmaSlow      = 200;

input group "Sesión (UTC, offset broker auto)"
input int    SessionStartUTC = 7;       // broker = +2 = 9
input int    SessionEndUTC   = 21;      // broker = +2 = 23
input int    BrokerOffsetH   = 2;       // FTMO-Demo es UTC+2

input group "Visualización"
input bool   ShowOnlyFirst  = true;     // solo primera señal del día
input bool   ShowSlTp       = true;     // SL/TP de la última señal
input color  SlColor        = clrCrimson;
input color  TpColor        = clrLimeGreen;

//─── Buffers ───
double LongBuf[], ShortBuf[], Ema20Buf[], Ema50Buf[];

//─── Handles ───
int hEma20, hEma50, hAdx, hAtr, hRsi;
int hEma50_H4 = INVALID_HANDLE;
int hEma200_H4 = INVALID_HANDLE;

//─── State ───
string g_status_objs[6] = {
   "FTMO_PB_TITLE",
   "FTMO_PB_BIAS",
   "FTMO_PB_H4",
   "FTMO_PB_ADX",
   "FTMO_PB_RSI",
   "FTMO_PB_PB"
};

string g_lastSL = "FTMO_PB_LAST_SL";
string g_lastTP = "FTMO_PB_LAST_TP";

//+------------------------------------------------------------------+
int OnInit() {
   SetIndexBuffer(0, LongBuf,  INDICATOR_DATA);
   SetIndexBuffer(1, ShortBuf, INDICATOR_DATA);
   SetIndexBuffer(2, Ema20Buf, INDICATOR_DATA);
   SetIndexBuffer(3, Ema50Buf, INDICATOR_DATA);

   PlotIndexSetInteger(0, PLOT_ARROW, 233);  // ▲
   PlotIndexSetInteger(1, PLOT_ARROW, 234);  // ▼
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   ArraySetAsSeries(LongBuf,  false);
   ArraySetAsSeries(ShortBuf, false);
   ArraySetAsSeries(Ema20Buf, false);
   ArraySetAsSeries(Ema50Buf, false);

   hEma20 = iMA(_Symbol, _Period, EmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hEma50 = iMA(_Symbol, _Period, EmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hAdx   = iADX(_Symbol, _Period, AdxPeriod);
   hAtr   = iATR(_Symbol, _Period, AdxPeriod);
   hRsi   = iRSI(_Symbol, _Period, RsiPeriod, PRICE_CLOSE);

   if(UseH4Filter) {
      hEma50_H4  = iMA(_Symbol, PERIOD_H4, H4EmaFast, 0, MODE_EMA, PRICE_CLOSE);
      hEma200_H4 = iMA(_Symbol, PERIOD_H4, H4EmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   }

   if(hEma20==INVALID_HANDLE || hEma50==INVALID_HANDLE || hAdx==INVALID_HANDLE
      || hAtr==INVALID_HANDLE || hRsi==INVALID_HANDLE) return INIT_FAILED;
   if(UseH4Filter && (hEma50_H4==INVALID_HANDLE || hEma200_H4==INVALID_HANDLE))
      return INIT_FAILED;

   IndicatorSetString(INDICATOR_SHORTNAME, "FTMO Pullback");
   CreateStatusPanel();
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   Comment("");
   for(int i=0; i<ArraySize(g_status_objs); i++)
      ObjectDelete(0, g_status_objs[i]);
   ObjectDelete(0, g_lastSL);
   ObjectDelete(0, g_lastTP);
}

//+------------------------------------------------------------------+
void CreateStatusPanel() {
   for(int i=0; i<ArraySize(g_status_objs); i++) {
      string n = g_status_objs[i];
      if(ObjectFind(0,n) < 0) ObjectCreate(0, n, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, n, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, n, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, n, OBJPROP_YDISTANCE, 20 + i*16);
      ObjectSetInteger(0, n, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, n, OBJPROP_COLOR, clrWhite);
      ObjectSetInteger(0, n, OBJPROP_BACK, false);
      ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   }
   ObjectSetString(0, g_status_objs[0], OBJPROP_TEXT, "FTMO Pullback");
   ObjectSetInteger(0, g_status_objs[0], OBJPROP_FONTSIZE, 10);
   // Inicializar el resto con placeholders para detectar si la actualización falla
   ObjectSetString(0, g_status_objs[1], OBJPROP_TEXT, "Bias: …");
   ObjectSetString(0, g_status_objs[2], OBJPROP_TEXT, "H4: …");
   ObjectSetString(0, g_status_objs[3], OBJPROP_TEXT, "ADX: …");
   ObjectSetString(0, g_status_objs[4], OBJPROP_TEXT, "RSI: …");
   ObjectSetString(0, g_status_objs[5], OBJPROP_TEXT, "EMAs: …");
}

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[]) {

   int needed = MathMax(EmaSlow, AdxPeriod*3) + 5;
   if(rates_total < needed) {
      Comment(StringFormat("FTMO_Pullback: warmup (rates=%d, needed=%d)", rates_total, needed));
      return 0;
   }

   // Solo procesamos los últimos N bars donde TODOS los indicadores están calculados.
   // BarsCalculated() del handle más restrictivo (EMA200 H4) determina el rango válido.
   int bc_e20 = BarsCalculated(hEma20);
   int bc_e50 = BarsCalculated(hEma50);
   int bc_adx = BarsCalculated(hAdx);
   int bc_atr = BarsCalculated(hAtr);
   int bc_rsi = BarsCalculated(hRsi);
   int bc_min = MathMin(MathMin(MathMin(bc_e20, bc_e50), MathMin(bc_adx, bc_atr)), bc_rsi);

   bool use_h4 = UseH4Filter;
   if(use_h4) {
      int bc_h4f = BarsCalculated(hEma50_H4);
      int bc_h4s = BarsCalculated(hEma200_H4);
      if(bc_h4f <= 0 || bc_h4s <= 0) use_h4 = false;
      else bc_min = MathMin(bc_min, MathMin(bc_h4f, bc_h4s));
   }

   if(bc_min <= needed) {
      Comment(StringFormat("FTMO_Pullback: data not ready (bars_calculated=%d, needed=%d)",
                           bc_min, needed));
      return prev_calculated;
   }

   // Limitamos a los últimos N bars (con un cap de 5000 para no procesar décadas)
   int n_use = MathMin(MathMin(rates_total, bc_min), 5000);
   int chart_start = rates_total - n_use;   // primer bar del chart que vamos a tocar

   double ema20[], ema50[], adx[], atr[], rsi[], h4f[], h4s[];
   ArraySetAsSeries(ema20, false);
   ArraySetAsSeries(ema50, false);
   ArraySetAsSeries(adx,   false);
   ArraySetAsSeries(atr,   false);
   ArraySetAsSeries(rsi,   false);
   ArraySetAsSeries(h4f,   false);
   ArraySetAsSeries(h4s,   false);

   if(CopyBuffer(hEma20,0,0,n_use,ema20) != n_use ||
      CopyBuffer(hEma50,0,0,n_use,ema50) != n_use ||
      CopyBuffer(hAdx,  0,0,n_use,adx)   != n_use ||
      CopyBuffer(hAtr,  0,0,n_use,atr)   != n_use ||
      CopyBuffer(hRsi,  0,0,n_use,rsi)   != n_use) {
      Comment("FTMO_Pullback: CopyBuffer mismatch on primary indicators");
      return prev_calculated;
   }

   if(use_h4) {
      if(CopyBuffer(hEma50_H4, 0,0,n_use,h4f) != n_use ||
         CopyBuffer(hEma200_H4,0,0,n_use,h4s) != n_use) {
         use_h4 = false;
      }
   }

   int s_start = (SessionStartUTC + BrokerOffsetH) % 24;
   int s_end   = (SessionEndUTC + BrokerOffsetH) % 24;

   datetime last_signal_day = 0;

   // Limpiar TODOS los buffers a EMPTY_VALUE (incluyendo zonas que no procesaremos)
   for(int j = 0; j < rates_total; j++) {
      Ema20Buf[j] = EMPTY_VALUE;
      Ema50Buf[j] = EMPTY_VALUE;
      LongBuf[j]  = EMPTY_VALUE;
      ShortBuf[j] = EMPTY_VALUE;
   }

   // Iteramos sobre el rango de chart bars correspondiente a indicador disponible.
   // Mapping: chart_idx = chart_start + ind_idx; ind_idx = chart_idx - chart_start
   int chart_first = MathMax(needed + chart_start, chart_start + 2);
   for(int ci = chart_first; ci < rates_total; ci++) {
      int ii = ci - chart_start;
      if(ii < 2 || ii >= n_use) continue;

      Ema20Buf[ci] = ema20[ii];
      Ema50Buf[ci] = ema50[ii];

      // Sesión
      MqlDateTime dt;
      TimeToStruct(time[ci], dt);
      bool in_session;
      if(s_start < s_end) in_session = (dt.hour >= s_start && dt.hour < s_end);
      else                in_session = (dt.hour >= s_start || dt.hour < s_end);
      if(!in_session) continue;

      if(adx[ii] < AdxMin) continue;

      bool bullish = close[ci] > ema50[ii] && ema20[ii] > ema50[ii];
      bool bearish = close[ci] < ema50[ii] && ema20[ii] < ema50[ii];
      if(!bullish && !bearish) continue;

      if(use_h4) {
         if(bullish && h4f[ii] < h4s[ii]) continue;
         if(bearish && h4f[ii] > h4s[ii]) continue;
      }

      datetime day_start = (datetime)((long)time[ci] / 86400 * 86400);
      if(ShowOnlyFirst && day_start == last_signal_day) continue;

      double price = close[ci], prev = close[ci-1], a = atr[ii];

      if(bullish) {
         bool pullback = (prev < ema20[ii-1]) && (price > ema20[ii]);
         bool rsi_ok   = rsi[ii] < RsiOverbought;
         if(pullback && rsi_ok) {
            LongBuf[ci] = low[ci];
            last_signal_day = day_start;
            if(ShowSlTp && ci == rates_total - 1) {
               double sl = price - a * AtrSlMult;
               double tp = price + (price - sl) * RrTarget;
               DrawSlTp(time[ci], sl, tp);
            }
         }
      }
      else if(bearish && !LongOnly) {
         bool pullback = (prev > ema20[ii-1]) && (price < ema20[ii]);
         bool rsi_ok   = rsi[ii] > RsiOversold;
         if(pullback && rsi_ok) {
            ShortBuf[ci] = high[ci];
            last_signal_day = day_start;
            if(ShowSlTp && ci == rates_total - 1) {
               double sl = price + a * AtrSlMult;
               double tp = price - (sl - price) * RrTarget;
               DrawSlTp(time[ci], sl, tp);
            }
         }
      }
   }

   // ─── Status panel update — usar el último bar del chart, mapeado al último indicador ───
   int chart_last = rates_total - 1;
   int ind_last   = n_use - 1;
   if(chart_last >= 0 && ind_last >= 0) {
      double cl = close[chart_last];
      string bias = "FLAT";
      if(cl > ema50[ind_last] && ema20[ind_last] > ema50[ind_last])      bias = "BULL";
      else if(cl < ema50[ind_last] && ema20[ind_last] < ema50[ind_last]) bias = "BEAR";

      string h4txt = "H4: off";
      if(use_h4) {
         double h4f_v = h4f[ind_last], h4s_v = h4s[ind_last];
         if(h4f_v > h4s_v)      h4txt = "H4: BULL";
         else if(h4f_v < h4s_v) h4txt = "H4: BEAR";
         else                   h4txt = "H4: flat";
      }

      string adxtxt = StringFormat("ADX: %.1f (min %.0f) %s",
                                   adx[ind_last], AdxMin, (adx[ind_last] >= AdxMin ? "OK" : "X"));
      string rsitxt = StringFormat("RSI: %.1f", rsi[ind_last]);
      string pbtxt  = StringFormat("EMA20=%.5f EMA50=%.5f", ema20[ind_last], ema50[ind_last]);

      ObjectSetString(0, g_status_objs[1], OBJPROP_TEXT, "Bias: " + bias);
      ObjectSetString(0, g_status_objs[2], OBJPROP_TEXT, h4txt);
      ObjectSetString(0, g_status_objs[3], OBJPROP_TEXT, adxtxt);
      ObjectSetString(0, g_status_objs[4], OBJPROP_TEXT, rsitxt);
      ObjectSetString(0, g_status_objs[5], OBJPROP_TEXT, pbtxt);
      Comment(StringFormat("FTMO_Pullback: OK | last bar @ %s | close=%.5f",
                           TimeToString(time[chart_last]), cl));
      ChartRedraw(0);
   }

   return rates_total;
}

//+------------------------------------------------------------------+
void DrawSlTp(datetime t, double sl, double tp) {
   if(ObjectFind(0,g_lastSL)<0) ObjectCreate(0,g_lastSL,OBJ_HLINE,0,t,sl);
   else                          ObjectSetDouble(0,g_lastSL,OBJPROP_PRICE,0,sl);
   ObjectSetInteger(0,g_lastSL,OBJPROP_COLOR,SlColor);
   ObjectSetInteger(0,g_lastSL,OBJPROP_STYLE,STYLE_DASH);
   ObjectSetInteger(0,g_lastSL,OBJPROP_WIDTH,1);

   if(ObjectFind(0,g_lastTP)<0) ObjectCreate(0,g_lastTP,OBJ_HLINE,0,t,tp);
   else                          ObjectSetDouble(0,g_lastTP,OBJPROP_PRICE,0,tp);
   ObjectSetInteger(0,g_lastTP,OBJPROP_COLOR,TpColor);
   ObjectSetInteger(0,g_lastTP,OBJPROP_STYLE,STYLE_DASH);
   ObjectSetInteger(0,g_lastTP,OBJPROP_WIDTH,1);
}

//+------------------------------------------------------------------+
