#!/usr/bin/env python3
"""
Fetches Estonian navigation marks from Transpordiamet NMA X-tee SOAP API
and produces GeoJSON for tippecanoe conversion to PMTiles.

Source: nma.vta.ee (CC BY 4.0)
Run: monthly via GitHub Actions.
"""

import json
import logging
import sys
import xml.etree.ElementTree as ET
from typing import Any

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SOAP_URL = "https://nma.vta.ee/xml_file"

SOAP_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope
  xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"
  xmlns:nma="http://producers.nma.xtee.riik.ee/producer/nma"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:xtee="http://x-tee.riik.ee/xsd/xtee.xsd"
  SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <SOAP-ENV:Header>
    <xtee:asutus xsi:type="xsd:string">1</xtee:asutus>
    <xtee:isikukood xsi:type="xsd:string">1</xtee:isikukood>
    <xtee:id xsi:type="xsd:string">111</xtee:id>
    <xtee:nimi xsi:type="xsd:string">nma.Navimark.v1</xtee:nimi>
    <xtee:andmekogu xsi:type="xsd:string">1</xtee:andmekogu>
  </SOAP-ENV:Header>
  <SOAP-ENV:Body>
    <nma:NavimarkRequest>
      <FilterCond>
        <HarbourLococode/>
      </FilterCond>
      <WithImages>N</WithImages>
    </nma:NavimarkRequest>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

# S-57/IALA type mapping for Estonian NMA types.
# Key = TypeName field value from SOAP response.
# Value = (seamark:type, extra properties dict)
TYPE_MAP: dict[str, tuple[str, dict[str, str]]] = {
    "Tuletorn": ("light_major", {}),
    "Tuletorn, sihi alumine": ("leading_line", {}),
    "Tuletorn, sihi ülemine": ("leading_line", {}),
    "Tuletorn, sihi alumine/ülemine": ("leading_line", {}),
    "Tulepaak": ("beacon_lateral", {}),
    "Tulepaak, sihi alumine": ("beacon_lateral", {}),
    "Tulepaak, sihi ülemine": ("beacon_lateral", {}),

    "Parema külje poi": ("buoy_lateral", {"seamark:buoy_lateral:category": "starboard"}),
    "Vasaku külje poi": ("buoy_lateral", {"seamark:buoy_lateral:category": "port"}),
    "Teljepoi": ("buoy_safe_water", {}),
    "Eraldiasuva ohu poi": ("buoy_isolated_danger", {}),

    "Parema külje tooder": ("buoy_lateral", {"seamark:buoy_lateral:category": "starboard"}),
    "Vasaku külje tooder": ("buoy_lateral", {"seamark:buoy_lateral:category": "port"}),
    "Teljetooder": ("buoy_safe_water", {}),
    "Eriotstarbeline tooder": ("buoy_special_purpose", {}),
    "Eraldiasuva ohu tooder": ("buoy_isolated_danger", {}),

    "Põhjapoi": ("buoy_cardinal", {"seamark:buoy_cardinal:category": "north"}),
    "Lõunapoi": ("buoy_cardinal", {"seamark:buoy_cardinal:category": "south"}),
    "Idapoi": ("buoy_cardinal", {"seamark:buoy_cardinal:category": "east"}),
    "Läänepoi": ("buoy_cardinal", {"seamark:buoy_cardinal:category": "west"}),

    "Põhjatooder": ("buoy_cardinal", {"seamark:buoy_cardinal:category": "north"}),
    "Lõunatooder": ("buoy_cardinal", {"seamark:buoy_cardinal:category": "south"}),
    "Idatooder": ("buoy_cardinal", {"seamark:buoy_cardinal:category": "east"}),
    "Läänetooder": ("buoy_cardinal", {"seamark:buoy_cardinal:category": "west"}),

    "Päevamärk": ("daymark", {}),
    "Päevamärk, sihi alumine": ("daymark", {}),
    "Päevamärk, sihi ülemine": ("daymark", {}),
}


def parse_navimarks(xml: str) -> list[dict[str, Any]]:
    marks: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        logger.error("XML parse error: %s", e)
        return marks

    ns = {
        "soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "nma": "http://producers.nma.xtee.riik.ee/producer/nma",
    }

    for item in root.iter():
        tag = item.tag
        if tag.endswith("}Navimark") or tag == "Navimark":
            mark = parse_single_mark(item)
            if mark:
                marks.append(mark)

    logger.info("Parsed %d navigation marks", len(marks))
    return marks


def parse_single_mark(item: ET.Element) -> dict[str, Any] | None:
    def text(tag: str) -> str | None:
        for el in item.iter():
            local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
            if local == tag and el.text:
                return el.text.strip()
        return None

    tyyp = text("Tyyp") or text("Type") or text("Tüüp") or ""
    nimi = text("Nimi") or text("Name") or ""
    lat_str = text("Lat") or text("Latitude") or text("Laius") or ""
    lon_str = text("Lon") or text("Longitude") or text("Pikkus") or ""

    if not lat_str or not lon_str:
        return None

    try:
        lat = float(lat_str.replace(",", "."))
        lon = float(lon_str.replace(",", "."))
    except ValueError:
        return None

    # Coordinates are in degrees × 60,000,000 (integer format)
    if lat > 180 or lon > 180:
        lat /= 60000000.0
        lon /= 60000000.0

    seamark_type: str
    extra_props: dict[str, str] = {}
    if tyyp in TYPE_MAP:
        seamark_type, extra_props = TYPE_MAP[tyyp]
    else:
        seamark_type = "buoy_lateral"
        extra_props = {}

    light_char = text("ValoKarakteristika") or text("LightChar") or ""
    light_colour = text("ValoVari") or text("LightColour") or ""
    light_period = text("ValoPeriod") or text("LightPeriod") or ""
    height = text("Korgus") or text("Height") or ""
    range_nm = text("Nähtavus") or text("Range") or ""
    mark_id = text("NM_EstNo") or text("ID") or text("Number") or ""

    props: dict[str, Any] = {"seamark:type": seamark_type}
    props.update(extra_props)
    if nimi:
        props["seamark:name"] = nimi
    if light_char:
        props["seamark:light:character"] = light_char
    if light_colour:
        props["seamark:light:colour"] = light_colour
    if light_period:
        props["seamark:light:period"] = light_period
    if height:
        props["seamark:light:height"] = height
    if range_nm:
        props["seamark:light:range"] = range_nm
    if mark_id:
        props["ee:id"] = mark_id
    if tyyp:
        props["ee:type"] = tyyp

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def main() -> None:
    logger.info("Fetching Estonian navigation marks from %s", SOAP_URL)

    try:
        response = requests.post(
            SOAP_URL,
            data=SOAP_REQUEST.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            timeout=60,
        )
        response.raise_for_status()
        xml = response.text
        logger.info("SOAP response: %d bytes", len(xml))
    except requests.RequestException as e:
        logger.error("Failed to fetch SOAP data: %s", e)
        sys.exit(1)

    marks = parse_navimarks(xml)

    if not marks:
        logger.warning("No marks parsed, exiting")
        sys.exit(1)

    geojson = {"type": "FeatureCollection", "features": marks}

    with open("ee_seamarks.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    logger.info("Generated ee_seamarks.geojson with %d features", len(marks))


if __name__ == "__main__":
    main()
