//+------------------------------------------------------------------+
//|                                          FTMO_TrailViewer.mq5   |
//|                  Visualizador del trailing stop en posiciones    |
//|                                                                  |
//| Para cada posición abierta del bot (magic=90210) sobre el        |
//| símbolo actual, dibuja:                                          |
//|   - Línea horizontal verde de entry                              |
//|   - Línea horizontal roja de SL (la que tiene el bot — se        |
//|     actualiza cuando el bot mueve el trail)                      |
//|   - Línea horizontal azul de TP                                  |
//|   - Línea de trail teórico (highest desde entry − ATR × mult)    |
//|     para comparar con lo que está poniendo el bot                |
//|                                                                  |
//| Panel de estado: ticket, side, entry, SL, TP, ATR, trail teórico |
//+------------------------------------------------------------------+
#property copyright "FTMO-Scalper"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   1

#property indicator_label1  "Trail teórico"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrGold
#property indicator_style1  STYLE_DASH
#property indicator_width1  1

input group "Bot"
input int    BotMagic       = 90210;
input int    AtrPeriod      = 14;
input double TrailAtrMult   = 0.3;      // ajusta al trail mult de la estrategia visible
input bool   ShowEntryLine  = true;
input bool   ShowSlLine     = true;
input bool   ShowTpLine     = true;
input bool   ShowTrailLine  = true;
input color  EntryColor     = clrLimeGreen;
input color  SlColor        = clrCrimson;
input color  TpColor        = clrDodgerBlue;

double TrailBuf[];

int hAtr;

string g_objPrefix = "FTMO_Trail_";
string g_status_objs[8] = {
   "FTMO_Trail_TITLE",
   "FTMO_Trail_TICKET",
   "FTMO_Trail_SIDE",
   "FTMO_Trail_ENTRY",
   "FTMO_Trail_SL",
   "FTMO_Trail_TP",
   "FTMO_Trail_ATR",
   "FTMO_Trail_THEORY"
};

//+------------------------------------------------------------------+
int OnInit() {
   SetIndexBuffer(0, TrailBuf, INDICATOR_DATA);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   ArraySetAsSeries(TrailBuf, false);

   hAtr = iATR(_Symbol, _Period, AtrPeriod);
   if(hAtr == INVALID_HANDLE) return INIT_FAILED;

   IndicatorSetString(INDICATOR_SHORTNAME, "FTMO Trail Viewer");
   CreateStatusPanel();
   EventSetTimer(2);  // refrescar cada 2s
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   EventKillTimer();
   for(int i=0; i<ArraySize(g_status_objs); i++)
      ObjectDelete(0, g_status_objs[i]);
   ObjectsDeleteAll(0, g_objPrefix + "L_");
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
   ObjectSetString(0, g_status_objs[0], OBJPROP_TEXT, "FTMO Trail Viewer");
   ObjectSetInteger(0, g_status_objs[0], OBJPROP_FONTSIZE, 10);
}

//+------------------------------------------------------------------+
void OnTimer() {
   RefreshLines();
   ChartRedraw(0);
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

   for(int i = 0; i < rates_total; i++) TrailBuf[i] = EMPTY_VALUE;

   double atr[];
   if(CopyBuffer(hAtr, 0, 0, rates_total, atr) <= 0) return prev_calculated;

   // Buscar posición primera del bot en el símbolo activo
   ulong tk = FindBotTicket();
   if(tk == 0) {
      RefreshLines();
      return rates_total;
   }
   if(!PositionSelectByTicket(tk)) return rates_total;

   datetime entry_time = (datetime)PositionGetInteger(POSITION_TIME);
   long pos_type = PositionGetInteger(POSITION_TYPE);
   bool is_long = (pos_type == POSITION_TYPE_BUY);

   double highest = 0, lowest = 0;
   bool first = true;

   for(int i = 0; i < rates_total; i++) {
      if(time[i] < entry_time) continue;

      if(first) {
         highest = high[i];
         lowest  = low[i];
         first   = false;
      } else {
         highest = MathMax(highest, high[i]);
         lowest  = MathMin(lowest,  low[i]);
      }

      if(ShowTrailLine) {
         double a = atr[i];
         if(a <= 0) { TrailBuf[i] = EMPTY_VALUE; continue; }
         TrailBuf[i] = is_long ? (highest - a * TrailAtrMult)
                                : (lowest  + a * TrailAtrMult);
      }
   }

   RefreshLines();
   return rates_total;
}

