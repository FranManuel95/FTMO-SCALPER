# data/news_filter.py — Filtro de noticias económicas

import requests
import logging
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

@dataclass
class NewsEvent:
    title:      str
    currency:   str
    impact:     str
    event_time: datetime

class NewsFilter:

    BLOCK_MINUTES      = 30
    CACHE_DURATION     = 3600
    WATCHED_CURRENCIES = {"USD", "EUR"}

    def __init__(self):
        self._cache:      List[NewsEvent] = []
        self._cache_time: float = 0
        self.log = logging.getLogger("NewsFilter")

    def _fetch_events(self) -> List[NewsEvent]:
        try:
            today = datetime.utcnow().strftime("%b%d.%Y").lower()
            url   = f"https://www.forexfactory.com/calendar?day={today}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp  = requests.get(url, headers=headers, timeout=10)
            from bs4 import BeautifulSoup
            soup  = BeautifulSoup(resp.text, "html.parser")
            events = []

            for row in soup.find_all("tr", class_="calendar__row"):
                impact_el   = row.find("td", class_="calendar__impact")
                title_el    = row.find("td", class_="calendar__event")
                time_el     = row.find("td", class_="calendar__time")
                currency_el = row.find("td", class_="calendar__currency")

                if not all([impact_el, title_el, time_el, currency_el]):
                    continue

                impact   = "high" if "high" in str(impact_el) else "low"
                currency = currency_el.get_text(strip=True)

                if impact != "high": continue
                if currency not in self.WATCHED_CURRENCIES: continue

                time_str = time_el.get_text(strip=True)
                try:
                    event_time = datetime.strptime(
                        f"{datetime.utcnow().date()} {time_str}",
                        "%Y-%m-%d %I:%M%p")
                except:
                    continue

                events.append(NewsEvent(
                    title      = title_el.get_text(strip=True),
                    currency   = currency,
                    impact     = impact,
                    event_time = event_time
                ))

            self.log.info(f"📰 {len(events)} eventos high-impact hoy")
            return events

        except Exception as e:
            self.log.error(f"Error news filter: {e}")
            return []

    def _refresh_if_needed(self):
        if time.time() - self._cache_time > self.CACHE_DURATION:
            self._cache      = self._fetch_events()
            self._cache_time = time.time()

    def is_news_active(self, now: datetime = None) -> bool:
        self._refresh_if_needed()
        now    = now or datetime.utcnow()
        window = timedelta(minutes=self.BLOCK_MINUTES)

        for event in self._cache:
            if abs((event.event_time - now).total_seconds()) <= window.total_seconds():
                self.log.warning(f"⛔ Noticia: {event.title} ({event.currency})")
                return True
        return False

    def next_clear_time(self, now: datetime = None) -> str:
        now    = now or datetime.utcnow()
        window = timedelta(minutes=self.BLOCK_MINUTES)
        for event in sorted(self._cache, key=lambda e: e.event_time):
            clear = event.event_time + window
            if clear > now:
                return clear.strftime("%H:%M UTC")
        return "Ahora mismo"