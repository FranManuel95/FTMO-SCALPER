//+------------------------------------------------------------------+
//|                                                   FTMO_ORB.mq5  |
//|                        Opening Range Breakout viewer (MT5)      |
//|                                                                  |
//| Una sola plantilla, tres presets:                                |
//|                                                                  |
//|   Asian:   RangeStartUTC=23, RangeEndUTC=7,  EntryStart=7,  End=12
//|   London:  RangeStartUTC=7,  RangeEndUTC=8,  EntryStart=8,  End=12
//|   NY:      RangeStartUTC=13, RangeEndUTC=14, EntryStart=14, End=20
//|                                                                  |
//| Reglas idénticas a:                                              |
//|   src/signals/breakout/asian_session_orb.py                      |
//|   src/signals/breakout/london_open_breakout.py                   |
//|   src/signals/breakout/ny_open_breakout.py                       |
//|                                                                  |
//| Filtros: ADX > AdxMin, range_min_atr < range/ATR < range_max_atr,|
//|          H4 trend alineado con dirección del breakout            |
//|                                                                  |
//| SL = lado opuesto del rango ± AtrSlMult×ATR                      |
//| TP = entry ± RR × stop_distance                                  |
//+------------------------------------------------------------------+
#property copyright "FTMO-Scalper"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1  "Long"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLimeGreen
#property indicator_width1  2

#property indicator_label2  "Short"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrCrimson
#property indicator_width2  2

//─── Inputs ───
input group "Ventana del rango (UTC)"
input int    RangeStartUTC  = 7;
input int    RangeEndUTC    = 8;
input group "Ventana de entrada (UTC)"
input int    EntryStartUTC  = 8;
input int    EntryEndUTC    = 12;
input int    BrokerOffsetH  = 2;        // FTMO-Demo es UTC+2

input group "Filtros"
input int    AtrPeriod      = 14;
input int    AdxPeriod      = 14;
input double AdxMin         = 18.0;
input double RangeMinAtr    = 0.3;      // tamaño rango / ATR (mínimo)
input double RangeMaxAtr    = 3.5;      // tamaño rango / ATR (máximo)
input double AtrSlMult      = 0.3;      // buffer SL más allá del rango
input double RrTarget       = 2.5;
input bool   UseH4Filter    = true;
input int    H4EmaFast      = 50;
input int    H4EmaSlow      = 200;

input group "Visualización"
input bool   ShowRangeBox   = true;
input color  RangeColor     = clrSlateGray;
input color  EntryWindowCol = clrDarkGray;
input bool   ShowEntryBox   = true;
input bool   ShowSlTp       = true;     // SL/TP de la última señal
input color  SlColor        = clrCrimson;
input color  TpColor        = clrLimeGreen;
input int    MaxDaysBack    = 60;

//─── Buffers ───
double LongBuf[], ShortBuf[];

//─── Handles ───
int hAtr, hAdx;
int hEma50_H4 = INVALID_HANDLE;
int hEma200_H4 = INVALID_HANDLE;

//─── Status panel ───
string g_status_objs[5] = {
   "FTMO_ORB_TITLE",
   "FTMO_ORB_RANGE",
   "FTMO_ORB_ATR",
   "FTMO_ORB_ADX",
   "FTMO_ORB_H4"
};
string g_lastSL = "FTMO_ORB_LAST_SL";
string g_lastTP = "FTMO_ORB_LAST_TP";
string g_objPrefix = "FTMO_ORB_";