//+------------------------------------------------------------------+
ulong FindBotTicket() {
   int total = PositionsTotal();
   for(int idx = 0; idx < total; idx++) {
      ulong tk = PositionGetTicket(idx);
      if(tk == 0) continue;
      if(!PositionSelectByTicket(tk)) continue;
      long mg = PositionGetInteger(POSITION_MAGIC);
      string sym = PositionGetString(POSITION_SYMBOL);
      if(mg == BotMagic && sym == _Symbol) return tk;
   }
   return 0;
}

//+------------------------------------------------------------------+
void RefreshLines() {
   ObjectsDeleteAll(0, g_objPrefix + "L_");

   ulong tk = FindBotTicket();
   if(tk == 0) {
      ObjectSetString(0, g_status_objs[1], OBJPROP_TEXT, "Sin posición abierta");
      ObjectSetString(0, g_status_objs[2], OBJPROP_TEXT, "");
      ObjectSetString(0, g_status_objs[3], OBJPROP_TEXT, "");
      ObjectSetString(0, g_status_objs[4], OBJPROP_TEXT, "");
      ObjectSetString(0, g_status_objs[5], OBJPROP_TEXT, "");
      ObjectSetString(0, g_status_objs[6], OBJPROP_TEXT, "");
      ObjectSetString(0, g_status_objs[7], OBJPROP_TEXT, "");
      return;
   }
   if(!PositionSelectByTicket(tk)) return;

   double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl    = PositionGetDouble(POSITION_SL);
   double tp    = PositionGetDouble(POSITION_TP);
   long pos_type = PositionGetInteger(POSITION_TYPE);
   bool is_long = (pos_type == POSITION_TYPE_BUY);

   if(ShowEntryLine) DrawHLine("L_ENTRY", entry, EntryColor, STYLE_SOLID, 1);
   if(ShowSlLine)    DrawHLine("L_SL",    sl,    SlColor,    STYLE_DASH,  1);
   if(ShowTpLine)    DrawHLine("L_TP",    tp,    TpColor,    STYLE_DASH,  1);

   double atr_now[1];
   if(CopyBuffer(hAtr, 0, 0, 1, atr_now) <= 0) atr_now[0] = 0;

   double trail_theory = 0;
   if(atr_now[0] > 0) {
      // Recompute end-of-history trail
      datetime entry_time = (datetime)PositionGetInteger(POSITION_TIME);
      MqlRates r[];
      ArraySetAsSeries(r, false);
      int copied = CopyRates(_Symbol, _Period, entry_time, TimeCurrent(), r);
      if(copied > 0) {
         double hh = r[0].high, ll = r[0].low;
         for(int i=1; i<copied; i++) {
            if(r[i].high > hh) hh = r[i].high;
            if(r[i].low  < ll) ll = r[i].low;
         }
         trail_theory = is_long ? (hh - atr_now[0] * TrailAtrMult)
                                : (ll + atr_now[0] * TrailAtrMult);
      }
   }

   ObjectSetString(0, g_status_objs[1], OBJPROP_TEXT, StringFormat("Ticket: %I64u", tk));
   ObjectSetString(0, g_status_objs[2], OBJPROP_TEXT, "Side: " + (is_long ? "LONG" : "SHORT"));
   ObjectSetString(0, g_status_objs[3], OBJPROP_TEXT, StringFormat("Entry: %.5f", entry));
   ObjectSetString(0, g_status_objs[4], OBJPROP_TEXT, StringFormat("SL bot: %.5f", sl));
   ObjectSetString(0, g_status_objs[5], OBJPROP_TEXT, StringFormat("TP bot: %.5f", tp));
   ObjectSetString(0, g_status_objs[6], OBJPROP_TEXT, StringFormat("ATR: %.5f", atr_now[0]));
   ObjectSetString(0, g_status_objs[7], OBJPROP_TEXT, StringFormat("Trail teórico: %.5f", trail_theory));
}

//+------------------------------------------------------------------+
void DrawHLine(string suffix, double price, color c, int style, int width) {
   string n = g_objPrefix + suffix;
   if(ObjectFind(0,n) < 0) ObjectCreate(0,n,OBJ_HLINE,0,0,price);
   ObjectSetDouble(0,n,OBJPROP_PRICE,0,price);
   ObjectSetInteger(0,n,OBJPROP_COLOR,c);
   ObjectSetInteger(0,n,OBJPROP_STYLE,style);
   ObjectSetInteger(0,n,OBJPROP_WIDTH,width);
   ObjectSetInteger(0,n,OBJPROP_SELECTABLE,false);
}
//+------------------------------------------------------------------+
