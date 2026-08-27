import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import logging
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, date

logging.basicConfig(level=logging.INFO)


class AnsesCalendarService:
    """
    Servicio para obtener y parsear en tiempo real los calendarios de pago
    desde la fuente oficial de ANSES.
    """

    CALENDAR_URL = "https://anses.gob.ar/consultas/calendario-de-pagos"
    FALLBACK_URL_TEMPLATE = "https://hacecuentas.com/calendario-pagos-anses-{month}-{year}"
    CACHE_FILE = "app/calendar_cache.json"
    PREFETCH_DAY = 20

    @staticmethod
    def _normalize_month(month: str) -> str:
        normalized = unicodedata.normalize("NFD", month.lower())
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")

    def _period_labels(self):
        current = datetime.now()
        next_month = 1 if current.month == 12 else current.month + 1
        next_year = current.year + 1 if current.month == 12 else current.year
        return (
            current.strftime("%B").lower(),
            next_month,
            next_year,
        )

    def _find_latest_date(self, schedules: Dict, target_year: Optional[int] = None) -> Optional[date]:
        """
        Encuentra la última fecha de pago en un calendario para determinar su vigencia.
        Ahora maneja rangos de fecha (ej: "DD/MM al DD/MM").
        """
        latest_date = None
        current_year = target_year or datetime.now().year
        for prestacion in schedules.values():
            for entry in prestacion.get("dates", []):
                try:
                    date_str = entry["fecha"]
                    # Maneja rangos como "DD/MM al DD/MM" tomando la última fecha.
                    if " al " in date_str:
                        date_str = date_str.split(" al ")[-1]

                    day, month = map(int, date_str.strip().split('/'))

                    # Lógica simple para manejar el cambio de año (ej. calendario de Diciembre con pagos en Enero).
                    current_month = datetime.now().month
                    year_to_use = current_year
                    if target_year is None and current_month >= 10 and month < 3:
                        year_to_use = current_year + 1

                    date_obj = datetime(year_to_use, month, day).date()

                    if latest_date is None or date_obj > latest_date:
                        latest_date = date_obj
                except (ValueError, IndexError):
                    # Ignora entradas que no tengan un formato de fecha parseable (ej. texto).
                    continue
        return latest_date

    def _split_by_period(self, schedules: Dict):
        current = datetime.now()
        next_month = 1 if current.month == 12 else current.month + 1
        next_year = current.year + 1 if current.month == 12 else current.year
        current_names = {
            self._normalize_month(current.strftime("%B")),
            self._normalize_month(("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre").split()[current.month - 1]),
        }
        next_name = self._normalize_month(
            ("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre").split()[next_month - 1]
        )
        current_schedules = {}
        next_schedules = {}
        for title, schedule in schedules.items():
            month = self._normalize_month(schedule.get("month", ""))
            if month in current_names:
                current_schedules[title] = schedule
            elif month == next_name:
                next_schedules[title] = schedule
        return current_schedules, next_schedules, current.year, next_year

    def _fetch_calendar_html(self) -> Optional[str]:
        """
        Obtiene el contenido HTML de la página de calendarios de ANSES.
        """
        current = datetime.now()
        month_names = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
        next_month = 1 if current.month == 12 else current.month + 1
        next_year = current.year + 1 if current.month == 12 else current.year
        urls = [
            self.CALENDAR_URL,
            self.FALLBACK_URL_TEMPLATE.format(month=month_names[next_month - 1], year=next_year),
        ]
        for url in urls:
            try:
                response = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=15,
                )
                response.raise_for_status()
                response.encoding = response.apparent_encoding
                self._last_source_url = url
                return response.text
            except requests.RequestException as e:
                logging.warning("No se pudo obtener el calendario desde %s: %s", url, e)
        return None

    def _fetch_url_html(self, url: str) -> Optional[str]:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except requests.RequestException as e:
            logging.warning("No se pudo obtener el calendario desde %s: %s", url, e)
            return None

    def _parse_calendar_html(self, html_content: str) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
        """
        Parsea el contenido HTML para extraer los calendarios de pago.
        """
        if not html_content:
            return {}

        soup = BeautifulSoup(html_content, 'html.parser')
        schedules = {}

        # Los calendarios oficiales están dentro de 'accordion-item'.
        accordion_items = soup.find_all('div', class_='accordion-item')

        for item in accordion_items:
            title_element = item.find('h3')
            if not title_element:
                continue

            title = title_element.get_text(strip=True)
            month_element = item.find('h4', class_='cobroMes')
            month = month_element.get_text(strip=True).replace("Mes a cobrar:", "").strip() if month_element else "No especificado"

            if title not in schedules:
                schedules[title] = {"month": month, "dates": []}

            date_entries = item.find_all('div', class_='date')
            for entry in date_entries:
                doc_element = entry.find('div', class_='documento')
                date_element = entry.find('div', class_='fecha')

                if doc_element and date_element:
                    doc_text = doc_element.get_text(strip=True)
                    # Normaliza el texto del documento para consistencia.
                    if doc_text.lower().startswith("documentos terminados en"):
                        doc_text = doc_text.replace("Documentos", "DNI")

                    date_text = date_element.get_text(strip=True)
                    schedules[title]["dates"].append({
                        "documento": doc_text,
                        "fecha": date_text
                    })
        if schedules:
            return schedules

        # Respaldo para publicaciones con tablas estructuradas mientras ANSES bloquea el acceso.
        fallback_titles = {
            "jubilados y pensionados que cobran hasta la minima": "Jubilaciones y pensiones que no superen el haber mínimo",
            "jubilados y pensionados que superan la minima": "Jubilaciones y pensiones que superen el haber mínimo",
            "auh y asignaciones familiares (suaf)": "Asignación Familiar por Hijo y Asignación Universal por Hijo",
            "pensiones no contributivas (pnc)": "Pensiones No Contributivas",
        }
        for table in soup.find_all("table"):
            heading = table.find_previous(["h2", "h3", "h4"])
            heading_text = self._normalize_month(heading.get_text(" ", strip=True)) if heading else ""
            title = fallback_titles.get(heading_text)
            if not title:
                continue
            entries = []
            for row in table.find_all("tr"):
                cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.find_all(["th", "td"])]
                if len(cells) < 2 or not re.search(r"\d", cells[0]):
                    continue
                date_match = re.search(r"\b\d{1,2} de septiembre\b", cells[1], re.IGNORECASE)
                if not date_match:
                    continue
                day = re.search(r"\d{1,2}", date_match.group()).group()
                entries.append({"documento": f"DNI terminados en {cells[0]}", "fecha": f"{day}/9"})
            if entries:
                schedules[title] = {"month": "Septiembre", "dates": entries}
        if schedules:
            return schedules

        script_text = " ".join(script.get_text(" ", strip=True) for script in soup.find_all("script"))
        script_titles = {
            "minima": "Jubilaciones y pensiones que no superen el haber mínimo",
            "superan": "Jubilaciones y pensiones que superen el haber mínimo",
            "auh": "Asignación Familiar por Hijo y Asignación Universal por Hijo",
            "pnc": "Pensiones No Contributivas",
        }
        for group, title in script_titles.items():
            match = re.search(rf'{group}:\{{name:"[^"]+",dates:\[([^\]]+)\]', script_text)
            if not match:
                continue
            entries = []
            for raw_date in re.findall(r'"([^"\n]+)"', match.group(1)):
                date_match = re.search(r"\b(\d{1,2}) de ([a-záéíóú]+)\b", raw_date, re.IGNORECASE)
                if date_match:
                    entries.append({
                        "documento": "DNI terminados en todos los números",
                        "fecha": f"{date_match.group(1)}/{self._month_number(date_match.group(2))}",
                    })
            if entries:
                schedules[title] = {"month": self._month_name_from_date(entries[0]["fecha"]), "dates": entries}
        return schedules

    @staticmethod
    def _month_number(month: str) -> int:
        months = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
        return months.index(month.lower()) + 1

    @staticmethod
    def _month_name_from_date(date_text: str) -> str:
        months = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
        return months[int(date_text.split("/")[1]) - 1].capitalize()

    def _fetch_and_cache_schedules(self) -> Dict:
        """
        Obtiene los datos desde la web, los parsea y los guarda en el caché.
        """
        logging.info("Realizando nueva consulta al sitio web de ANSES para actualizar calendario.")
        html_content = self._fetch_calendar_html()
        if not html_content:
            logging.error("No se pudo obtener el HTML. No se puede actualizar el caché.")
            return {}

        schedules = self._parse_calendar_html(html_content)
        current = datetime.now()
        month_names = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
        current_url = self.FALLBACK_URL_TEMPLATE.format(
            month=month_names[current.month - 1], year=current.year
        )
        next_month = 1 if current.month == 12 else current.month + 1
        next_year = current.year + 1 if current.month == 12 else current.year
        current_schedules, next_schedules, current_year, next_year = self._split_by_period(schedules)
        if not current_schedules:
            current_html = self._fetch_url_html(current_url)
            if current_html:
                current_schedules = self._parse_calendar_html(current_html)
        if not next_schedules:
            next_url = self.FALLBACK_URL_TEMPLATE.format(month=month_names[next_month - 1], year=next_year)
            next_html = self._fetch_url_html(next_url)
            if next_html:
                next_schedules = self._parse_calendar_html(next_html)
        if not current_schedules and not next_schedules:
            logging.warning("Se obtuvo el HTML pero no se pudieron parsear los calendarios.")
            return {}

        previous_cache = {}
        try:
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                previous_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            pass
        if not current_schedules:
            current_schedules = previous_cache.get("current_month", previous_cache.get("schedules", {}))
        current_last_payment = self._find_latest_date(current_schedules, current_year)
        next_last_payment = self._find_latest_date(next_schedules, next_year)

        cache_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "last_check_date": datetime.now().date().isoformat(),
            "current_month": current_schedules,
            "next_month": next_schedules,
            "last_payment_date": current_last_payment.isoformat() if current_last_payment else None,
            "next_last_payment_date": next_last_payment.isoformat() if next_last_payment else None,
        }

        try:
            os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=4)
            logging.info(
                "Caché actualizado. Último pago actual: %s. Último pago siguiente: %s",
                current_last_payment,
                next_last_payment,
            )
        except IOError as e:
            logging.error(f"No se pudo escribir en el archivo de caché {self.CACHE_FILE}: {e}")

        return {
            "mes_actual": current_schedules,
            "mes_siguiente": next_schedules,
        }

    def get_payment_schedules(self) -> Dict:
        """
        Devuelve por separado el calendario actual y el siguiente.
        Desde el día 20 se intenta una actualización diaria del siguiente mes.
        """
        cache = {}
        try:
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)

                if "current_month" not in cache:
                    cache = {
                        "timestamp": cache.get("timestamp", "1970-01-01T00:00:00"),
                        "last_check_date": None,
                        "current_month": cache.get("schedules", {}),
                        "next_month": {},
                        "last_payment_date": cache.get("last_payment_date"),
                        "next_last_payment_date": None,
                    }

        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:
            logging.warning(f"Caché no encontrado o inválido. Se intentará obtener uno nuevo. Razón: {e}")

        today = datetime.now().date()
        missing_current = not cache.get("current_month")
        should_check_next = today.day >= self.PREFETCH_DAY
        checked_today = cache.get("last_check_date") == today.isoformat()
        if (should_check_next and not checked_today) or missing_current:
            logging.info("Día de comprobación anticipada. Se buscará el calendario siguiente.")
            refreshed = self._fetch_and_cache_schedules()
            if refreshed:
                return refreshed
            cache["last_check_date"] = today.isoformat()
            try:
                with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False, indent=4)
            except IOError as e:
                logging.error(f"No se pudo registrar la comprobación diaria: {e}")

        return {
            "mes_actual": cache.get("current_month", {}),
            "mes_siguiente": cache.get("next_month", {}),
        }