//+------------------------------------------------------------------+
int OnInit() {
   SetIndexBuffer(0, LongBuf,  INDICATOR_DATA);
   SetIndexBuffer(1, ShortBuf, INDICATOR_DATA);
   PlotIndexSetInteger(0, PLOT_ARROW, 233);
   PlotIndexSetInteger(1, PLOT_ARROW, 234);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   ArraySetAsSeries(LongBuf, false);
   ArraySetAsSeries(ShortBuf, false);

   hAtr = iATR(_Symbol, _Period, AtrPeriod);
   hAdx = iADX(_Symbol, _Period, AdxPeriod);
   if(UseH4Filter) {
      hEma50_H4  = iMA(_Symbol, PERIOD_H4, H4EmaFast, 0, MODE_EMA, PRICE_CLOSE);
      hEma200_H4 = iMA(_Symbol, PERIOD_H4, H4EmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   }

   if(hAtr==INVALID_HANDLE || hAdx==INVALID_HANDLE) return INIT_FAILED;
   if(UseH4Filter && (hEma50_H4==INVALID_HANDLE || hEma200_H4==INVALID_HANDLE))
      return INIT_FAILED;

   IndicatorSetString(INDICATOR_SHORTNAME, "FTMO ORB");
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
   // Limpiar todas las cajas dibujadas
   ObjectsDeleteAll(0, g_objPrefix);
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
   ObjectSetString(0, g_status_objs[0], OBJPROP_TEXT, "FTMO ORB");
   ObjectSetInteger(0, g_status_objs[0], OBJPROP_FONTSIZE, 10);
   ObjectSetString(0, g_status_objs[1], OBJPROP_TEXT, "Range: …");
   ObjectSetString(0, g_status_objs[2], OBJPROP_TEXT, "ATR: …");
   ObjectSetString(0, g_status_objs[3], OBJPROP_TEXT, "ADX: …");
   ObjectSetString(0, g_status_objs[4], OBJPROP_TEXT, "H4: …");
}

//+------------------------------------------------------------------+
struct DayRange {
   datetime day;
   datetime range_start_t;
   datetime range_end_t;
   double   high;
   double   low;
   bool     built;
   bool     signalled;
};

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

   int needed = MathMax(AtrPeriod*3, AdxPeriod*3) + 5;
   if(rates_total < needed) {
      Comment(StringFormat("FTMO_ORB: warmup (rates=%d, needed=%d)", rates_total, needed));
      return 0;
   }

   // Solo procesamos los últimos N bars donde TODOS los indicadores están calculados.
   int bc_atr = BarsCalculated(hAtr);
   int bc_adx = BarsCalculated(hAdx);
   int bc_min = MathMin(bc_atr, bc_adx);

   bool use_h4 = UseH4Filter;
   if(use_h4) {
      int bc_h4f = BarsCalculated(hEma50_H4);
      int bc_h4s = BarsCalculated(hEma200_H4);
      if(bc_h4f <= 0 || bc_h4s <= 0) use_h4 = false;
      else bc_min = MathMin(bc_min, MathMin(bc_h4f, bc_h4s));
   }

   if(bc_min <= needed) {
      Comment(StringFormat("FTMO_ORB: data not ready (bars_calculated=%d, needed=%d)",
                           bc_min, needed));
      return prev_calculated;
   }

   // Limitar a los últimos N bars (cap de 5000 para no procesar décadas).
   int n_use = MathMin(MathMin(rates_total, bc_min), 5000);
   int chart_start = rates_total - n_use;

   double atr[], adx[], h4f[], h4s[];
   ArraySetAsSeries(atr, false);
   ArraySetAsSeries(adx, false);
   ArraySetAsSeries(h4f, false);
   ArraySetAsSeries(h4s, false);

   if(CopyBuffer(hAtr,0,0,n_use,atr) != n_use ||
      CopyBuffer(hAdx,0,0,n_use,adx) != n_use) {
      Comment("FTMO_ORB: CopyBuffer mismatch on ATR/ADX");
      return prev_calculated;
   }

   if(use_h4) {
      if(CopyBuffer(hEma50_H4, 0,0,n_use,h4f) != n_use ||
         CopyBuffer(hEma200_H4,0,0,n_use,h4s) != n_use) {
         use_h4 = false;
      }
   }

   int rs = (RangeStartUTC + BrokerOffsetH) % 24;
   int re = (RangeEndUTC   + BrokerOffsetH) % 24;
   int es = (EntryStartUTC + BrokerOffsetH) % 24;
   int ee = (EntryEndUTC   + BrokerOffsetH) % 24;

   // Limpiar TODOS los buffers en el rango del chart
   for(int j = 0; j < rates_total; j++) {
      LongBuf[j]  = EMPTY_VALUE;
      ShortBuf[j] = EMPTY_VALUE;
   }

   // Solo procesamos los últimos MaxDaysBack días dentro de la ventana válida
   datetime cutoff = TimeCurrent() - (datetime)(MaxDaysBack * 86400);
   int start_idx = MathMax(chart_start, needed);
   for(int k = start_idx; k < rates_total; k++) {
      if(time[k] >= cutoff) { start_idx = k; break; }
   }

   // Limpiar cajas viejas
   ObjectsDeleteAll(0, g_objPrefix + "Box_");
   ObjectsDeleteAll(0, g_objPrefix + "EBox_");

   // Estado por día
   DayRange cur;
   cur.day = 0;
   cur.high = 0; cur.low = 0;
   cur.built = false; cur.signalled = false;
   cur.range_start_t = 0; cur.range_end_t = 0;

   // Mapping: chart_idx ci → indicator_idx ii = ci - chart_start
   for(int ci = start_idx; ci < rates_total; ci++) {
      int ii = ci - chart_start;
      if(ii < 0 || ii >= n_use) continue;

      MqlDateTime dt;
      TimeToStruct(time[ci], dt);
      datetime day_start = (datetime)((long)time[ci] / 86400 * 86400);

      if(day_start != cur.day) {
         cur.day = day_start;
         cur.high = 0; cur.low = 0;
         cur.built = false; cur.signalled = false;
         cur.range_start_t = 0; cur.range_end_t = 0;
      }

      bool in_range = InWindow(dt.hour, rs, re);
      if(in_range) {
         if(cur.range_start_t == 0) {
            cur.range_start_t = time[ci];
            cur.high = high[ci];
            cur.low  = low[ci];
         } else {
            cur.high = MathMax(cur.high, high[ci]);
            cur.low  = MathMin(cur.low,  low[ci]);
         }
         cur.range_end_t = time[ci] + (datetime)PeriodSeconds(_Period);
      }

      if(!in_range && cur.range_start_t > 0 && !cur.built && dt.hour >= re) {
         cur.built = true;
         if(ShowRangeBox) DrawRangeBox(cur);
      }

      if(!cur.built || cur.signalled) continue;

      bool in_entry = InWindow(dt.hour, es, ee);
      if(!in_entry) continue;

      double a = atr[ii], dx = adx[ii], cl = close[ci];
      if(a <= 0) continue;

      double range_size = cur.high - cur.low;
      bool size_ok = (range_size >= a * RangeMinAtr) && (range_size <= a * RangeMaxAtr);
      bool adx_ok  = dx >= AdxMin;

      bool is_long  = cl > cur.high;
      bool is_short = cl < cur.low;
      if(!is_long && !is_short) continue;
      if(!size_ok || !adx_ok) continue;

      if(use_h4) {
         if(is_long  && h4f[ii] < h4s[ii]) continue;
         if(is_short && h4f[ii] > h4s[ii]) continue;
      }

      double buffer = a * AtrSlMult;
      double sl, tp;
      if(is_long) {
         sl = cur.low - buffer;
         double risk = cl - sl;
         if(risk <= 0) continue;
         tp = cl + risk * RrTarget;
         LongBuf[ci] = low[ci];
      } else {
         sl = cur.high + buffer;
         double risk = sl - cl;
         if(risk <= 0) continue;
         tp = cl - risk * RrTarget;
         ShortBuf[ci] = high[ci];
      }
      cur.signalled = true;

      if(ShowSlTp && ci == rates_total - 1) DrawSlTp(time[ci], sl, tp);

      if(ShowEntryBox) DrawEntryBox(cur, time[ci], es, ee);
   }

   // ─── Status panel (inlined) ───
   int chart_last = rates_total - 1;
   int ind_last   = n_use - 1;
   if(chart_last >= 0 && ind_last >= 0) {
      double a = atr[ind_last], dx = adx[ind_last];

      string rg;
      if(cur.high > 0 && cur.low > 0 && cur.built) {
         double rs_size = cur.high - cur.low;
         double ratio   = (a > 0) ? rs_size / a : 0;
         string ok = (ratio >= RangeMinAtr && ratio <= RangeMaxAtr) ? "OK" : "X";
         rg = StringFormat("Range: %.5f (%.2fxATR) %s", rs_size, ratio, ok);
      } else if(cur.high > 0) {
         rg = StringFormat("Range building: H=%.5f L=%.5f", cur.high, cur.low);
      } else {
         rg = "Range: pending";
      }

      string adxtxt = StringFormat("ADX: %.1f (min %.0f) %s",
                                   dx, AdxMin, (dx >= AdxMin ? "OK" : "X"));
      string atrtxt = StringFormat("ATR: %.5f", a);

      string h4txt = "H4: off";
      if(use_h4) {
         double h4f_v = h4f[ind_last], h4s_v = h4s[ind_last];
         if(h4f_v > h4s_v)      h4txt = "H4: BULL";
         else if(h4f_v < h4s_v) h4txt = "H4: BEAR";
      }

      ObjectSetString(0, g_status_objs[1], OBJPROP_TEXT, rg);
      ObjectSetString(0, g_status_objs[2], OBJPROP_TEXT, atrtxt);
      ObjectSetString(0, g_status_objs[3], OBJPROP_TEXT, adxtxt);
      ObjectSetString(0, g_status_objs[4], OBJPROP_TEXT, h4txt);
      Comment(StringFormat("FTMO_ORB: OK | last bar @ %s", TimeToString(time[chart_last])));
      ChartRedraw(0);
   }

   return rates_total;
}

