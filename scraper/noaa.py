"""Parse the CPC Spanish ENSO bulletin; the output contains plain text only."""
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
import re
import unicodedata
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, NavigableString

URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc_Sp.shtml"
SOURCE = "NOAA / Climate Prediction Center"
MAX_HTML = 512 * 1024
MONTHS = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
BLOCKS = ("p", "div", "br", "td", "tr", "article", "section", "h1", "h2", "h3", "li")


def clean(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def bulletin_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in reversed(soup.select("head, script, style, noscript, template")):
        tag.decompose()

    # Normalize source formatting while preserving punctuation next to links and emphasis.
    for run in soup.find_all(string=True):
        if type(run) is NavigableString:
            normalized = re.sub(r"\s+", " ", run)
            if normalized != run:
                run.replace_with(normalized)

    # HTML line breaks are semantic. Other source line breaks are just indentation.
    for tag in soup.find_all(BLOCKS):
        if tag.name == "br":
            tag.replace_with("\n")
        else:
            tag.insert_before("\n")
            tag.insert_after("\n")
    return "\n".join(filter(None, map(clean, soup.get_text().splitlines())))


@dataclass(frozen=True)
class Bulletin:
    published: str
    title: str
    status: str
    summary: str
    source: str = SOURCE
    url: str = URL

    @property
    def revision(self):
        payload = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode()).hexdigest()


def parse(raw):
    if not raw or len(raw) > MAX_HTML:
        raise ValueError("Tamaño de HTML fuera del límite.")
    marker = re.search(rb"charset\s*=\s*['\"]?([\w-]+)", raw[:4096], re.I)
    enc = marker[1].decode("ascii").lower() if marker else "utf-8"
    if enc not in {"utf-8", "utf8", "windows-1252", "iso-8859-1", "us-ascii"}:
        raise ValueError("Codificación HTML desconocida.")
    try:
        html = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        html = raw.decode("cp1252" if enc in {"iso-8859-1", "windows-1252"} or not marker else enc)
    saved_from = re.search(r"<!--\s*saved from url=\(\d+\)(\S+)\s*-->", html[:4096], re.I)
    if saved_from:
        link = urlsplit(saved_from[1])
        canonical = urlsplit(URL)
        if (link.scheme, link.netloc, link.path) != (canonical.scheme, canonical.netloc, canonical.path):
            raise ValueError("La URL de la captura no corresponde al boletín del CPC.")
    body = bulletin_text(html)
    # Bound the issue date to its masthead, so the next release never becomes the issue date.
    header = re.search(r"(EL NIÑO\s*/\s*OSCILACIÓN DEL SUR).{0,180}?(DISCUSIÓN DIAGNÓSTICA)"
                       r"(.{0,700}?)Estatus del Sistema de alerta del ENSO\s*:", body, re.I | re.S)
    if not header or not re.search(r"NCEP\s*/\s*NWS", header[3], re.I):
        raise ValueError("Cambió la cabecera o la atribución del boletín de NOAA.")
    dates = re.findall(r"\b(\d{1,2})\s+de\s+([a-záé]+)\s+de\s+(\d{4})\b", header[3], re.I)
    if len(dates) != 1 or dates[0][1].lower() not in MONTHS:
        raise ValueError("Fecha de publicación ausente o ambigua.")
    day, month, year = dates[0]
    published = date(int(year), MONTHS.index(month.lower()) + 1, int(day)).isoformat()
    result = re.match(r"\s*(.{1,220}?)\s*\nSinopsis\s*:\s*([^\n]{18,2600})(?:\n|$)",
                      body[header.end():], re.I | re.S)
    if not result:
        raise ValueError("Falta el estado ENSO o la sinopsis. Se conserva el historial.")
    return Bulletin(published, clean(header[1]) + " · " + clean(header[2]),
                    clean(result[1]), clean(result[2]))