//+------------------------------------------------------------------+
bool InWindow(int hour, int wstart, int wend) {
   if(wstart < wend) return (hour >= wstart && hour < wend);
   return (hour >= wstart || hour < wend);
}

//+------------------------------------------------------------------+
void DrawRangeBox(const DayRange &r) {
   string n = StringFormat("%sBox_%I64d", g_objPrefix, (long)r.day);
   if(ObjectFind(0,n) < 0)
      ObjectCreate(0, n, OBJ_RECTANGLE, 0, r.range_start_t, r.high, r.range_end_t, r.low);
   ObjectSetInteger(0, n, OBJPROP_TIME,  0, r.range_start_t);
   ObjectSetDouble (0, n, OBJPROP_PRICE, 0, r.high);
   ObjectSetInteger(0, n, OBJPROP_TIME,  1, r.range_end_t);
   ObjectSetDouble (0, n, OBJPROP_PRICE, 1, r.low);
   ObjectSetInteger(0, n, OBJPROP_COLOR, RangeColor);
   ObjectSetInteger(0, n, OBJPROP_FILL, true);
   ObjectSetInteger(0, n, OBJPROP_BACK, true);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}

//+------------------------------------------------------------------+
void DrawEntryBox(const DayRange &r, datetime sig_time, int es, int ee) {
   string n = StringFormat("%sEBox_%I64d", g_objPrefix, (long)r.day);
   if(ObjectFind(0,n) >= 0) return;
   datetime e_start = r.range_end_t;
   // entry end del día (ee horas tras medianoche broker)
   datetime e_end = r.day + (datetime)(ee * 3600);
   if(e_end <= e_start) e_end = e_start + 6 * 3600;
   ObjectCreate(0, n, OBJ_RECTANGLE, 0, e_start, r.high, e_end, r.low);
   ObjectSetInteger(0, n, OBJPROP_COLOR, EntryWindowCol);
   ObjectSetInteger(0, n, OBJPROP_FILL, true);
   ObjectSetInteger(0, n, OBJPROP_BACK, true);
   ObjectSetInteger(0, n, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}

//+------------------------------------------------------------------+
void DrawSlTp(datetime t, double sl, double tp) {
   if(ObjectFind(0,g_lastSL)<0) ObjectCreate(0,g_lastSL,OBJ_HLINE,0,t,sl);
   ObjectSetDouble(0,g_lastSL,OBJPROP_PRICE,0,sl);
   ObjectSetInteger(0,g_lastSL,OBJPROP_COLOR,SlColor);
   ObjectSetInteger(0,g_lastSL,OBJPROP_STYLE,STYLE_DASH);
   ObjectSetInteger(0,g_lastSL,OBJPROP_WIDTH,1);

   if(ObjectFind(0,g_lastTP)<0) ObjectCreate(0,g_lastTP,OBJ_HLINE,0,t,tp);
   ObjectSetDouble(0,g_lastTP,OBJPROP_PRICE,0,tp);
   ObjectSetInteger(0,g_lastTP,OBJPROP_COLOR,TpColor);
   ObjectSetInteger(0,g_lastTP,OBJPROP_STYLE,STYLE_DASH);
   ObjectSetInteger(0,g_lastTP,OBJPROP_WIDTH,1);
}

//+------------------------------------------------------------------+
